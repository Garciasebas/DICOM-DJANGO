# DICOM-DJANGO Project

Sistema de gestión de archivos DICOM para investigación médica.

## 🚀 Instalación Rápida

### Requisitos Previos
- Python 3.8 o superior
- PostgreSQL 12 o superior
- pip

### Pasos de Instalación

1. **Clonar el repositorio**
   ```bash
   git clone <repository-url>
   cd DICOM-DJANGO/dicom_project
   ```

2. **Crear y activar entorno virtual** (recomendado)
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar base de datos PostgreSQL**
   
   Crear la base de datos en PostgreSQL:
   ```sql
   CREATE DATABASE dicom_db;
   ```
   
   Actualizar las credenciales en `dicom_project/settings.py` (líneas 77-89) según tu configuración local.

5. **Ejecutar migraciones**
   ```bash
   python manage.py migrate
   ```
   
   Esto creará automáticamente:
   - ✅ 10 Participants (PART001-PART010)
   - ✅ 10 Members (equipo de investigación)
   - ✅ 5 Experiments (estudios médicos)

6. **Crear superusuario** (opcional)
   ```bash
   python manage.py createsuperuser
   ```

7. **Iniciar el servidor**
   ```bash
   python manage.py runserver
   ```

8. **Acceder a la aplicación**
   - Aplicación: http://127.0.0.1:8000/
   - Admin: http://127.0.0.1:8000/admin/

## 📊 Datos Iniciales

El proyecto incluye datos de prueba que se crean automáticamente al ejecutar `migrate`:

- **10 Participants**: Participantes ficticios con IDs PART001-PART010
  - Incluyen: nombre, apellido, email, teléfono
- **10 Members**: Miembros del equipo de investigación
  - Roles: Investigador Principal, Coordinadora, Técnico Radiólogo, Médica Especialista, Analista de Datos, etc.
- **5 Experiments**: Estudios médicos de ejemplo
  - RM cerebral, TAC tórax, Ecografía Doppler, RM rodilla, PET-CT

## 🛠️ Comandos Útiles

```bash
# Verificar estado de migraciones
python manage.py showmigrations

# Crear superusuario
python manage.py createsuperuser

# Ejecutar shell de Django
python manage.py shell

# Verificar datos iniciales
python manage.py shell -c "from dicom_app.models import Participant, Member; print(f'Participants: {Participant.objects.count()}'); print(f'Members: {Member.objects.count()}')"
```

## 📁 Estructura del Proyecto

```
dicom_project/
├── dicom_app/              # Aplicación principal
│   ├── models.py           # Modelos de datos
│   ├── views.py            # Vistas
│   ├── urls.py             # Rutas
│   ├── templates/          # Plantillas HTML
│   ├── static/             # Archivos estáticos (CSS, JS)
│   └── migrations/         # Migraciones de BD
├── dicom_project/          # Configuración del proyecto
│   ├── settings.py         # Configuración
│   └── urls.py             # Rutas principales
├── media/                  # Archivos subidos (DICOM, consentimientos)
├── manage.py               # Script de gestión de Django
└── requirements.txt        # Dependencias
```

## 🔒 Seguridad

⚠️ **IMPORTANTE**: Antes de desplegar en producción:
- Cambiar `SECRET_KEY` en `settings.py`
- Establecer `DEBUG = False`
- Configurar `ALLOWED_HOSTS`
- Usar variables de entorno para credenciales de base de datos
- Configurar HTTPS
- Revisar configuración de CORS si es necesario

## 📦 Dependencias Principales

- Django 5.1.1 - Framework web
- pydicom 2.3.1 - Lectura de archivos DICOM
- dicom2nifti 2.4.6 - Conversión DICOM a NIfTI
- nibabel 5.3.2 - Procesamiento de imágenes médicas
- Pillow 10.3.0 - Procesamiento de imágenes
- psycopg2 2.9.9 - Adaptador PostgreSQL

## 🗄️ Modelos de Datos

- **Experiment**: Experimentos/estudios médicos
- **Participant**: Participantes de los estudios
- **Member**: Miembros del equipo de investigación
- **DicomFile**: Archivos DICOM subidos
- **DicomTag**: Tags/metadatos de archivos DICOM
- **ConsentFile**: Notas de consentimiento
- **TeamMember**: Relación usuarios-experimentos

## 📝 Notas

- Los archivos DICOM se almacenan en `media/dicoms/raw/YYYY/MM/DD/`
- Las notas de consentimiento se almacenan en `media/consent_notes/YYYY/MM/DD/`
- El proyecto usa zona horaria `America/Asuncion` (UTC-3/UTC-4)
- Idioma configurado: Español (Paraguay)
