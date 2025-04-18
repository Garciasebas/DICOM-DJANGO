from django.urls import path
from .views import (
    DicomFileListView,
    DicomFileDetailView,
    DicomFileCreateView,
    DicomFileUpdateView,
    DicomFileDeleteView,
    upload_dicom,
    export_dicom_to_bids
)
urlpatterns = [
    path('', DicomFileListView.as_view(), name='dicomfile_list'),
    path('<int:pk>/', DicomFileDetailView.as_view(), name='dicomfile_detail'),
    path('dicomfile/new/', DicomFileCreateView.as_view(), name='dicomfile_create'),
    path('dicomfile/<int:pk>/edit/', DicomFileUpdateView.as_view(), name='dicomfile_edit'),
    path('dicomfile/<int:pk>/delete/', DicomFileDeleteView.as_view(), name='dicomfile_delete'),
    path('upload/', upload_dicom, name='upload_dicom'),
    path('search/', DicomFileListView.as_view(), name='dicom_search'),
    path('dicom/<int:pk>/export_bids/', export_dicom_to_bids, name='export_dicom_to_bids'),
]