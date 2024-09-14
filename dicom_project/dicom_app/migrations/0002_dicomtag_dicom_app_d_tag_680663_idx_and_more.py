# Generated by Django 5.1.1 on 2024-09-14 17:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dicom_app', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='dicomtag',
            index=models.Index(fields=['tag'], name='dicom_app_d_tag_680663_idx'),
        ),
        migrations.AddIndex(
            model_name='dicomtag',
            index=models.Index(fields=['dicom_file'], name='dicom_app_d_dicom_f_f63741_idx'),
        ),
    ]
