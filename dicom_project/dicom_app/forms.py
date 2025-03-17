from django import forms
from .models import DicomFile, DicomTag

class DicomUploadForm(forms.Form):
    dicom_file = forms.FileField()

class DicomFileForm(forms.ModelForm):
    class Meta:
        model = DicomFile
        fields = ['patient_name']

class DicomTagForm(forms.ModelForm):
    class Meta:
        model = DicomTag
        fields = ['tag', 'description', 'vr', 'value']