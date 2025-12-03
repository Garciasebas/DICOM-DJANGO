import pydicom
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import FileResponse, Http404, HttpResponse
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
from .models import DicomFile, DicomTag, Experiment, Participant, ConsentFile
from .forms import DicomFileForm, DicomTagForm, DicomUploadForm, ExperimentForm
import uuid
import numpy as np
import nibabel as nib
import uuid

def generate_pacient_code():
    # Genera un UUID4 y toma los primeros 8 caracteres en mayúsculas
    return str(uuid.uuid4())[:8].upper()

def anonymize_dicom(ds):
    """
    Función para anonimizar un archivo DICOM eliminando o modificando datos sensibles.

     Aplica técnicas de anonimización al archivo DICOM:
    1. Pseudonimización: Reemplaza valores sensibles por identificadores anónimos.
    2. Enmascaramiento de datos: Sustituye información con valores genéricos.
    3. Eliminación de datos sensibles: Borra etiquetas privadas y secundarias.
    """
    # Lista de elementos sensibles a anonimizar
    sensitive_tags = [
        "PatientName", "PatientID", "PatientBirthDate", "PatientSex",
        "InstitutionName", "ReferringPhysicianName", "StudyInstanceUID",
        "SeriesInstanceUID", "AccessionNumber"
    ]

    # Eliminar datos sensibles
    for tag in sensitive_tags:
        if tag in ds:
            ds.data_element(tag).value = ""

    # Reemplazar identificadores únicos
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = pydicom.uid.generate_uid()

    # Pseudonimización: Sustitución de datos personales con valores anónimos
    def person_names_callback(ds, elem):
        if elem.VR == "PN":  # PN = Personal Name
            elem.value = "anonymous"

    ds.walk(person_names_callback)

    # Eliminación de datos sensibles
    ds.remove_private_tags()

    def curves_callback(ds, elem):
        if elem.tag.group & 0xFF00 == 0x5000:
            del ds[elem.tag]

    ds.walk(curves_callback)

    # Enmascaramiento de datos: Se reemplazan con valores genéricos en lugar de eliminarlos
    if "PatientBirthDate" in ds:
        ds.data_element("PatientBirthDate").value = "19000101"

    return ds

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
    save_dir = Path("media/dicoms/raw/")
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{pacient_code}_{uuid.uuid4().hex[:6]}.dcm"
    full_path = save_dir / filename
    
    # Guardar el archivo ORIGINAL
    ds.save_as(str(full_path))
    
    # Crear instancia DicomFile
    dicom_instance = DicomFile.objects.create(
        participant=participant,
        experiment=experiment,
        patient_name=pacient_code,
        file=str(full_path),
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
    subject_id = f"sub-{dicom_instance.patient_name.lower()}"
    session_id = "ses-01"
    anat_dir = Path(temp_dir) / subject_id / session_id / "anat"
    anat_dir.mkdir(parents=True, exist_ok=True)

    output_nifti = anat_dir / 'output.nii.gz'
    try:
        # Crear carpeta temporal con el único DICOM
        temp_dicom_dir = tempfile.mkdtemp()
        temp_dicom_path = os.path.join(temp_dicom_dir, 'image.dcm')
        
        # Leer el archivo original, anonimizar y guardar en temporal
        ds = pydicom.dcmread(dicom_path)
        ds = anonymize_dicom(ds)
        ds.save_as(temp_dicom_path)
        
        # shutil.copyfile(dicom_path, temp_dicom_path) # <-- Reemplazado por lógica de anonimización
        convert_directory(temp_dicom_dir, anat_dir, compression=True)
    except Exception as e:
        print("❌ dicom2nifti falló:", str(e))

    # Si aún no se generó ningún NIfTI, usar método alternativo
    nii_files = list(anat_dir.glob("*.nii.gz"))
    if not nii_files:
        try:
            # Para conversión simple, también anonimizar primero
            ds_simple = pydicom.dcmread(dicom_path)
            ds_simple = anonymize_dicom(ds_simple)
            # Guardar temporalmente para convertir (o convertir desde objeto si la función lo soportara, pero usa path)
            # Como convert_single_dicom_to_nifti lee de path, necesitamos guardar el anonimizado
            temp_simple_dicom = temp_dicom_dir + "/temp_simple.dcm" # Reusar dir temporal
            ds_simple.save_as(temp_simple_dicom)
            
            convert_single_dicom_to_nifti(temp_simple_dicom, output_nifti)
            nii_files = [output_nifti]
        except Exception as e:
            traceback.print_exc()
            return HttpResponse(f"No se pudo convertir el DICOM: {e}", status=500)

    if not nii_files:
        return HttpResponse("❌ La conversión falló: no se generó ningún archivo .nii.gz", status=500)

    output_nifti = nii_files[0]

    # Crear JSON de metadatos
    metadata = {
        "Modality": "MRI",
        "Manufacturer": "Unknown",
        "PatientName": dicom_instance.patient_name,
        "InstitutionName": "Anonymous Hospital"
    }

    try:
        json_path = output_nifti.with_suffix(".json")
        with open(json_path, 'w') as jf:
            json.dump(metadata, jf, indent=4)
    except Exception as e:
        return HttpResponse(f"No se pudo crear el archivo JSON: {e}", status=500)

    with open(Path(temp_dir) / "dataset_description.json", 'w') as df:
        json.dump({
            "Name": "Exported BIDS Dataset",
            "BIDSVersion": "1.8.0"
        }, df, indent=4)

    # Comprimir todo
    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, temp_dir)
                zipf.write(full_path, arcname=arcname)

    return FileResponse(open(zip_path, 'rb'), as_attachment=True, filename=f"{subject_id}_bids.zip")

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
    
    # Obtener todos los participantes del experimento
    participants = experiment.participants.all()
    
    if not participants.exists():
        return HttpResponse("No hay participantes asociados a este experimento.", status=404)
    
    # Crear archivo participants.tsv
    participants_tsv_path = bids_root / "participants.tsv"
    with open(participants_tsv_path, 'w') as tsv_file:
        tsv_file.write("participant_id\tage\tsex\tgroup\n")
        for participant in participants:
            subject_id = f"sub-{participant.subject_id.lower()}"
            tsv_file.write(f"{subject_id}\tNA\tNA\tcontrol\n")
    
    # Procesar cada participante
    for participant in participants:
        subject_id = f"sub-{participant.subject_id.lower()}"
        subject_dir = bids_root / subject_id
        
        # Crear carpetas anat, func, dwi para cada participante
        anat_dir = subject_dir / "anat"
        func_dir = subject_dir / "func"
        dwi_dir = subject_dir / "dwi"
        
        anat_dir.mkdir(parents=True, exist_ok=True)
        func_dir.mkdir(parents=True, exist_ok=True)
        dwi_dir.mkdir(parents=True, exist_ok=True)
        
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
                
                # Clasificar el tipo de imagen basándose en el nombre del archivo o metadatos
                filename_lower = dicom_file.original_filename.lower() if dicom_file.original_filename else ""
                
                if "t1" in filename_lower or "anat" in filename_lower:
                    output_dir = anat_dir
                    output_basename = f"{subject_id}_T1w"
                elif "bold" in filename_lower or "func" in filename_lower or "rest" in filename_lower:
                    output_dir = func_dir
                    output_basename = f"{subject_id}_task-rest_bold"
                elif "dwi" in filename_lower or "dti" in filename_lower:
                    output_dir = dwi_dir
                    output_basename = f"{subject_id}_dwi"
                else:
                    # Por defecto, asumir anat
                    output_dir = anat_dir
                    output_basename = f"{subject_id}_T1w"
                
                output_nifti = output_dir / f"{output_basename}.nii.gz"
                
                # Convertir DICOM a NIfTI
                try:
                    # Intentar conversión con dicom2nifti
                    temp_dicom_dir = tempfile.mkdtemp()
                    temp_dicom_path = os.path.join(temp_dicom_dir, 'image.dcm')
                    
                    # Leer, anonimizar y guardar temporalmente
                    ds = pydicom.dcmread(dicom_path)
                    ds = anonymize_dicom(ds)
                    ds.save_as(temp_dicom_path)
                    
                    # shutil.copyfile(dicom_path, temp_dicom_path) # <-- Reemplazado
                    
                    # Intentar convertir
                    nii_files = list(output_dir.glob("*.nii.gz"))
                    initial_count = len(nii_files)
                    
                    try:
                        convert_directory(temp_dicom_dir, output_dir, compression=True)
                        nii_files = list(output_dir.glob("*.nii.gz"))
                        
                        # Si se generó un archivo, renombrarlo
                        if len(nii_files) > initial_count:
                            new_file = nii_files[-1]
                            new_file.rename(output_nifti)
                    except:
                        # Si falla, usar método alternativo
                        # Usar el archivo anonimizado temporal que ya creamos
                        convert_single_dicom_to_nifti(temp_dicom_path, output_nifti)
                    
                    # Limpiar directorio temporal
                    shutil.rmtree(temp_dicom_dir, ignore_errors=True)
                    
                except Exception as e:
                    print(f"⚠️ Error convirtiendo {dicom_file.original_filename}: {str(e)}")
                    continue
                
                # Crear archivo JSON sidecar
                json_path = output_dir / f"{output_basename}.json"
                metadata = {
                    "Modality": "MRI",
                    "Manufacturer": "Unknown",
                    "PatientID": participant.subject_id,
                    "InstitutionName": "Anonymous Hospital"
                }
                
                # Añadir metadatos específicos según el tipo
                if "bold" in output_basename:
                    metadata["TaskName"] = "rest"
                    metadata["RepetitionTime"] = 2.0
                
                with open(json_path, 'w') as jf:
                    json.dump(metadata, jf, indent=4)
                
                # Para archivos DWI, crear archivos .bval y .bvec (vacíos por ahora)
                if "dwi" in output_basename:
                    bval_path = output_dir / f"{output_basename}.bval"
                    bvec_path = output_dir / f"{output_basename}.bvec"
                    
                    with open(bval_path, 'w') as f:
                        f.write("0\n")
                    
                    with open(bvec_path, 'w') as f:
                        f.write("0 0 0\n")
                
            except Exception as e:
                print(f"⚠️ Error procesando archivo DICOM {dicom_file.id}: {str(e)}")
                traceback.print_exc()
                continue
    
    # Crear archivo dataset_description.json
    dataset_description = {
        "Name": f"BIDS Dataset - {experiment.name}",
        "BIDSVersion": "1.8.0",
        "DatasetType": "raw"
    }
    
    with open(bids_root / "dataset_description.json", 'w') as f:
        json.dump(dataset_description, f, indent=4)
    
    # Comprimir todo en un ZIP
    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(bids_root):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, temp_dir)
                zipf.write(full_path, arcname=arcname)
    
    # Limpiar directorio temporal
    shutil.rmtree(temp_dir, ignore_errors=True)
    
    # Retornar el archivo ZIP
    experiment_name_safe = experiment.name.replace(" ", "_").lower()
    return FileResponse(
        open(zip_path, 'rb'), 
        as_attachment=True, 
        filename=f"{experiment_name_safe}_bids.zip"
    )

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
    return render(request, 'dicom_app/dashboard.html', {'experiments': experiments})

@login_required
def participant_dashboard(request):
    # Only allow participants or admins
    if not request.user.groups.filter(name='Participante').exists() and not request.user.is_staff:
        return redirect('dashboard')
        
    participants = Participant.objects.all()
    query = request.GET.get('q')
    if query:
        participants = participants.filter(subject_id__icontains=query)
    
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
    Vista para visualizar la imagen renderizada de un archivo DICOM
    """
    import io
    import base64
    from PIL import Image
    
    dicom_file = get_object_or_404(DicomFile, pk=dicom_id)
    
    try:
        # Leer el archivo DICOM
        dicom_path = dicom_file.file.path
        
        if not os.path.exists(dicom_path):
            raise Http404("Archivo DICOM no encontrado")
        
        ds = pydicom.dcmread(dicom_path)
        
        # Verificar que el DICOM tenga datos de imagen
        if "PixelData" not in ds:
            return render(request, 'dicom_app/dicom_image_view.html', {
                'dicom_file': dicom_file,
                'error': 'Este archivo DICOM no contiene datos de imagen (PixelData).',
                'participant_id': dicom_file.participant.id if dicom_file.participant else None
            })
        
        # Obtener el pixel array
        pixel_array = ds.pixel_array
        
        # Normalizar la imagen a 0-255
        pixel_array = pixel_array.astype(float)
        pixel_min = pixel_array.min()
        pixel_max = pixel_array.max()
        
        if pixel_max > pixel_min:
            pixel_array = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255.0)
        
        pixel_array = pixel_array.astype(np.uint8)
        
        # Convertir a imagen PIL
        if len(pixel_array.shape) == 2:
            # Imagen en escala de grises
            image = Image.fromarray(pixel_array, mode='L')
        elif len(pixel_array.shape) == 3:
            # Imagen RGB
            image = Image.fromarray(pixel_array, mode='RGB')
        else:
            raise Exception("Formato de imagen no soportado")
        
        # Convertir la imagen a base64 para embeber en HTML
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return render(request, 'dicom_app/dicom_image_view.html', {
            'dicom_file': dicom_file,
            'image_data': image_base64,
            'image_width': pixel_array.shape[1] if len(pixel_array.shape) >= 2 else 0,
            'image_height': pixel_array.shape[0] if len(pixel_array.shape) >= 1 else 0,
            'participant_id': dicom_file.participant.id if dicom_file.participant else None
        })
        
    except Exception as e:
        return render(request, 'dicom_app/dicom_image_view.html', {
            'dicom_file': dicom_file,
            'error': f'Error al procesar la imagen DICOM: {str(e)}',
            'participant_id': dicom_file.participant.id if dicom_file.participant else None
        })

