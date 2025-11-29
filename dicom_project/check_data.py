import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from dicom_app.models import Participant, Experiment, DicomFile

print("Checking relationships...")

participants = Participant.objects.all()
for p in participants:
    print(f"Participant: {p} (ID: {p.id})")
    print(f"  Experiment: {p.experiment.name} (ID: {p.experiment.id})")
    dicom_files = p.dicom_files.all()
    print(f"  DicomFiles count: {dicom_files.count()}")
    for df in dicom_files:
        print(f"    - File: {df.file} (ID: {df.id})")
