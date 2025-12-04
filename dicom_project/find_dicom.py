from dicom_app.models import DicomFile
import os
from django.conf import settings

print(f"MEDIA_ROOT: {settings.MEDIA_ROOT}")
for df in DicomFile.objects.all():
    paths = [
        df.file.path,
        os.path.join(settings.MEDIA_ROOT, df.file.name.replace('media/', '', 1)) if df.file.name.startswith('media/') else None,
        os.path.join(settings.MEDIA_ROOT, df.file.name),
        os.path.join(settings.MEDIA_ROOT, 'dicoms', 'raw', os.path.basename(df.file.name))
    ]
    found = False
    for p in paths:
        if p and os.path.exists(p):
            print(f"FOUND ID: {df.id} at {p}")
            found = True
            break
    if not found:
        print(f"MISSING ID: {df.id}")
