from django.contrib.auth.models import User
from dicom_app.models import Experiment, Participant

# Obtener o crear usuario admin
user, created = User.objects.get_or_create(username='admin')
if created:
    user.set_password('admin')
    user.is_superuser = True
    user.is_staff = True
    user.save()
    print("✅ Usuario admin creado")
else:
    print("ℹ️  Usuario admin ya existe")

# Obtener o crear experimento de prueba
experiment, created = Experiment.objects.get_or_create(
    name="Experimento de Prueba",
    defaults={
        'description': 'Este es un experimento de prueba para verificar la funcionalidad de subida de archivos DICOM y notas de consentimiento.',
        'status': 'Active'
    }
)

if created:
    print(f"✅ Experimento creado: {experiment.name}")
else:
    print(f"ℹ️  Experimento ya existe: {experiment.name}")

# Crear participantes de prueba
participants_data = [
    {'subject_id': 'SUB-001', 'details': 'Participante de prueba 1'},
    {'subject_id': 'SUB-002', 'details': 'Participante de prueba 2'},
    {'subject_id': 'SUB-003', 'details': 'Participante de prueba 3'},
]

for p_data in participants_data:
    participant, created = Participant.objects.get_or_create(
        subject_id=p_data['subject_id'],
        experiment=experiment,
        defaults={'details': p_data['details']}
    )
    if created:
        print(f"✅ Participante creado: {participant.subject_id}")
    else:
        print(f"ℹ️  Participante ya existe: {participant.subject_id}")

print("\n🎉 Datos de prueba configurados correctamente!")
print(f"📊 Experimento: {experiment.name} (ID: {experiment.id})")
print(f"👥 Participantes: {experiment.participants.count()}")
