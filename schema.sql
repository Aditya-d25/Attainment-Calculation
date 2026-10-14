-- =============================================================================
-- Database Schema for AI CO-PO Mapping & Attainment Calculation System
-- SPPU - Information Technology Department
-- 4-Year B.E. Programme (FE, SE, TE, BE) with 2 Divisions (Div A & Div B)
--
-- IMPORTANT:
--   Subjects and Course Outcomes (COs) are populated ONLY via PDF upload.
--   DO NOT add INSERT statements for subjects or course_outcomes here.
--   POs/PSOs below are official SPPU IT definitions and are the only
--   static seed data besides the academic division structure.
-- =============================================================================

CREATE DATABASE IF NOT EXISTS `co_po_attainment`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `co_po_attainment`;

-- -----------------------------------------------------------------------------
-- 1. Academic Divisions
--    Fixed structure: 4 years x 2 divisions = 8 classes for IT Department
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `academic_divisions` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `year`          ENUM('FE', 'SE', 'TE', 'BE') NOT NULL,
    `division`      VARCHAR(10)  NOT NULL,
    `class_name`    VARCHAR(50)  NOT NULL,
    `academic_year` VARCHAR(50)  NOT NULL DEFAULT '2024-25',
    `department`    VARCHAR(100) NOT NULL DEFAULT 'Information Technology',
    `class_teacher` VARCHAR(100) DEFAULT NULL,
    `created_at`    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY `uq_year_div_dept` (`year`, `division`, `academic_year`, `department`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 2. Outcome Frameworks
--    One framework per programme (e.g. "SPPU - BE IT 2019 Course").
--    Subjects are linked to a framework so they share the same PO/PSO set.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `outcome_frameworks` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `name`        VARCHAR(200) NOT NULL UNIQUE,
    `department`  VARCHAR(100) DEFAULT 'Information Technology',
    `description` TEXT         DEFAULT NULL,
    `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 3. Framework Outcomes (POs & PSOs)
--    Shared across all subjects linked to the same framework.
--    Populated from the PDF upload (or from the SPPU seed data below).
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `framework_outcomes` (
    `id`           INT AUTO_INCREMENT PRIMARY KEY,
    `framework_id` INT         NOT NULL,
    `outcome_code` VARCHAR(20) NOT NULL,
    `outcome_type` VARCHAR(10) NOT NULL DEFAULT 'PO',
    `description`  TEXT        NOT NULL,
    `created_at`   DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_fo_framework` (`framework_id`),
    CONSTRAINT `fk_fo_framework` FOREIGN KEY (`framework_id`)
        REFERENCES `outcome_frameworks` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 4. Subjects / Courses
--    Created automatically when a syllabus PDF is uploaded.
--    year: 'FE' | 'SE' | 'TE' | 'BE'
--    semester: 'Semester I' through 'Semester VIII'
--    division: 'All' | 'A' | 'B'
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `subjects` (
    `id`             INT AUTO_INCREMENT PRIMARY KEY,
    `course_code`    VARCHAR(50)  NOT NULL UNIQUE,
    `course_name`    VARCHAR(200) NOT NULL,
    `year`           VARCHAR(10)  NOT NULL DEFAULT 'BE',
    `semester`       VARCHAR(50)  NOT NULL DEFAULT 'Semester VII',
    `division`       VARCHAR(20)  NOT NULL DEFAULT 'All',
    `academic_year`  VARCHAR(50)  NOT NULL DEFAULT '2024-25',
    `department`     VARCHAR(100) NOT NULL DEFAULT 'Information Technology',
    `theory_enabled` BOOLEAN DEFAULT TRUE,
    `description`    TEXT DEFAULT NULL,
    `framework_id`   INT DEFAULT NULL,
    `created_at`     DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_subjects_framework` (`framework_id`),
    KEY `idx_subjects_year_div`  (`year`, `division`),
    CONSTRAINT `fk_subjects_framework` FOREIGN KEY (`framework_id`)
        REFERENCES `outcome_frameworks` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 5. Course Outcomes (COs)
--    Extracted from the syllabus PDF per subject.
--    Never inserted manually -- always via PDF upload.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `course_outcomes` (
    `id`                  INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`          INT  NOT NULL,
    `co_code`             VARCHAR(20) NOT NULL,
    `description`         TEXT NOT NULL,
    `univ_attainment`     FLOAT DEFAULT 0.0,
    `internal_attainment` FLOAT DEFAULT 0.0,
    `created_at`          DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_co_subject` (`subject_id`),
    CONSTRAINT `fk_co_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 6. Program Outcomes (legacy per-subject overrides)
--    Normally POs are read from framework_outcomes.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `program_outcomes` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`  INT NOT NULL,
    `po_code`     VARCHAR(20) NOT NULL,
    `description` TEXT NOT NULL,
    `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_po_subject` (`subject_id`),
    CONSTRAINT `fk_po_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 7. Program Specific Outcomes (legacy per-subject overrides)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `program_specific_outcomes` (
    `id`          INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`  INT NOT NULL,
    `pso_code`    VARCHAR(20) NOT NULL,
    `description` TEXT NOT NULL,
    `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_pso_subject` (`subject_id`),
    CONSTRAINT `fk_pso_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 8. AI CO-PO Mapping Results
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `ai_mapping_results` (
    `id`                  INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`          INT NOT NULL,
    `division`            VARCHAR(20) NOT NULL DEFAULT 'All',
    `co_id`               INT NOT NULL,
    `co_code`             VARCHAR(20) NOT NULL,
    `po_pso_id`           INT NOT NULL,
    `po_pso_code`         VARCHAR(20) NOT NULL,
    `po_pso_type`         VARCHAR(10) NOT NULL,
    `mapping_level`       INT NOT NULL DEFAULT 0,
    `confidence`          FLOAT NOT NULL DEFAULT 0.0,
    `similarity_score`    FLOAT NOT NULL DEFAULT 0.0,
    `reason`              TEXT DEFAULT NULL,
    `evidence`            TEXT DEFAULT NULL,
    `method`              VARCHAR(20) NOT NULL DEFAULT 'hybrid',
    `faculty_decision`    VARCHAR(20) NOT NULL DEFAULT 'pending',
    `final_mapping_level` INT DEFAULT NULL,
    `faculty_notes`       TEXT DEFAULT NULL,
    `reviewed_at`         DATETIME DEFAULT NULL,
    `created_at`          DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at`          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY `idx_ai_subject` (`subject_id`),
    KEY `idx_ai_co`      (`co_id`),
    KEY `idx_ai_div`     (`division`),
    CONSTRAINT `fk_ai_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ai_co` FOREIGN KEY (`co_id`)
        REFERENCES `course_outcomes` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 9. Reference Mappings (faculty-uploaded CO-PO matrix)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `reference_mappings` (
    `id`            INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`    INT NOT NULL,
    `division`      VARCHAR(20) NOT NULL DEFAULT 'All',
    `co_code`       VARCHAR(20) NOT NULL,
    `po_pso_code`   VARCHAR(20) NOT NULL,
    `po_pso_type`   VARCHAR(10) NOT NULL,
    `mapping_level` INT NOT NULL DEFAULT 0,
    `source_file`   VARCHAR(500) DEFAULT NULL,
    `created_at`    DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_ref_subject` (`subject_id`),
    CONSTRAINT `fk_ref_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 10. Mapping Evaluations (accuracy metrics per subject & method)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `mapping_evaluations` (
    `id`                    INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id`            INT NOT NULL,
    `division`              VARCHAR(20) NOT NULL DEFAULT 'All',
    `method`                VARCHAR(20) NOT NULL DEFAULT 'hybrid',
    `accuracy`              FLOAT DEFAULT NULL,
    `precision_macro`       FLOAT DEFAULT NULL,
    `recall_macro`          FLOAT DEFAULT NULL,
    `f1_macro`              FLOAT DEFAULT NULL,
    `agreement_percentage`  FLOAT DEFAULT NULL,
    `per_co_accuracy`       TEXT DEFAULT NULL,
    `per_po_accuracy`       TEXT DEFAULT NULL,
    `confusion_matrix`      TEXT DEFAULT NULL,
    `classification_report` TEXT DEFAULT NULL,
    `created_at`            DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_eval_subject` (`subject_id`),
    CONSTRAINT `fk_eval_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- 11. Documents (uploaded files tracker)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `documents` (
    `id`         INT AUTO_INCREMENT PRIMARY KEY,
    `subject_id` INT NOT NULL,
    `filename`   VARCHAR(500)  NOT NULL,
    `file_path`  VARCHAR(1000) NOT NULL,
    `doc_type`   VARCHAR(50)   NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    KEY `idx_docs_subject` (`subject_id`),
    CONSTRAINT `fk_docs_subject` FOREIGN KEY (`subject_id`)
        REFERENCES `subjects` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- SEED DATA (Department Structure Only)
-- All Frameworks, POs, PSOs, Subjects, and COs are extracted exclusively
-- from uploaded syllabus PDFs via the Admin Panel (POST /api/pdf/upload).
-- =============================================================================

-- Eight academic classes: 4 years x 2 divisions for IT Department
INSERT INTO `academic_divisions` (`year`, `division`, `class_name`, `academic_year`, `department`) VALUES
('FE', 'A', 'FE-IT-A', '2024-25', 'Information Technology'),
('FE', 'B', 'FE-IT-B', '2024-25', 'Information Technology'),
('SE', 'A', 'SE-IT-A', '2024-25', 'Information Technology'),
('SE', 'B', 'SE-IT-B', '2024-25', 'Information Technology'),
('TE', 'A', 'TE-IT-A', '2024-25', 'Information Technology'),
('TE', 'B', 'TE-IT-B', '2024-25', 'Information Technology'),
('BE', 'A', 'BE-IT-A', '2024-25', 'Information Technology'),
('BE', 'B', 'BE-IT-B', '2024-25', 'Information Technology')
ON DUPLICATE KEY UPDATE `class_name` = VALUES(`class_name`);

-- NOTE: outcome_frameworks, framework_outcomes, subjects, and course_outcomes tables
--       are populated dynamically when syllabus PDFs are uploaded.

