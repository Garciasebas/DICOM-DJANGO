import pydicom
from django.shortcuts import render
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
import os
import shutil
import tempfile
from pathlib import Path
import dicom2nifti
import json
import zipfile
from .models import DicomFile, DicomTag
from .forms import DicomFileForm, DicomTagForm, DicomUploadForm
import tempfile
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


def upload_dicom(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dicom_file = request.FILES['dicom_file']
            ds = pydicom.dcmread(dicom_file)

            # Aplicar anonimización antes de guardar los datos
            ds = anonymize_dicom(ds)

            # Generar nombre único y ruta permanente
            pacient_code = generate_pacient_code()
            save_dir = Path("media/dicoms/")
            save_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{pacient_code}_{uuid.uuid4().hex[:6]}.dcm"
            full_path = save_dir / filename

            # Guardar el archivo anonimizado
            ds.save_as(str(full_path))

            # Crear instancia DicomFile con ruta al archivo
            dicom_instance = DicomFile.objects.create(
                patient_name=pacient_code,
                file=str(full_path)
            )

            dicom_data = []  # Para almacenar los datos del DICOM que vamos a mostrar

            # Guardar los tags anonimizados en la base de datos
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

            # Pasar los datos DICOM anonimizados a la plantilla de éxito
            return render(request, 'success.html', {'dicom_data': dicom_data, 'patient_name': "Anonymous"})

    else:
        form = DicomUploadForm()

    return render(request, 'upload.html', {'form': form})

class DicomFileListView(ListView):
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

class DicomFileDetailView(DetailView):
    model = DicomFile
    template_name = 'dicomfile_detail.html'  # Plantilla que mostrarás
    context_object_name = 'dicom_file'  # Nombre del contexto en la plantilla

class DicomFileCreateView(CreateView):
    model = DicomFile
    form_class = DicomFileForm
    template_name = 'dicomfile_form.html'
    success_url = reverse_lazy('dicomfile_list')

class DicomFileUpdateView(UpdateView):
    model = DicomFile
    form_class = DicomFileForm
    template_name = 'dicomfile_form.html'
    success_url = reverse_lazy('dicomfile_list')

class DicomFileDeleteView(DeleteView):
    model = DicomFile
    template_name = 'dicomfile_confirm_delete.html'
    success_url = reverse_lazy('dicomfile_list')

def export_dicom_to_bids(request, pk):
    dicom_instance = get_object_or_404(DicomFile, pk=pk)
    dicom_path = dicom_instance.file

    if not os.path.exists(dicom_path):
        raise Http404("Archivo DICOM no encontrado")

    # Crear estructura temporal BIDS
    temp_dir = tempfile.mkdtemp()
    subject_id = f"sub-{dicom_instance.patient_name.lower()}"
    session_id = "ses-01"
    anat_dir = Path(temp_dir) / subject_id / session_id / "anat"
    anat_dir.mkdir(parents=True, exist_ok=True)

    # Convertir a NIfTI
    try:
        dicom2nifti.convert_directory(os.path.dirname(dicom_path), anat_dir, compression=True)
    except Exception as e:
        raise Exception(f"Error al convertir a NIfTI: {e}")

    # Crear JSON de metadatos
    metadata = {
        "Modality": "MRI",
        "Manufacturer": "Unknown",
        "PatientName": dicom_instance.patient_name,
        "InstitutionName": "Anonymous Hospital"
    }
    json_path = list(anat_dir.glob("*.nii.gz"))[0].with_suffix(".json")
    with open(json_path, 'w') as jf:
        json.dump(metadata, jf, indent=4)

    # dataset_description.json
    with open(Path(temp_dir) / "dataset_description.json", 'w') as df:
        json.dump({
            "Name": "Exported BIDS Dataset",
            "BIDSVersion": "1.8.0"
        }, df, indent=4)

    # Comprimir en .zip
    zip_path = tempfile.NamedTemporaryFile(delete=False, suffix=".zip").name
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, temp_dir)
                zipf.write(full_path, arcname=arcname)

    # Descargar como FileResponse
    response = FileResponse(open(zip_path, 'rb'), as_attachment=True, filename=f"{subject_id}_bids.zip")
    return response

def zip_bids_folder(bids_dir):
    zip_path = bids_dir + '.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(bids_dir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=os.path.relpath(file_path, bids_dir))
    return zip_path