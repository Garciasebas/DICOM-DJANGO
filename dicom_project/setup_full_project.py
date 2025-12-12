import os
import django
import random
# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from django.contrib.auth.models import User

from dicom_app.models import Experiment, Participant, Member, DicomFile

def create_superuser():
    username = 'admin'
    password = 'admin123'
    email = 'admin@example.com'
    if not User.objects.filter(username=username).exists():
        print(f"Creating superuser {username}...")
        User.objects.create_superuser(username, email, password)
        print("Superuser created.")
    else:
        print("Superuser already exists.")

def create_experiments():
    print("Creating experiments...")
    experiments = []
    for i in range(1, 6):
        name = f"Experiment {i}"
        exp, created = Experiment.objects.get_or_create(
            name=name,
            defaults={
                'description': f'Description for {name}',
                'status': 'Active'
            }
        )
        experiments.append(exp)
    print(f"Created {len(experiments)} experiments.")
    return experiments

def create_participants(experiments):
    print("Creating participants...")
    for i in range(1, 11):
        subject_id = f"SUB-{i:03d}"
        part, created = Participant.objects.get_or_create(
            subject_id=subject_id,
            defaults={
                'first_name': f'Participant',
                'last_name': f'{i}',
                'email': f'participant{i}@example.com',
                'details': f'Details for {subject_id}'
            }
        )
        # Assign random experiments
        part.experiments.add(*random.sample(experiments, k=random.randint(1, 3)))
    print("Created 10 participants.")

def create_members(experiments):
    print("Creating members...")
    roles = [choice[0] for choice in Member.ROLE_CHOICES]
    for i in range(1, 11):
        email = f'member{i}@example.com'
        mem, created = Member.objects.get_or_create(
            email=email,
            defaults={
                'first_name': f'Member',
                'last_name': f'{i}',
                'role': random.choice(roles)
            }
        )
        # Assign random experiments
        mem.experiments.add(*random.sample(experiments, k=random.randint(1, 3)))
    print("Created 10 members.")

if __name__ == "__main__":
    create_superuser()
    exps = create_experiments()
    create_participants(exps)
    create_members(exps)
    print("Setup complete.")
