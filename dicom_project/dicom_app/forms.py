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

class ConsentNoteForm(forms.Form):
    consent_file = forms.FileField(label='Seleccionar archivo')

    def clean_consent_file(self):
        file = self.cleaned_data.get('consent_file')
        if file:
            if not file.name.endswith(('.pdf', '.doc', '.docx')):
                raise forms.ValidationError('Solo se permiten archivos PDF o Word.')
        return file