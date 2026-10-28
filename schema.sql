CREATE DATABASE IF NOT EXISTS resume_assessment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE resume_assessment;
CREATE TABLE IF NOT EXISTS candidates (
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 full_name VARCHAR(255) NULL, email VARCHAR(320) NULL, phone VARCHAR(80) NULL,
 skills_json JSON NOT NULL, education_json JSON NOT NULL, experience_json JSON NOT NULL,
 linkedin_url VARCHAR(1000) NULL, linkedin_format_valid BOOLEAN NOT NULL DEFAULT FALSE,
 linkedin_found_in_resume BOOLEAN NOT NULL DEFAULT FALSE, resume_filename VARCHAR(255) NOT NULL,
 resume_text LONGTEXT NOT NULL, parsed_result_json JSON NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_candidates_email(email), INDEX idx_candidates_created_at(created_at)
);
