from django.urls import path
from .views import (
    DicomFileListView,
    DicomFileDetailView,
    DicomFileCreateView,
    DicomFileUpdateView,
    DicomFileDeleteView,
    upload_dicom,
    export_dicom_to_bids,
    export_experiment_to_bids,
    dashboard,
    participant_dashboard,
    experiment_success,
    ExperimentCreateView,
    ExperimentDetailView,
    ExperimentDeleteView,
    ParticipantCreateView,
    ParticipantDetailView,
    ParticipantListView,
    upload_consent_note,
    view_consent_note,
    upload_participant_dicom,
    upload_success,
    participant_experiments,
    participant_experiment_dicoms,
    dicom_image_view,
    create_participant_ajax,
    create_member_ajax,
    update_experiment_description
)

from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False), name='home'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
    path('participant-dashboard/', participant_dashboard, name='participant_dashboard'),
    path('experiment/new/', ExperimentCreateView.as_view(), name='experiment_create'),
    path('experiment/success/', experiment_success, name='experiment_success'),
    path('experiment/<int:pk>/', ExperimentDetailView.as_view(), name='experiment_detail'),
    path('experiment/<int:pk>/delete/', ExperimentDeleteView.as_view(), name='experiment_delete'),
    path('experiment/<int:experiment_id>/export_bids/', export_experiment_to_bids, name='export_experiment_to_bids'),
    path('experiment/<int:experiment_id>/participant/new/', ParticipantCreateView.as_view(), name='participant_create'),
    path('participant/<int:pk>/', ParticipantDetailView.as_view(), name='participant_detail'),
    path('participants/', participant_dashboard, name='participant_list'),
    path('participant/<int:participant_id>/experiments/', participant_experiments, name='participant_experiments'),
    path('participant/<int:participant_id>/experiments/<int:experiment_id>/', participant_experiment_dicoms, name='participant_experiment_dicoms'),
    
    # File upload URLs
    path('experiment/<int:experiment_id>/participant/<int:participant_id>/upload-consent/', upload_consent_note, name='upload_consent_note'),
    path('participant/<int:participant_id>/experiment/<int:experiment_id>/consent-note/', view_consent_note, name='view_consent_note'),
    path('experiment/<int:experiment_id>/participant/<int:participant_id>/upload-dicom/', upload_participant_dicom, name='upload_participant_dicom'),
    path('upload-success/<str:upload_type>/', upload_success, name='upload_success'),

    path('dicomfile_list/', DicomFileListView.as_view(), name='dicomfile_list'),
    path('<int:pk>/', DicomFileDetailView.as_view(), name='dicomfile_detail'),
    path('<int:dicom_id>/image/', dicom_image_view, name='dicom_image_view'),
    path('dicomfile/new/', DicomFileCreateView.as_view(), name='dicomfile_create'),
    path('dicomfile/<int:pk>/edit/', DicomFileUpdateView.as_view(), name='dicomfile_edit'),
    path('dicomfile/<int:pk>/delete/', DicomFileDeleteView.as_view(), name='dicomfile_delete'),
    path('upload/', upload_dicom, name='upload_dicom'),
    path('search/', DicomFileListView.as_view(), name='dicom_search'),
    path('dicom/<int:pk>/export_bids/', export_dicom_to_bids, name='export_dicom_to_bids'),
    
    # AJAX URLs
    path('ajax/participant/create/', create_participant_ajax, name='create_participant_ajax'),
    path('ajax/member/create/', create_member_ajax, name='create_member_ajax'),
    path('experiment/<int:pk>/update_description/', update_experiment_description, name='update_experiment_description'),
]
