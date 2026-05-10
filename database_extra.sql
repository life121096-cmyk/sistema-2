-- Tabla para etiquetas de filas
CREATE TABLE IF NOT EXISTS row_labels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    sheet_name VARCHAR(255) NOT NULL,
    row_index INT NOT NULL,
    label VARCHAR(255) NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Tabla para etiquetas de columnas
CREATE TABLE IF NOT EXISTS column_labels (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    sheet_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    label VARCHAR(255) NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Tabla para imágenes asociadas a filas
CREATE TABLE IF NOT EXISTS row_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    file_id INT NOT NULL,
    sheet_name VARCHAR(255) NOT NULL,
    row_index INT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
) ENGINE=InnoDB;
