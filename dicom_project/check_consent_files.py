from dicom_app.models import ConsentFile
import os

# Check for consent file for participant 1, experiment 1
cf = ConsentFile.objects.filter(participant_id=1, experiment_id=1).first()

if cf:
    print(f"Found ConsentFile: {cf}")
    print(f"File field: {cf.file}")
    print(f"File name: {cf.file.name}")
    try:
        file_path = cf.file.path
        print(f"File path: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
    except Exception as e:
        print(f"Error getting path: {e}")
else:
    print("No ConsentFile found for participant 1, experiment 1")

# List all consent files
print("\nAll consent files:")
for consent in ConsentFile.objects.all():
    print(f"  - {consent}")
