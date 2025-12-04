import os
import sys
import django
import shutil
import tempfile
from pathlib import Path

# Setup Django environment
sys.path.append(r'c:\Users\home\Documents\RepositoryAntigravity\DICOM-DJANGO\dicom_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from dicom_app.models import DicomFile, Experiment
from dicom_app.bids_utils import detect_modality, convert_dicom_to_nifti
import pydicom

def diagnose():
    print("--- Starting Diagnostics ---")
    
    # Check Experiments
    experiments = Experiment.objects.all()
    print(f"Found {experiments.count()} experiments.")
    
    if experiments.count() == 0:
        print("⚠️ No experiments found. Cannot test export.")
        return

    # Check DicomFiles
    dicom_files = DicomFile.objects.all()
    print(f"Found {dicom_files.count()} DICOM files.")
    
    if dicom_files.count() == 0:
        print("⚠️ No DICOM files found.")
        return

    # Pick a file to test
    target_file = dicom_files.first()
    print(f"Testing with DicomFile ID: {target_file.id}")
    print(f"File path: {target_file.file.path}")
    
    if not os.path.exists(target_file.file.path):
        print("❌ File does not exist on disk!")
        return
    else:
        print("✅ File exists on disk.")

    # Test Modality Detection
    try:
        ds = pydicom.dcmread(target_file.file.path)
        print("DICOM Header Sample:")
        print(f"  Modality: {ds.get('Modality', 'N/A')}")
        print(f"  SeriesDescription: {ds.get('SeriesDescription', 'N/A')}")
        print(f"  ImageType: {ds.get('ImageType', 'N/A')}")
        
        modality, suffix = detect_modality(ds)
        print(f"Detected Modality: {modality}, Suffix: {suffix}")
    except Exception as e:
        print(f"❌ Modality detection failed: {e}")

    # Test Conversion
    print("\nTesting Conversion...")
    temp_dir = Path(tempfile.mkdtemp())
    output_dir = temp_dir / "test_output"
    output_dir.mkdir()
    
    try:
        nifti, json_sidecar = convert_dicom_to_nifti(target_file.file.path, output_dir, "test_conversion")
        
        if nifti:
            print(f"✅ Conversion successful: {nifti}")
        else:
            print("❌ Conversion returned None.")
            
    except Exception as e:
        print(f"❌ Conversion crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    diagnose()
