from django.db import migrations

def update_roles(apps, schema_editor):
    Member = apps.get_model('dicom_app', 'Member')
    
    role_mapping = {
        'Investigador Principal': 'Líder Científico/a',
        'Coordinadora de Investigación': 'Coordinador/a de Investigación',
        'Técnico Radiólogo': 'Técnico/a en Neuroimagen',
        'Médica Especialista': 'Neurólogo/a',
        'Analista de Datos': 'Bioestadístico/a o Científico/a de Datos',
        'Enfermera Investigadora': 'Co-investigador/a',
        'Bioestadístico': 'Bioestadístico/a o Científico/a de Datos',
        'Asistente de Investigación': 'Asistente de Investigación',
        'Técnico en Informática': 'Ingeniero/a Biomédico/a',
        'Coordinadora Administrativa': 'Coordinador/a Clínico',
    }
    
    default_role = 'Asistente de Investigación'
    
    for member in Member.objects.all():
        if member.role in role_mapping:
            member.role = role_mapping[member.role]
        elif member.role not in role_mapping.values():
            # If the role is not in the mapping AND not already a valid role, use default
            member.role = default_role
        member.save()

class Migration(migrations.Migration):

    dependencies = [
        ('dicom_app', '0011_fix_dicom_file_paths'),
    ]

    operations = [
        migrations.RunPython(update_roles),
    ]
