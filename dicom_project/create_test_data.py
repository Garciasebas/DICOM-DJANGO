import os
import django
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from dicom_app.models import Participant, DicomFile, DicomTag

print("Creating test data...")

# Get a participant
participant = Participant.objects.first()
if not participant:
    print("No participant found. Please create one first.")
    exit()

print(f"Using participant: {participant}")

# Create DicomFile
dicom_file = DicomFile.objects.create(
    participant=participant,
    patient_name="TEST_PATIENT_001",
    file="path/to/test_file.dcm",
    upload_date=timezone.now(),
    is_anonymized=False
)
print(f"Created DicomFile: {dicom_file} (ID: {dicom_file.id})")

# Create Tags
tags_data = [
    ("0008,0005", "Specific Character Set", "CS", "ISO_IR 100"),
    ("0008,0008", "Image Type", "CS", "['ORIGINAL', 'PRIMARY', 'M', 'ND', 'NORM']"),
    ("0008,0012", "Instance Creation Date", "DA", "20161101"),
    ("0008,0013", "Instance Creation Time", "TM", "120000"),
    ("0010,0010", "Patient Name", "PN", "TEST_PATIENT_001"),
    ("0010,0020", "Patient ID", "LO", "123456"),
]

for tag, desc, vr, val in tags_data:
    DicomTag.objects.create(
        dicom_file=dicom_file,
        tag=tag,
        description=desc,
        vr=vr,
        value=val
    )

print("Created DicomTags.")
print("Done.")
