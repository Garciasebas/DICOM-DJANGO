import os
from django.conf import settings
from dicom_app.models import ConsentFile, DicomFile

print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")

print("\n--- Checking ConsentFiles ---")
for cf in ConsentFile.objects.all():
    exists = os.path.exists(cf.file.path)
    print(f"ID: {cf.id}")
    print(f"  Field: {cf.file.name}")
    print(f"  Path: {cf.file.path}")
    print(f"  Exists: {exists}")
    if not exists:
        # Try to find where it might be
        potential_path = os.path.join(settings.MEDIA_ROOT, cf.file.name)
        print(f"  Check manual join: {potential_path} -> {os.path.exists(potential_path)}")

print("\n--- Checking DicomFiles ---")
for df in DicomFile.objects.all():
    exists = os.path.exists(df.file.path)
    print(f"ID: {df.id}")
    print(f"  Field: {df.file.name}")
    print(f"  Path: {df.file.path}")
    print(f"  Exists: {exists}")
    if not exists:
        # Check if stripping 'media/' helps
        if df.file.name.startswith('media/'):
            stripped = df.file.name.replace('media/', '', 1)
            fixed_path = os.path.join(settings.MEDIA_ROOT, stripped)
            print(f"  Stripped 'media/': {fixed_path} -> {os.path.exists(fixed_path)}")
