from django.urls import path
from .views import upload_dicom

urlpatterns = [
    path('upload/', upload_dicom, name='upload_dicom'),
]