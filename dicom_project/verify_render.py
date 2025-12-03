import os
import django
import sys

# Add project root to path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from django.template.loader import render_to_string
from dicom_app.models import DicomFile

try:
    df = DicomFile.objects.get(id=5)
    context = {'dicom_file': df, 'participant_id': df.participant.id if df.participant else None}
    rendered = render_to_string('dicom_app/dicomfile_detail.html', context)
    
    with open('render_output.html', 'w', encoding='utf-8') as f:
        f.write(rendered)
    print("Rendered successfully to render_output.html")
except Exception as e:
    print(f"Error: {e}")
