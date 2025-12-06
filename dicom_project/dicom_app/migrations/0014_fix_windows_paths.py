from django.db import migrations

def fix_windows_paths(apps, schema_editor):
    DicomFile = apps.get_model('dicom_app', 'DicomFile')
    
    for dicom_file in DicomFile.objects.all():
        name = dicom_file.file.name
        changed = False
        
        # Normalize slashes to forward slashes for consistent checking
        name = name.replace('\\', '/')
        
        if name.startswith('media/'):
            name = name.replace('media/', '', 1)
            changed = True
            
        if changed:
            dicom_file.file.name = name
            dicom_file.save(update_fields=['file'])
            print(f"Fixed path for DicomFile {dicom_file.id}: {name}")

class Migration(migrations.Migration):

    dependencies = [
        ('dicom_app', '0013_alter_member_role'),
    ]

    operations = [
        migrations.RunPython(fix_windows_paths),
    ]
