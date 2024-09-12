import pydicom
from django.shortcuts import render, redirect
from .forms import DicomUploadForm
from .models import DicomFile, DicomTag

def upload_dicom(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dicom_file = request.FILES['dicom_file']
            ds = pydicom.dcmread(dicom_file)

            # Supongamos que queremos asociar los datos del archivo DICOM con el nombre del paciente
            patient_name = ds.PatientName if 'PatientName' in ds else 'Unknown Patient'
            
            # Crear una instancia de DicomFile para asociar todos los tags
            dicom_instance = DicomFile.objects.create(patient_name=patient_name)

            dicom_data = []  # Para almacenar los datos del DICOM que vamos a mostrar

            # Recorrer todos los elementos DICOM y guardarlos en la base de datos
            for element in ds:
                dicom_entry = DicomTag.objects.create(
                    dicom_file=dicom_instance,  # Asocia el tag con el archivo DICOM
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

            # Pasar los datos DICOM a la plantilla de éxito
            return render(request, 'success.html', {'dicom_data': dicom_data, 'patient_name': patient_name})
    else:
        form = DicomUploadForm()
    return render(request, 'upload.html', {'form': form})