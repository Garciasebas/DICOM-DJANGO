"""
Script to manually apply database schema changes for migration 0006
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dicom_project.settings')
django.setup()

from django.db import connection

sql_commands = [
    "DROP INDEX IF EXISTS dicom_app_d_tag_680663_idx;",
    "DROP INDEX IF EXISTS dicom_app_d_dicom_f_f63741_idx;",
    "UPDATE dicom_app_dicomfile SET participant_id = NULL;",
    "DELETE FROM dicom_app_participant;",
    "ALTER TABLE dicom_app_participant DROP CONSTRAINT IF EXISTS dicom_app_participant_experiment_id_fkey CASCADE;",
    "ALTER TABLE dicom_app_participant DROP COLUMN IF EXISTS experiment_id;",
    "ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS email VARCHAR(254) DEFAULT '';",
    "ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS first_name VARCHAR(100) DEFAULT '';",
    "ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS last_name VARCHAR(100) DEFAULT '';",
    "ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS phone VARCHAR(20) DEFAULT '';",
    "ALTER TABLE dicom_app_participant DROP CONSTRAINT IF EXISTS dicom_app_participant_subject_id_unique;",
    "ALTER TABLE dicom_app_participant ADD CONSTRAINT dicom_app_participant_subject_id_unique UNIQUE (subject_id);",
    """
    CREATE TABLE IF NOT EXISTS dicom_app_participant_experiments (
        id BIGSERIAL PRIMARY KEY,
        participant_id BIGINT NOT NULL REFERENCES dicom_app_participant(id) ON DELETE CASCADE,
        experiment_id BIGINT NOT NULL REFERENCES dicom_app_experiment(id) ON DELETE CASCADE,
        UNIQUE (participant_id, experiment_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS dicom_app_member_experiments (
        id BIGSERIAL PRIMARY KEY,
        member_id BIGINT NOT NULL REFERENCES dicom_app_member(id) ON DELETE CASCADE,
        experiment_id BIGINT NOT NULL REFERENCES dicom_app_experiment(id) ON DELETE CASCADE,
        UNIQUE (member_id, experiment_id)
    );
    """,
]

with connection.cursor() as cursor:
    for sql in sql_commands:
        try:
            print(f"Executing: {sql[:50]}...")
            cursor.execute(sql)
            print("✓ Success")
        except Exception as e:
            print(f"✗ Error: {e}")

print("\n✅ Manual migration completed!")
