from django.db import models
from django.contrib.auth.models import User

class Experiment(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Active')

    def __str__(self):
        return self.name

class Participant(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    details = models.TextField(blank=True)
    experiments = models.ManyToManyField(Experiment, related_name='participants', blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Member(models.Model):
    ROLE_CHOICES = [
        ('Líder Científico/a', 'Líder Científico/a'),
        ('Co-investigador/a', 'Co-investigador/a'),
        ('Investigador/a Posdoctoral', 'Investigador/a Posdoctoral'),
        ('Coordinador/a de Investigación', 'Coordinador/a de Investigación'),
        ('Coordinador/a Clínico', 'Coordinador/a Clínico'),
        ('Neurólogo/a', 'Neurólogo/a'),
        ('Técnico/a en Neuroimagen', 'Técnico/a en Neuroimagen'),
        ('Ingeniero/a Biomédico/a', 'Ingeniero/a Biomédico/a'),
        ('Especialista en Procesamiento de Imágenes', 'Especialista en Procesamiento de Imágenes'),
        ('Asistente de Investigación', 'Asistente de Investigación'),
        ('Bioestadístico/a o Científico/a de Datos', 'Bioestadístico/a o Científico/a de Datos'),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=ROLE_CHOICES)
    email = models.EmailField(blank=True)
    experiments = models.ManyToManyField(Experiment, related_name='members', blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.role}"

class TeamMember(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=100)
    experiments = models.ManyToManyField(Experiment, related_name='team_members')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class ConsentFile(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='consent_files')
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='consent_files')
    file = models.FileField(upload_to='consent_notes/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consent for {self.participant} - {self.experiment} ({self.upload_date.strftime('%Y-%m-%d')})"

class DicomFile(models.Model):
    id = models.AutoField(primary_key=True)
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='dicom_files')
    experiment = models.ForeignKey(Experiment, on_delete=models.SET_NULL, null=True, blank=True, related_name='dicom_files')
    patient_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='dicoms/raw/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    is_anonymized = models.BooleanField(default=False)

    def __str__(self):
        return f"DICOM File for {self.patient_name} uploaded on {self.upload_date}"

class DicomTag(models.Model):
    dicom_file = models.ForeignKey(DicomFile, on_delete=models.CASCADE, related_name='tags')
    tag = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    vr = models.CharField(max_length=10)  # Value Representation
    value = models.TextField()

    def __str__(self):
        return f"{self.tag}: {self.description}"