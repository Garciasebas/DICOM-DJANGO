import os
import json
import shutil
import tempfile
import pydicom
import dicom2nifti
from pathlib import Path

def normalize_subject_id(index):
    """
    Generates a BIDS-compliant subject ID: sub-01, sub-02, etc.
    """
    return f"sub-{index:02d}"

def detect_modality(ds):
    """
    Detects the modality of a DICOM dataset.
    Returns: (modality_folder, suffix)
    e.g., ('anat', 'T1w'), ('func', 'task-rest_bold'), ('dwi', 'dwi')
    """
    # Default to anat/T1w if unknown
    modality_folder = "anat"
    suffix = "T1w"

    try:
        series_desc = ds.get("SeriesDescription", "").lower()
        image_type = str(ds.get("ImageType", "")).lower()
        modality = ds.get("Modality", "").upper()

        if modality == "MR":
            if "diff" in series_desc or "dwi" in series_desc or "dti" in series_desc:
                modality_folder = "dwi"
                suffix = "dwi"
            elif "bold" in series_desc or "func" in series_desc or "fmri" in series_desc or "rest" in series_desc:
                modality_folder = "func"
                suffix = "task-rest_bold"
            elif "t1" in series_desc or "mprage" in series_desc:
                modality_folder = "anat"
                suffix = "T1w"
            elif "t2" in series_desc:
                modality_folder = "anat"
                suffix = "T2w"
            elif "flair" in series_desc:
                modality_folder = "anat"
                suffix = "FLAIR"
    except Exception as e:
        print(f"Error detecting modality: {e}")

    return modality_folder, suffix

def anonymize_dicom(ds):
    """
    Anonymizes a DICOM dataset in place.
    """
    sensitive_tags = [
        "PatientName", "PatientID", "PatientBirthDate", "PatientSex",
        "InstitutionName", "ReferringPhysicianName", "StudyInstanceUID",
        "SeriesInstanceUID", "AccessionNumber"
    ]

    for tag in sensitive_tags:
        if tag in ds:
            ds.data_element(tag).value = ""

    # Generate new UIDs to ensure anonymity while keeping relationship if needed (though here we just random)
    # For strict BIDS within a session, we might want to keep consistency, but for now random is safer for anonymization.
    ds.StudyInstanceUID = pydicom.uid.generate_uid()
    ds.SeriesInstanceUID = pydicom.uid.generate_uid()
    ds.SOPInstanceUID = pydicom.uid.generate_uid()

    def person_names_callback(ds, elem):
        if elem.VR == "PN":
            elem.value = "anonymous"

    ds.walk(person_names_callback)

    try:
        ds.remove_private_tags()
    except:
        pass

    return ds

def convert_dicom_to_nifti(dicom_path, output_dir, output_basename):
    """
    Converts a single DICOM file (or series) to NIfTI.
    
    Args:
        dicom_path: Path to the original DICOM file.
        output_dir: Pathlib Path to the output directory (e.g., .../sub-01/anat).
        output_basename: Base name for the output file (e.g., sub-01_T1w).
        
    Returns:
        Tuple of (nifti_path, json_path) or (None, None) if failed.
    """
    temp_convert_dir = tempfile.mkdtemp()
    temp_dicom_dir = tempfile.mkdtemp()
    
    generated_nifti = None
    generated_json = None
    
    try:
        # 1. Read and Anonymize
        ds = pydicom.dcmread(dicom_path)
        ds = anonymize_dicom(ds)
        
        # 2. Save to temp directory
        temp_dicom_path = os.path.join(temp_dicom_dir, 'image.dcm')
        ds.save_as(temp_dicom_path)
        
        # 3. Try Convert using dicom2nifti first
        print(f"Converting {dicom_path} to NIfTI...")
        try:
            dicom2nifti.convert_directory(temp_dicom_dir, temp_convert_dir, compression=True, reorient=True)
        except Exception as e:
            print(f"⚠️ dicom2nifti failed: {e}, trying fallback method...")
        
        # 4. Find generated files
        nifti_files = list(Path(temp_convert_dir).glob("*.nii.gz"))
        json_files = list(Path(temp_convert_dir).glob("*.json"))
        
        if nifti_files:
            # Move NIfTI file
            source_nifti = nifti_files[0]
            dest_nifti = output_dir / f"{output_basename}.nii.gz"
            shutil.move(str(source_nifti), str(dest_nifti))
            generated_nifti = dest_nifti
            print(f"✅ Generated NIfTI: {dest_nifti}")
            
            # Handle JSON sidecar
            if json_files:
                source_json = json_files[0]
                dest_json = output_dir / f"{output_basename}.json"
                shutil.move(str(source_json), str(dest_json))
                generated_json = dest_json
            else:
                # Create minimal JSON if missing
                dest_json = output_dir / f"{output_basename}.json"
                with open(dest_json, 'w') as f:
                    json.dump({
                        "Modality": ds.get("Modality", "MR"),
                        "PatientName": "anonymous"
                    }, f, indent=4)
                generated_json = dest_json
            
            print(f"✅ Generated JSON: {generated_json}")
        else:
            # Fallback: Use nibabel for single-slice DICOMs
            print(f"⚠️ dicom2nifti produced no output, using fallback conversion...")
            dest_nifti = output_dir / f"{output_basename}.nii.gz"
            
            # Use the existing convert_single_dicom_to_nifti function
            import numpy as np
            import nibabel as nib
            
            if "PixelData" in ds:
                image = ds.pixel_array
                if image.ndim >= 2:
                    affine = np.eye(4)
                    nii = nib.Nifti1Image(image, affine)
                    nib.save(nii, str(dest_nifti))
                    generated_nifti = dest_nifti
                    print(f"✅ Fallback conversion successful: {dest_nifti}")
                    
                    # Create JSON
                    dest_json = output_dir / f"{output_basename}.json"
                    with open(dest_json, 'w') as f:
                        json.dump({
                            "Modality": ds.get("Modality", "MR"),
                            "PatientName": "anonymous"
                        }, f, indent=4)
                    generated_json = dest_json
                else:
                    print(f"❌ Image has invalid dimensions: {image.ndim}")
            else:
                print(f"❌ DICOM has no PixelData")
            
    except Exception as e:
        print(f"❌ Conversion error for {dicom_path}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(temp_convert_dir, ignore_errors=True)
        shutil.rmtree(temp_dicom_dir, ignore_errors=True)
        
    return generated_nifti, generated_json

def create_dataset_description(base_dir):
    """
    Creates dataset_description.json
    """
    data = {
        "Name": "My Dataset",
        "BIDSVersion": "1.8.0",
        "DatasetType": "raw",
        "Authors": ["DICOM HUB User"],
        "License": "CC-BY-4.0"
    }
    with open(base_dir / "dataset_description.json", 'w') as f:
        json.dump(data, f, indent=4)

def create_participants_tsv(base_dir, participants_data):
    """
    Creates participants.tsv
    participants_data: list of dicts with 'participant_id', 'age', 'sex', 'group'
    """
    tsv_path = base_dir / "participants.tsv"
    with open(tsv_path, 'w') as f:
        f.write("participant_id\tage\tsex\tgroup\n")
        for p in participants_data:
            f.write(f"{p['participant_id']}\t{p.get('age', 'n/a')}\t{p.get('sex', 'n/a')}\t{p.get('group', 'control')}\n")
