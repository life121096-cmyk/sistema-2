-- ══════════════════════════════════════════════════════════════
--  Insalud - Base de datos MySQL (XAMPP)
--  Ejecutar en phpMyAdmin o MySQL CLI
-- ══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS excel_manager
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE excel_manager;

-- ─── Tabla principal de archivos ───────────────────────────────
CREATE TABLE IF NOT EXISTS files (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    original_name VARCHAR(255)  NOT NULL COMMENT 'Nombre original del archivo',
    stored_name   VARCHAR(255)  NOT NULL COMMENT 'Nombre guardado en disco',
    file_size     BIGINT        NOT NULL DEFAULT 0 COMMENT 'Tamaño en bytes',
    file_type     VARCHAR(10)   NOT NULL DEFAULT 'XLSX' COMMENT 'XLSX, XLS, CSV',
    sheet_count   INT           NOT NULL DEFAULT 1 COMMENT 'Número de hojas',
    description   TEXT          NULL COMMENT 'Descripción opcional',
    tags          VARCHAR(500)  NULL COMMENT 'Etiquetas separadas por coma',
    uploaded_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NULL ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_uploaded_at (uploaded_at),
    INDEX idx_file_type   (file_type),
    INDEX idx_original_name (original_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Tabla de hojas por archivo ────────────────────────────────
CREATE TABLE IF NOT EXISTS file_sheets (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    file_id      INT          NOT NULL,
    sheet_name   VARCHAR(255) NOT NULL COMMENT 'Nombre de la hoja/pestaña',
    total_rows   INT          NOT NULL DEFAULT 0,
    columns_info JSON         NULL COMMENT 'Lista de columnas en JSON',
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
    INDEX idx_file_id (file_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── Vista útil para estadísticas ──────────────────────────────
CREATE OR REPLACE VIEW v_files_summary AS
SELECT
    f.id,
    f.original_name,
    f.stored_name,
    f.file_size,
    f.file_type,
    f.sheet_count,
    f.uploaded_at,
    COUNT(fs.id)       AS total_sheets,
    SUM(fs.total_rows) AS total_rows
FROM files f
LEFT JOIN file_sheets fs ON f.id = fs.file_id
GROUP BY f.id;

SELECT 'Base de datos excel_manager creada exitosamente ✅' AS mensaje;
