import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from dicom_app.models import DicomFile

try:
    dicom_files = DicomFile.objects.all()
    print(f"Total DicomFiles: {dicom_files.count()}")
    
    for df in dicom_files:
        print(f"ID: {df.pk} | Path: {df.file.name}")
        full_path = os.path.join(settings.MEDIA_ROOT, df.file.name)
        print(f"  Exists? {os.path.exists(full_path)}")
        
except Exception as e:
    print(f"Error: {e}")
