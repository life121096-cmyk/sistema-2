CREATE TABLE IF NOT EXISTS excel_templates (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS excel_template_mappings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  template_id INT NOT NULL,
  column_name VARCHAR(255) NOT NULL,
  field_key ENUM('estado','municipio','parroquia','asic','custom') NOT NULL,
  custom_value VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (template_id) REFERENCES excel_templates(id) ON DELETE CASCADE
);
