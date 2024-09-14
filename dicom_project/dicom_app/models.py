from django.db import models

class DicomFile(models.Model):
    patient_name = models.CharField(max_length=255)
    upload_date = models.DateTimeField(auto_now_add=True)

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

    class Meta:
        indexes = [
            models.Index(fields=['tag']),
            models.Index(fields=['dicom_file']),
        ]