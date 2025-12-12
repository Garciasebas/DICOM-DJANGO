import pydicom
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
import os
import traceback
import shutil
import tempfile
from pathlib import Path
from dicom2nifti import convert_directory
import json
import zipfile
from .models import DicomFile, DicomTag, Experiment, Participant, ConsentFile, Member
from .forms import DicomFileForm, DicomTagForm, DicomUploadForm, ExperimentForm
import uuid
import numpy as np
import nibabel as nib
import uuid
from .bids_utils import (
    normalize_subject_id, detect_modality, convert_dicom_to_nifti,
    create_dataset_description, create_participants_tsv
)

def generate_pacient_code():
    # Genera un UUID4 y toma los primeros 8 caracteres en mayúsculas
    return str(uuid.uuid4())[:8].upper()



def process_dicom_file(dicom_file_upload, participant=None, experiment=None):
    """
    Procesa un archivo DICOM: lee, anonimiza, guarda y crea registros en BD.
    
    Args:
        dicom_file_upload: Archivo subido desde request.FILES
        participant: Instancia de Participant (opcional)
        experiment: Instancia de Experiment (opcional)
    
    Returns:
        Tuple: (DicomFile instance, list of tag dictionaries)
    """
    # Leer el archivo DICOM
    ds = pydicom.dcmread(dicom_file_upload)
    
    # No aplicar anonimización aquí. Guardar archivo original.
    # ds = anonymize_dicom(ds)  <-- REMOVED
    
    # Generar código de paciente
    pacient_code = generate_pacient_code()
    
    # Crear directorio y nombre de archivo para RAW
    # El path debe ser relativo a MEDIA_ROOT (sin incluir 'media/')
    save_dir = Path("media/dicoms/raw/")
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{pacient_code}_{uuid.uuid4().hex[:6]}.dcm"
    full_path = save_dir / filename
    
    # Guardar el archivo ORIGINAL
    ds.save_as(str(full_path))
    
    # Path relativo a MEDIA_ROOT para Django FileField
    relative_path = f"dicoms/raw/{filename}"
    
    # Crear instancia DicomFile
    dicom_instance = DicomFile.objects.create(
        participant=participant,
        experiment=experiment,
        patient_name=pacient_code,
        file=relative_path,  # Usar path relativo a MEDIA_ROOT
        original_filename=dicom_file_upload.name,
        file_size=dicom_file_upload.size
    )
    
    # Guardar los tags en la base de datos
    dicom_data = []
    for element in ds:
        dicom_entry = DicomTag.objects.create(
            dicom_file=dicom_instance,
            tag=str(element.tag),
            description=element.description(),
            vr=element.VR,
            value=str(element.value)
        )
        dicom_data.append({
            'tag': dicom_entry.tag,
            'description': dicom_entry.description,
            'vr': dicom_entry.vr,
            'value': dicom_entry.value,
        })
    
    return dicom_instance, dicom_data



@login_required
def upload_dicom(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dicom_file = request.FILES['dicom_file']
            
            # Usar la función helper para procesar el DICOM
            dicom_instance, dicom_data = process_dicom_file(dicom_file)
            
            # Pasar los datos DICOM anonimizados a la plantilla de éxito
            return render(request, 'success.html', {
                'dicom_data': dicom_data, 
                'patient_name': dicom_instance.patient_name
            })

    else:
        form = DicomUploadForm()

    return render(request, 'upload.html', {'form': form})

class DicomFileListView(LoginRequiredMixin, ListView):
    model = DicomFile
    template_name = 'dicomfile_list.html'  # Nombre de tu plantilla
    context_object_name = 'dicom_files'
    paginate_by = 10  # Número de resultados por página

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(patient_name__icontains=query))
        return queryset

class DicomFileDetailView(LoginRequiredMixin, DetailView):
    model = DicomFile
    template_name = 'dicom_app/dicomfile_detail.html'  # Plantilla corregida
    context_object_name = 'dicom_file'  # Nombre del contexto en la plantilla
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add participant_id to context for the back button
        if self.object.participant:
            context['participant_id'] = self.object.participant.id
            
        # Optimization: Fetch all tags efficiently
        # We fetch all tags in one query to avoid N+1 issues and multiple hits
        all_tags = list(self.object.tags.all())
        
        # Filter and clean tags for display
        cleaned_tags = []
        binary_vrs = ["OB", "OW", "OF", "OL", "UN"]
        
        for tag in all_tags:
            display_value = tag.value
            
            # Check for binary VRs, PixelData, or excessive length
            if (tag.vr in binary_vrs or 
                "PixelData" in tag.tag or 
                "7FE0,0010" in tag.tag or 
                len(tag.value) > 400):
                display_value = "[Valor binario omitido]"
            
            cleaned_tags.append({
                'tag': tag.tag,
                'description': tag.description,
                'vr': tag.vr,
                'value': display_value
            })
        
        # Split into initial (server-side rendered) and remaining (client-side rendered)
        initial_count = 50
        context['initial_tags'] = cleaned_tags[:initial_count]
        
        # Serialize remaining tags for JavaScript
        context['remaining_tags_json'] = json.dumps(cleaned_tags[initial_count:])
        return context

class DicomFileCreateView(LoginRequiredMixin, CreateView):
    model = DicomFile
    form_class = DicomFileForm
    template_name = 'dicomfile_form.html'
    success_url = reverse_lazy('dicomfile_list')

class DicomFileUpdateView(LoginRequiredMixin, UpdateView):
    model = DicomFile
    form_class = DicomFileForm
    template_name = 'dicomfile_form.html'
    
    def get_success_url(self):
        return reverse_lazy('dicomfile_detail', kwargs={'pk': self.object.pk})

class DicomFileDeleteView(LoginRequiredMixin, DeleteView):
    model = DicomFile
    template_name = 'dicomfile_confirm_delete.html'
    
    def get_success_url(self):
        # Redirect to the participant's experiments list after deletion
        if self.object.participant:
            return reverse_lazy('participant_experiments', kwargs={'participant_id': self.object.participant.id})
        return reverse_lazy('participant_dashboard')

def convert_single_dicom_to_nifti(dicom_path, output_path):
    ds = pydicom.dcmread(dicom_path)
    if "PixelData" not in ds:
        raise Exception("DICOM no contiene datos de imagen (PixelData)")

    image = ds.pixel_array
    if image.ndim < 2:
        raise Exception("La imagen es inválida o vacía.")

    affine = np.eye(4)
    nii = nib.Nifti1Image(image, affine)
    nib.save(nii, output_path)

@login_required
def export_dicom_to_bids(request, pk):
    dicom_instance = get_object_or_404(DicomFile, pk=pk)
    dicom_path = dicom_instance.file.path

    if not os.path.exists(dicom_path):
        raise Http404("Archivo DICOM no encontrado")

    temp_dir = tempfile.mkdtemp()
    try:
        # Generate BIDS structure
        subject_id = normalize_subject_id(1) # Single file export gets sub-01
        session_id = "ses-01"
        
        # Detect modality
        ds = pydicom.dcmread(dicom_path)
        modality_folder, suffix = detect_modality(ds)
        
        output_dir = Path(temp_dir) / subject_id / session_id / modality_folder
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_basename = f"{subject_id}_{suffix}"
        
        # Convert
        nifti_path, json_path = convert_dicom_to_nifti(dicom_path, output_dir, output_basename)
        
        if not nifti_path:
             return HttpResponse("❌ La conversión falló: no se generó ningún archivo .nii.gz", status=500)

        # Create dataset_description.json
        create_dataset_description(Path(temp_dir))
        
        # Create participants.tsv (minimal)
        create_participants_tsv(Path(temp_dir), [{
            'participant_id': subject_id,
            'age': 'n/a',
            'sex': 'n/a',
            'group': 'control'
        }])

        # Zip
        zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_dir)
                    zipf.write(full_path, arcname=arcname)

        return FileResponse(open(zip_path, 'rb'), as_attachment=True, filename=f"{subject_id}_bids.zip")
        
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(f"Error exportando a BIDS: {e}", status=500)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@login_required
def export_experiment_to_bids(request, experiment_id):
    """
    Exporta todos los archivos DICOM de un experimento a formato BIDS.
    Genera una estructura BIDS completa con todos los participantes.
    """
    experiment = get_object_or_404(Experiment, pk=experiment_id)
    
    # Crear directorio temporal para la estructura BIDS
    temp_dir = tempfile.mkdtemp()
    bids_root = Path(temp_dir) / "my_dataset"
    bids_root.mkdir(parents=True, exist_ok=True)
    
    try:
        # Obtener todos los participantes del experimento
        participants = experiment.participants.all()
        
        if not participants.exists():
            return HttpResponse("No hay participantes asociados a este experimento.", status=404)
        
        participants_data = []
        
        # Procesar cada participante
        for idx, participant in enumerate(participants, start=1):
            # Normalizar ID: sub-01, sub-02...
            subject_id = normalize_subject_id(idx)
            
            participants_data.append({
                'participant_id': subject_id,
                'age': 'n/a', # Podríamos sacar esto de metadatos si existieran
                'sex': 'n/a',
                'group': 'control' # Default
            })
            
            subject_dir = bids_root / subject_id
            
            # Obtener todos los archivos DICOM del participante en este experimento
            dicom_files = DicomFile.objects.filter(
                participant=participant,
                experiment=experiment
            )
            
            # Procesar cada archivo DICOM
            for dicom_file in dicom_files:
                try:
                    dicom_path = dicom_file.file.path
                    
                    if not os.path.exists(dicom_path):
                        print(f"⚠️ Archivo DICOM no encontrado: {dicom_path}")
                        continue
                    
                    # Detectar modalidad
                    ds = pydicom.dcmread(dicom_path)
                    modality_folder, suffix = detect_modality(ds)
                    
                    # Estructura: sub-XX/modality/
                    # Nota: BIDS a veces usa ses-XX. El usuario pidió sub-01/anat/...
                    # Si quisiéramos sesiones: sub-01/ses-01/anat/...
                    # El prompt dice: sub-01/anat/ (sin sesión explícita en el ejemplo principal, 
                    # pero luego dice "sub-01/anat/"). Seguiré el ejemplo del prompt.
                    
                    output_dir = subject_dir / modality_folder
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Logic to detect existing files and increment index
                    if modality_folder == 'func':
                        # Pattern: sub-01_task-rest_run-XX_bold
                        # We glob for *task-rest*bold.nii.gz to count existing runs
                        # Or if suffix is just 'task-rest_bold', we can split it or look for the unique part
                        
                        # In detect_modality for func we return suffix="task-rest_bold"
                        # We want: sub-XX_task-rest_run-XX_bold
                        
                        # Count existing .nii.gz files in this folder that match pattern
                        existing_files = list(output_dir.glob("*_bold.nii.gz"))
                        run_index = len(existing_files) + 1
                        run_entity = f"run-{run_index:02d}"
                        
                        # Construct basename
                        # suffix is 'task-rest_bold', we want to insert run-XX
                        if "task-rest" in suffix:
                            # format: sub-XX_task-rest_run-XX_bold
                            output_basename = f"{subject_id}_task-rest_{run_entity}_bold"
                        else:
                            # fallback if suffix changes
                            output_basename = f"{subject_id}_{run_entity}_{suffix}"
                            
                    else:
                        # For anat and dwi use 'acq'
                        # sub-XX_acq-XX_T1w or sub-XX_acq-XX_dwi
                        
                        # Count files with same suffix
                        existing_files = list(output_dir.glob(f"*{suffix}.nii.gz"))
                        acq_index = len(existing_files) + 1
                        acq_entity = f"acq-{acq_index:02d}"
                        
                        output_basename = f"{subject_id}_{acq_entity}_{suffix}"
                    
                    # Convertir
                    print(f"📦 Processing DICOM {dicom_file.id} for {subject_id}/{modality_folder}")
                    nifti_path, json_path = convert_dicom_to_nifti(dicom_path, output_dir, output_basename)
                    
                    if not nifti_path:
                        print(f"⚠️ Conversion failed for DICOM {dicom_file.id}, skipping...")
                        continue
                    
                except Exception as e:
                    print(f"⚠️ Error procesando archivo DICOM {dicom_file.id}: {str(e)}")
                    traceback.print_exc()
                    continue
        
        # Crear participants.tsv
        create_participants_tsv(bids_root, participants_data)
        
        # Crear dataset_description.json
        create_dataset_description(bids_root)
        
        # Comprimir todo en un ZIP
        zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(bids_root):
                for file in files:
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, temp_dir) # relative to temp_dir so my_dataset is root
                    zipf.write(full_path, arcname=arcname)
        
        # Retornar el archivo ZIP
        experiment_name_safe = experiment.name.replace(" ", "_").lower()
        return FileResponse(
            open(zip_path, 'rb'), 
            as_attachment=True, 
            filename=f"{experiment_name_safe}_bids.zip"
        )
        
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(f"Error exportando experimento: {e}", status=500)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def zip_bids_folder(bids_dir):
    zip_path = bids_dir + '.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(bids_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=os.path.relpath(file_path, bids_dir))
    return zip_path

def main_menu(request):
    return render(request, 'main_menu.html')

@login_required
def experiment_success(request):
    """Vista de éxito después de crear un experimento"""
    return render(request, 'dicom_app/experiment_success.html')

# Experiment and Participant Views
@login_required
def dashboard(request):
    # Check if user is in 'Participante' group
    if request.user.groups.filter(name='Participante').exists():
        return redirect('participant_dashboard')
        
    experiments = Experiment.objects.filter(status='Active')
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        experiments = experiments.filter(name__icontains=query)
        
    return render(request, 'dicom_app/dashboard.html', {'experiments': experiments})

@login_required
def participant_dashboard(request):
    # Only allow participants or admins
    if not request.user.groups.filter(name='Participante').exists() and not request.user.is_staff:
        return redirect('dashboard')
        
    participants = Participant.objects.all()
    query = request.GET.get('q')
    if query:
        participants = participants.filter(
            Q(subject_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    # Calcular la última participación para cada participante desde DICOM uploads
    participants_with_last_date = []
    for participant in participants:
        latest_dicom = DicomFile.objects.filter(participant=participant).order_by('-upload_date').first()
        participant.last_participation = latest_dicom.upload_date if latest_dicom else None
        participants_with_last_date.append(participant)
        
    return render(request, 'dicom_app/participant_dashboard.html', {
        'participants': participants_with_last_date
    })

class ExperimentCreateView(LoginRequiredMixin, CreateView):
    model = Experiment
    form_class = ExperimentForm
    template_name = 'dicom_app/experiment_form.html'
    success_url = reverse_lazy('experiment_success')
    
    def form_valid(self, form):
        # Django automatically handles ManyToMany relationships when using ModelForm
        # The participants and members will be saved automatically
        response = super().form_valid(form)
        
        # Debug output
        experiment = self.object
        print(f"Experiment created: {experiment.name}")
        print(f"Participants count: {experiment.participants.count()}")
        print(f"Members count: {experiment.members.count()}")
        
        return response




class ExperimentDetailView(LoginRequiredMixin, DetailView):
    model = Experiment
    template_name = 'dicom_app/experiment_detail.html'
    context_object_name = 'experiment'

class ExperimentDeleteView(LoginRequiredMixin, DeleteView):
    model = Experiment
    template_name = 'dicom_app/experiment_confirm_delete.html'
    success_url = reverse_lazy('dashboard')

class ParticipantCreateView(LoginRequiredMixin, CreateView):
    model = Participant
    fields = ['subject_id', 'details', 'experiment']
    template_name = 'dicom_app/participant_form.html'
    
    def get_success_url(self):
        return reverse_lazy('experiment_detail', kwargs={'pk': self.object.experiment.pk})

class ParticipantDetailView(LoginRequiredMixin, DetailView):
    model = Participant
    template_name = 'dicom_app/participant_detail.html'
    context_object_name = 'participant'

class ParticipantListView(LoginRequiredMixin, ListView):
    model = Participant
    template_name = 'dicom_app/participant_list.html'
    context_object_name = 'participants'

# New views for file uploads
@login_required
def upload_consent_note(request, experiment_id, participant_id):
    """Vista para subir nota de consentimiento de un participante"""
    experiment = get_object_or_404(Experiment, pk=experiment_id)
    participant = get_object_or_404(Participant, pk=participant_id)
    
    if request.method == 'POST':
        if 'consent_file' in request.FILES:
            file = request.FILES['consent_file']
            
            # Create ConsentFile record
            consent_file = ConsentFile.objects.create(
                participant=participant,
                experiment=experiment,
                file=file,
                original_filename=file.name,
                file_size=file.size
            )
            
            return render(request, 'dicom_app/upload_success_consent.html', {
                'experiment': experiment,
                'participant': participant
            })
    
    return render(request, 'dicom_app/upload_consent_note.html', {
        'participant': participant,
        'experiment': experiment
    })

@login_required
def view_consent_note(request, participant_id, experiment_id):
    """Vista para visualizar la nota de consentimiento de un participante en un experimento"""
    participant = get_object_or_404(Participant, pk=participant_id)
    experiment = get_object_or_404(Experiment, pk=experiment_id)
    
    # Buscar el ConsentFile más reciente para este participante y experimento
    consent_file = ConsentFile.objects.filter(
        participant=participant,
        experiment=experiment
    ).order_by('-upload_date').first()
    
    # Si no existe el archivo, mostrar mensaje de error
    if not consent_file or not consent_file.file:
        return HttpResponse(
            "Este participante no tiene nota de consentimiento cargada.",
            content_type="text/plain; charset=utf-8"
        )
    
    # Verificar que el archivo existe en el sistema de archivos
    try:
        file_path = consent_file.file.path
        if not os.path.exists(file_path):
            return HttpResponse(
                "El archivo de consentimiento no se encuentra en el servidor.",
                content_type="text/plain; charset=utf-8"
            )
    except Exception as e:
        return HttpResponse(
            f"Error al acceder al archivo: {str(e)}",
            content_type="text/plain; charset=utf-8"
        )
    
    # Detectar el tipo de contenido basado en la extensión del archivo
    file_extension = os.path.splitext(file_path)[1].lower()
    content_type_map = {
        '.pdf': 'application/pdf',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
    }
    content_type = content_type_map.get(file_extension, 'application/pdf')
    
    # Servir el archivo directamente usando FileResponse con context manager
    try:
        file_handle = open(file_path, 'rb')
        response = FileResponse(
            file_handle,
            content_type=content_type
        )
        # Configurar para mostrar inline (en el navegador) en lugar de descargar
        filename = consent_file.original_filename or "consent_note.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except Exception as e:
        return HttpResponse(
            f"Error al servir el archivo: {str(e)}",
            content_type="text/plain; charset=utf-8"
        )


@login_required
def upload_participant_dicom(request, experiment_id, participant_id):
    """Vista para subir archivos DICOM de un participante"""
    experiment = get_object_or_404(Experiment, pk=experiment_id)
    participant = get_object_or_404(Participant, pk=participant_id)
    
    if request.method == 'POST':
        if 'dicom_file' in request.FILES:
            file = request.FILES['dicom_file']
            
            # Usar la función helper para procesar el DICOM
            # Esto incluye: leer, anonimizar, guardar archivo, crear DicomFile y DicomTags
            dicom_instance, dicom_data = process_dicom_file(
                file, 
                participant=participant, 
                experiment=experiment
            )
            
            return render(request, 'dicom_app/upload_success_dicom.html', {
                'experiment': experiment,
                'participant': participant
            })
    
    return render(request, 'dicom_app/upload_dicom.html', {
        'participant': participant,
        'experiment': experiment
    })

@login_required
def upload_success(request, upload_type):
    """Vista de éxito después de subir archivos"""
    messages = {
        'dicom': '¡Archivo DICOM subido exitosamente!',
        'consent': '¡Nota de consentimiento subida exitosamente!'
    }
    message = messages.get(upload_type, '¡Archivo subido exitosamente!')
    
    return render(request, 'dicom_app/upload_success.html', {
        'message': message
    })

@login_required
def participant_experiments(request, participant_id):
    """Vista para mostrar todos los experimentos de un participante"""
    participant = get_object_or_404(Participant, pk=participant_id)
    
    # Obtener todos los experimentos del participante usando la relación ManyToMany
    experiments = participant.experiments.all().order_by('-created_at')
    
    return render(request, 'dicom_app/participant_experiments.html', {
        'participant': participant,
        'experiments': experiments
    })

@login_required
def participant_experiment_dicoms(request, participant_id, experiment_id):
    """
    Muestra todos los archivos DICOM de un participante para un experimento específico
    """
    participant = get_object_or_404(Participant, pk=participant_id)
    experiment = get_object_or_404(Experiment, pk=experiment_id)
    
    # Obtener todos los DICOM files del participante para este experimento
    dicom_files = DicomFile.objects.filter(
        participant=participant,
        experiment=experiment
    ).order_by('-upload_date')
    
    return render(request, 'dicom_app/participant_experiment_dicoms.html', {
        'participant': participant,
        'experiment': experiment,
        'dicom_files': dicom_files
    })

@login_required
def dicom_image_view(request, dicom_id):
    """
    Vista para visualizar la imagen renderizada de un archivo DICOM.
    Retorna directamente la imagen PNG.
    """
    import io
    from PIL import Image
    from django.conf import settings
    
    dicom_file = get_object_or_404(DicomFile, pk=dicom_id)
    
    # 1. Resolución robusta de la ruta del archivo
    possible_paths = []
    
    # Ruta estándar de Django
    try:
        possible_paths.append(dicom_file.file.path)
    except:
        pass
        
    # Ruta corrigiendo posible duplicación de 'media/'
    if dicom_file.file.name.startswith('media/'):
        clean_name = dicom_file.file.name.replace('media/', '', 1)
        possible_paths.append(os.path.join(settings.MEDIA_ROOT, clean_name))
        
    # Ruta asumiendo que el nombre ya es relativo a MEDIA_ROOT
    possible_paths.append(os.path.join(settings.MEDIA_ROOT, dicom_file.file.name))
    
    # Ruta absoluta hardcodeada para debug
    try:
        fname = os.path.basename(dicom_file.file.name)
        manual_path = os.path.join(settings.MEDIA_ROOT, 'dicoms', 'raw', fname)
        possible_paths.append(manual_path)
    except:
        pass
    
    dicom_path = None
    for path in possible_paths:
        if os.path.exists(path):
            dicom_path = path
            break
            
    if not dicom_path:
        return HttpResponse("Archivo DICOM no encontrado en el servidor.", status=404)
    
    try:
        # 2. Leer archivo DICOM
        ds = pydicom.dcmread(dicom_path)
        
        # 3. Verificar PixelData
        if "PixelData" not in ds:
            # Intentar generar una imagen placeholder con texto
            img = Image.new('RGB', (400, 100), color = (255, 255, 255))
            # Aquí podríamos dibujar texto, pero por ahora retornamos error simple
            return HttpResponse("El archivo DICOM no contiene datos de imagen (PixelData).", status=400)
        
        # 4. Procesar imagen
        pixel_array = ds.pixel_array
        
        # Normalizar a 0-255
        pixel_array = pixel_array.astype(float)
        pixel_min = pixel_array.min()
        pixel_max = pixel_array.max()
        
        if pixel_max > pixel_min:
            pixel_array = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255.0)
        
        pixel_array = pixel_array.astype(np.uint8)
        
        # Convertir a PIL
        if len(pixel_array.shape) == 2:
            image = Image.fromarray(pixel_array, mode='L')
        elif len(pixel_array.shape) == 3:
            # Si es RGB, asegurar orden correcto
            if pixel_array.shape[0] == 3: # Canales primero
                pixel_array = np.moveaxis(pixel_array, 0, -1)
            image = Image.fromarray(pixel_array, mode='RGB')
        else:
            return HttpResponse("Formato de dimensiones de imagen no soportado.", status=400)
            
        # 5. Retornar respuesta HTTP con imagen
        response = HttpResponse(content_type="image/png")
        image.save(response, "PNG")
        return response
        
    except Exception as e:
        traceback.print_exc()
        return HttpResponse(f"Error procesando imagen DICOM: {str(e)}", status=500)

@require_POST
def create_participant_ajax(request):
    try:
        data = json.loads(request.body)
        full_name = data.get('full_name', '').strip()
        
        if not full_name:
            return JsonResponse({'status': 'error', 'message': 'El nombre es obligatorio.'}, status=400)
            
        # Split name
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        
        # Generate subject_id
        # We use a simple strategy: SUB- + random 6 chars
        subject_id = f"SUB-{uuid.uuid4().hex[:6].upper()}"
        
        participant = Participant.objects.create(
            subject_id=subject_id,
            first_name=first_name,
            last_name=last_name
        )
        
        return JsonResponse({
            'status': 'success',
            'id': participant.id,
            'value': f"{participant.first_name} {participant.last_name}"
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
def create_member_ajax(request):
    try:
        data = json.loads(request.body)
        full_name = data.get('full_name', '').strip()
        role = data.get('role', '').strip()
        
        if not full_name or not role:
            return JsonResponse({'status': 'error', 'message': 'Nombre y rol son obligatorios.'}, status=400)
            
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ''
        
        member = Member.objects.create(
            first_name=first_name,
            last_name=last_name,
            role=role
        )
        
        return JsonResponse({
            'status': 'success',
            'id': member.id,
            'value': f"{member.first_name} {member.last_name} - {member.role}"
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
def update_experiment_description(request, pk):
    try:
        experiment = get_object_or_404(Experiment, pk=pk)
        data = json.loads(request.body)
        description = data.get('description', '').strip()
        
        experiment.description = description
        experiment.save()
        
        return JsonResponse({
            'status': 'success',
            'description': experiment.description
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




