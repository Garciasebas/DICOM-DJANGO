import pydicom
from django.shortcuts import render
from .forms import DicomUploadForm
from .models import DicomFile, DicomTag
import tempfile
import uuid

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

            # Guardar el archivo anonimizado temporalmente
            temp_path = tempfile.NamedTemporaryFile(delete=False).name
            ds.save_as(temp_path)

            # Crear una instancia de DicomFile para asociar los tags anonimizados
            dicom_instance = DicomFile.objects.create(
                patient_name="Anonymous"  # Nombre anonimizado
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
