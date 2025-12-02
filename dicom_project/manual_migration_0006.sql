-- Manual database migration script for 0006
-- This script applies the schema changes that couldn't be done via Django migrations

-- Drop problematic indexes
DROP INDEX IF EXISTS dicom_app_d_tag_680663_idx;
DROP INDEX IF EXISTS dicom_app_d_dicom_f_f63741_idx;

-- Nullify all participant references in DicomFile
UPDATE dicom_app_dicomfile SET participant_id = NULL;

-- Delete all participants
DELETE FROM dicom_app_participant;

-- Drop the foreign key constraint
ALTER TABLE dicom_app_participant DROP CONSTRAINT IF EXISTS dicom_app_participant_experiment_id_fkey CASCADE;

-- Drop the experiment_id column
ALTER TABLE dicom_app_participant DROP COLUMN IF EXISTS experiment_id;

-- Add new fields to participant
ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS email VARCHAR(254) DEFAULT '';
ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS first_name VARCHAR(100) DEFAULT '';
ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS last_name VARCHAR(100) DEFAULT '';
ALTER TABLE dicom_app_participant ADD COLUMN IF NOT EXISTS phone VARCHAR(20) DEFAULT '';

-- Make subject_id unique
ALTER TABLE dicom_app_participant DROP CONSTRAINT IF EXISTS dicom_app_participant_subject_id_unique;
ALTER TABLE dicom_app_participant ADD CONSTRAINT dicom_app_participant_subject_id_unique UNIQUE (subject_id);

-- Create the many-to-many table for participant-experiment relationship
CREATE TABLE IF NOT EXISTS dicom_app_participant_experiments (
    id BIGSERIAL PRIMARY KEY,
    participant_id BIGINT NOT NULL REFERENCES dicom_app_participant(id) ON DELETE CASCADE,
    experiment_id BIGINT NOT NULL REFERENCES dicom_app_experiment(id) ON DELETE CASCADE,
    UNIQUE (participant_id, experiment_id)
);

-- Create the many-to-many table for member-experiment relationship
CREATE TABLE IF NOT EXISTS dicom_app_member_experiments (
    id BIGSERIAL PRIMARY KEY,
    member_id BIGINT NOT NULL REFERENCES dicom_app_member(id) ON DELETE CASCADE,
    experiment_id BIGINT NOT NULL REFERENCES dicom_app_experiment(id) ON DELETE CASCADE,
    UNIQUE (member_id, experiment_id)
);
