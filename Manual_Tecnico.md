# Manual Técnico del Proyecto DICOM-DJANGO

Este documento proporciona una visión técnica profunda del sistema, enfocada en desarrolladores. Se detallan la arquitectura, modelos esenciales, vistas críticas, lógica de procesamiento de imágenes médicas y guía de despliegue.

---

## 1. Arquitectura General del Sistema

El proyecto está construido sobre **Django**, utilizando una arquitectura MVT (Model-View-Template).

### Estructura de Directorios Clave
*   **`dicom_project/`**: Configuración principal (`settings.py`, `urls.py`).
*   **`dicom_app/`**: Aplicación núcleo.
    *   `models.py`: Definición de estructura de datos.
    *   `views.py`: Controladores y lógica de negocio.
    *   `bids_utils.py`: Lógica de procesamiento DICOM y BIDS.
    *   `templates/`: Interfaz de usuario ("Vistas" en MVC).
    *   `static/`: Assets (CSS/JS).
*   **`media/`**: Almacenamiento de archivos no estáticos (DICOMs, Notas de consentimiento).

### Flujo de Datos
1.  **Experimento**: Entidad raíz.
2.  **Participante**: Se vincula a Experimentos (N:M).
3.  **Archivos**:
    *   **DICOM**: Procesados -> Metadata extraída -> Almacenados -> Visualizados/Exportados.
    *   **Consentimiento**: Almacenados -> Visualizados inline.

---

## 2. Modelos Esenciales

### Experiment
Agrupa la lógica de investigación.
```python
class Experiment(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='Active')

    def __str__(self):
        return self.name
```

### Participant
Sujeto de estudio con ID único para trazabilidad.
```python
class Participant(models.Model):
    subject_id = models.CharField(max_length=100, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    # ...
    experiments = models.ManyToManyField(Experiment, related_name='participants', blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
```

### Member
Investigadores y staff asociados al equipo.
```python
class Member(models.Model):
    ROLE_CHOICES = [
        ('Líder Científico/a', 'Líder Científico/a'),
        # ... otros roles
    ]
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=ROLE_CHOICES)
    email = models.EmailField(blank=True)
    experiments = models.ManyToManyField(Experiment, related_name='members', blank=True)
```

### DicomFile
Representa el archivo físico y su metadata básica.
```python
class DicomFile(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='dicom_files')
    experiment = models.ForeignKey(Experiment, on_delete=models.SET_NULL, null=True, blank=True, related_name='dicom_files')
    patient_name = models.CharField(max_length=255)
    file = models.FileField(upload_to='dicoms/raw/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    is_anonymized = models.BooleanField(default=False)
```

### ConsentFile
Notas de consentimiento.
```python
class ConsentFile(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='consent_files')
    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='consent_files')
    file = models.FileField(upload_to='consent_notes/%Y/%m/%d/')
    # ...
```

### DicomTag
Almacena tags DICOM individuales para consultas rápidas sin re-parsear el archivo.
```python
class DicomTag(models.Model):
    dicom_file = models.ForeignKey(DicomFile, on_delete=models.CASCADE, related_name='tags')
    tag = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    vr = models.CharField(max_length=10)
    value = models.TextField()
```

---

## 3. Vistas Clave

### Gestión de Experimentos
**Crear Experimento (`ExperimentCreateView`)**:
Usa `CreateView` genérico de Django. Maneja automáticamente la creación y relaciones M2M del formulario.
```python
class ExperimentCreateView(LoginRequiredMixin, CreateView):
    model = Experiment
    form_class = ExperimentForm
    template_name = 'dicom_app/experiment_form.html'
    success_url = reverse_lazy('experiment_success')
```

**Detalle del Experimento (`ExperimentDetailView`)**:
Visualiza participantes y miembros.
```python
class ExperimentDetailView(LoginRequiredMixin, DetailView):
    model = Experiment
    template_name = 'dicom_app/experiment_detail.html'
    context_object_name = 'experiment'
```

### Gestión de Participantes
**Dashboard (`participant_dashboard`)**:
Lista participantes, filtra por búsqueda y calcula metadata extra (última participación).
```python
@login_required
def participant_dashboard(request):
    participants = Participant.objects.all()
    # ... lógica de búsqueda ...
    for participant in participants:
        latest_dicom = DicomFile.objects.filter(participant=participant).order_by('-upload_date').first()
        participant.last_participation = latest_dicom.upload_date if latest_dicom else None
    return render(request, 'dicom_app/participant_dashboard.html', {'participants': participants})
```

**Lista de Experimentos de un Participante (`participant_experiments`)**:
```python
@login_required
def participant_experiments(request, participant_id):
    participant = get_object_or_404(Participant, pk=participant_id)
    experiments = participant.experiments.all().order_by('-created_at')
    return render(request, 'dicom_app/participant_experiments.html', ...)
```

### Gestión de DICOM
**Subida de DICOM (`upload_dicom`)**:
Maneja el formulario y delega el procesamiento.
```python
@login_required
def upload_dicom(request):
    if request.method == 'POST':
        form = DicomUploadForm(request.POST, request.FILES)
        if form.is_valid():
            dicom_file = request.FILES['dicom_file']
            # Delegación a loader helper
            dicom_instance, dicom_data = process_dicom_file(dicom_file)
            return render(request, 'success.html', ...)
    # ...
```

**Detalle del Archivo (`DicomFileDetailView`)**:
Prepara los tags para visualización optimizada (carga inicial + carga diferida via JSON).
```python
class DicomFileDetailView(LoginRequiredMixin, DetailView):
    model = DicomFile
    template_name = 'dicom_app/dicomfile_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tags = list(self.object.tags.all())
        # ... lógica de limpieza de tags ...
        context['initial_tags'] = cleaned_tags[:50]
        context['remaining_tags_json'] = json.dumps(cleaned_tags[50:])
        return context
```

**Visualización de Imagen (`dicom_image_view`)**:
Renderiza el pixel array del DICOM a PNG.
```python
@login_required
def dicom_image_view(request, dicom_id):
    dicom_file = get_object_or_404(DicomFile, pk=dicom_id)
    # ... resolución de path ...
    ds = pydicom.dcmread(dicom_path)
    pixel_array = ds.pixel_array
    # ... normalización a 8-bit ...
    image = Image.fromarray(pixel_array)
    response = HttpResponse(content_type="image/png")
    image.save(response, "PNG")
    return response
```

### Nota de Consentimiento
**Visualizar (`view_consent_note`)**:
Sirve el archivo (PDF/IMG) inline asegurando tipos MIME correctos.
```python
@login_required
def view_consent_note(request, participant_id, experiment_id):
    # ... obtener consent_file ...
    response = FileResponse(open(file_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response
```

---

## 4. Procesamiento del DICOM

### Flujo de lectura y extracción
Función `process_dicom_file` (en `views.py`):
1.  Lee el archivo con `pydicom`.
2.  Genera un nombre de archivo seguro.
3.  Guarda el archivo raw en `media/dicoms/raw/`.
4.  Crea la entrada `DicomFile`.
5.  Itera todos los elementos del dataset y crea registros `DicomTag`.

### Exportación y Conversión a BIDS
Función `export_experiment_to_bids` y `bids_utils.py`:
1.  **Estructura**: Crea directorios `sub-XX/anat/`, `sub-XX/func/`.
2.  **Detección (`detect_modality`)**:
    Analiza `SeriesDescription` o `Modality` para clasificar en `anat` (T1w), `func` (BOLD), o `dwi` (DWI).
    ```python
    def detect_modality(ds):
        if "bold" in series_desc: return "func", "task-rest_bold"
        # ...
    ```
3.  **Anonimización (`anonymize_dicom`)**:
    Borra tags sensibles (`PatientName`, `PatientID`) y regenera UIDs antes de la conversión final.
4.  **Conversión (`convert_dicom_to_nifti`)**:
    Intenta usar `dicom2nifti` para convertir el directorio.
    Si falla (o es imagen única), usa `nibabel` como fallback.
    ```python
    def convert_dicom_to_nifti(...):
        # ... try: dicom2nifti.convert_directory(...)
        # ... except: nib.save(nib.Nifti1Image(pixel_array, affine), output_path)
    ```

---

## 5. Rutas Esenciales

```python
# URLs de Proyecto
urlpatterns = [
    path('', include('dicom_app.urls')),
    # ... admin ...
]

# URLs de Aplicación (dicom_app/urls.py)
urlpatterns = [
    # Dashboard
    path('dashboard/', dashboard, name='dashboard'),
    path('participant-dashboard/', participant_dashboard, name='participant_dashboard'),
    
    # Experimentos
    path('experiment/new/', ExperimentCreateView.as_view(), name='experiment_create'),
    path('experiment/<int:pk>/', ExperimentDetailView.as_view(), name='experiment_detail'),
    
    # Participantes
    path('participants/', participant_dashboard, name='participant_list'),
    path('participant/<int:participant_id>/experiments/<int:experiment_id>/', participant_experiment_dicoms, ...),

    # DICOM Ops
    path('upload/', upload_dicom, name='upload_dicom'),
    path('<int:pk>/', DicomFileDetailView.as_view(), name='dicomfile_detail'),
    path('<int:dicom_id>/image/', dicom_image_view, name='dicom_image_view'),
    
    # Exportación
    path('experiment/<int:experiment_id>/export_bids/', export_experiment_to_bids, name='export_experiment_to_bids'),
    
    # Consentimiento
    path('participant/<int:participant_id>/experiment/<int:experiment_id>/consent-note/', view_consent_note, name='view_consent_note'),
]
```

---

## 6. Templates Importantes

### `dicomfile_detail.html`
*   **Propósito**: Mostrar toda la información técnica de un DICOM.
*   **Componentes**:
    *   Header con nombre de paciente y fecha.
    *   Botones de acción (Editar, Eliminar, Ver Imagen).
    *   Tabla de Tags: Renderiza los primeros 50 tags desde el servidor (`initial_tags`) y usa un script JS para cargar el resto (`remaining_tags_json`) evitando bloqueos del render en archivos grandes.

### `participant_dashboard.html`
*   **Propósito**: Listado principal de participantes.
*   **Estructura**:
    *   Barra de búsqueda GET `?q=...`.
    *   Tabla iterando `participants` con columnas: Nombre, Última Participación (calculada en vista), Botón "Visualizar" (ojo).

### `experiment_detail.html`
*   **Propósito**: Gestión centralizada de un estudio.
*   **Componentes**:
    *   Edición de Descripción: Bloque JS que permite editar `experiment.description` in-place y guardar con `fetch`.
    *   Listado de Participantes: Muestra lista y accesos directos críticos ("Subir nota de consentimiento", "Subir DICOM").
    *   Listado de Miembros: Muestra el equipo asignado.

---

## 7. Manual de Instalación Técnico

Pasos para levantar el proyecto desde cero en un entorno de desarrollo.

1.  **Entorno Virtual**:
    Crear y activar entorno virtual para aislar dependencias.
    ```bash
    python -m venv venv
    # Windows:
    .\venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate
    ```

2.  **Instalar Dependencias**:
    ```bash
    pip install -r requirements.txt
    ```
    *Core packages: Django, pydicom, numpy, Pillow, dicom2nifti, nibabel.*

3.  **Base de Datos**:
    Aplicar migraciones para crear las tablas (sqlite3 por defecto).
    ```bash
    python manage.py migrate
    ```

4.  **Administración**:
    Crear superusuario para acceder a `/admin/` y gestionar usuarios del sistema.
    ```bash
    python manage.py createsuperuser
    ```

5.  **Ejecutar Servidor**:
    ```bash
    python manage.py runserver
    ```
    El sistema estará disponible en `http://127.0.0.1:8000/`.
