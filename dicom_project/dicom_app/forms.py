from django import forms
from .models import DicomFile, DicomTag, Experiment, Participant, Member

class ExperimentForm(forms.ModelForm):
    participants = forms.ModelMultipleChoiceField(
        queryset=Participant.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select-multiple'}),
        required=False,
        label='Participantes'
    )
    members = forms.ModelMultipleChoiceField(
        queryset=Member.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select-multiple'}),
        required=False,
        label='Miembros del Equipo'
    )
    
    class Meta:
        model = Experiment
        fields = ['name', 'description']
        labels = {
            'name': 'Nombre del Experimento',
            'description': 'Descripción',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del Experimento'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Descripción', 'rows': 4, 'maxlength': '300'}),
        }
    
    def save(self, commit=True):
        experiment = super().save(commit=commit)
        if commit:
            experiment.participants.set(self.cleaned_data['participants'])
            experiment.members.set(self.cleaned_data['members'])
        return experiment

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