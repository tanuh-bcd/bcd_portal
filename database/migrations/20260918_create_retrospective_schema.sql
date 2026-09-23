CREATE DATABASE IF NOT EXISTS `retrospective`
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `retrospective`;

CREATE TABLE IF NOT EXISTS retrospective_upload_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    upload_batch_id VARCHAR(30) NOT NULL,
    institute_id VARCHAR(20) NOT NULL,
    institute_name VARCHAR(255) NOT NULL,
    source_folder_name VARCHAR(255) NOT NULL,
    total_cases_identified INT NOT NULL DEFAULT 0,
    processed_cases INT NOT NULL DEFAULT 0,
    successful_cases INT NOT NULL DEFAULT 0,
    failed_cases INT NOT NULL DEFAULT 0,
    no_data_cases INT NOT NULL DEFAULT 0,
    batch_status ENUM('PENDING','PROCESSING','COMPLETED','COMPLETED_WITH_ERRORS','FAILED') NOT NULL DEFAULT 'PENDING',
    created_by VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_retro_batch_id UNIQUE (upload_batch_id),
    INDEX idx_retro_batch_institute (institute_id),
    INDEX idx_retro_batch_status (batch_status)
);

CREATE TABLE IF NOT EXISTS retrospective_cases (
    id INT AUTO_INCREMENT PRIMARY KEY,
    retrospective_case_id VARCHAR(20) NOT NULL,
    upload_batch_id VARCHAR(30) NOT NULL,
    institute_id VARCHAR(20) NOT NULL,
    institute_name VARCHAR(255) NOT NULL,
    source_case_name VARCHAR(255) NOT NULL,
    source_folder VARCHAR(500) NULL,
    dicom_count INT NOT NULL DEFAULT 0,
    report_count INT NOT NULL DEFAULT 0,
    dicom_available BOOLEAN NOT NULL DEFAULT FALSE,
    report_available BOOLEAN NOT NULL DEFAULT FALSE,
    dicom_reference TEXT NULL,
    report_gcs_path TEXT NULL,
    case_status ENUM('PENDING','PROCESSING','COMPLETED','PARTIAL','FAILED','NO_DATA') NOT NULL DEFAULT 'PENDING',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_retro_case_id UNIQUE (retrospective_case_id),
    CONSTRAINT uq_retro_case_batch_source UNIQUE (upload_batch_id, source_case_name),
    CONSTRAINT fk_retro_case_batch FOREIGN KEY (upload_batch_id)
        REFERENCES retrospective_upload_batches (upload_batch_id) ON DELETE CASCADE,
    INDEX idx_retro_case_institute (institute_id),
    INDEX idx_retro_case_status (case_status)
);

CREATE TABLE IF NOT EXISTS retrospective_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    retrospective_case_id VARCHAR(20) NOT NULL,
    file_type ENUM('DICOM','REPORT') NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    gcp_path TEXT NULL,
    dicom_uid VARCHAR(128) NULL,
    upload_status ENUM('PENDING','UPLOADED','FAILED') NOT NULL DEFAULT 'PENDING',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT uq_retro_file_case_name UNIQUE (retrospective_case_id, file_type, file_name),
    CONSTRAINT fk_retro_file_case FOREIGN KEY (retrospective_case_id)
        REFERENCES retrospective_cases (retrospective_case_id) ON DELETE CASCADE,
    INDEX idx_retro_file_status (upload_status),
    INDEX idx_retro_file_dicom_uid (dicom_uid)
);
