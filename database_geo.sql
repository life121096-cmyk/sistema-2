-- ─── Catálogo Geográfico ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS estados (
    id     INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS municipios (
    id        INT AUTO_INCREMENT PRIMARY KEY,
    estado_id INT NOT NULL,
    nombre    VARCHAR(100) NOT NULL,
    FOREIGN KEY (estado_id) REFERENCES estados(id) ON DELETE CASCADE,
    UNIQUE KEY uk_mun (estado_id, nombre)
);

CREATE TABLE IF NOT EXISTS parroquias (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    municipio_id INT NOT NULL,
    nombre       VARCHAR(100) NOT NULL,
    FOREIGN KEY (municipio_id) REFERENCES municipios(id) ON DELETE CASCADE,
    UNIQUE KEY uk_parr (municipio_id, nombre)
);

CREATE TABLE IF NOT EXISTS asics (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    nombre       VARCHAR(200) NOT NULL,
    parroquia_id INT DEFAULT NULL,
    FOREIGN KEY (parroquia_id) REFERENCES parroquias(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS `jefes_asic` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `apellido` varchar(100) NOT NULL,
  `telefono` varchar(50) DEFAULT NULL,
  `asic_id` int(11) DEFAULT NULL,
  `cdi` varchar(200) NOT NULL,
  `estado_id` int(11) DEFAULT NULL,
  `municipio_id` int(11) DEFAULT NULL,
  `parroquia_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `asic_id` (`asic_id`),
  KEY `estado_id` (`estado_id`),
  KEY `municipio_id` (`municipio_id`),
  KEY `parroquia_id` (`parroquia_id`),
  CONSTRAINT `jefes_asic_ibfk_1` FOREIGN KEY (`asic_id`) REFERENCES `asics` (`id`) ON DELETE SET NULL,
  CONSTRAINT `jefes_asic_ibfk_2` FOREIGN KEY (`estado_id`) REFERENCES `estados` (`id`) ON DELETE SET NULL,
  CONSTRAINT `jefes_asic_ibfk_3` FOREIGN KEY (`municipio_id`) REFERENCES `municipios` (`id`) ON DELETE SET NULL,
  CONSTRAINT `jefes_asic_ibfk_4` FOREIGN KEY (`parroquia_id`) REFERENCES `parroquias` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
