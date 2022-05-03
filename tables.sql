DROP TABLE IF EXISTS `cache`;
DROP TABLE IF EXISTS `places`;
DROP TABLE IF EXISTS `ciudades`;
DROP TABLE IF EXISTS `departamentos`;
DROP TABLE IF EXISTS `paises`;

CREATE TABLE `paises` (
 `idpais` int(11) NOT NULL AUTO_INCREMENT,
 `nombre_pais` varchar(70) NOT NULL,
 `priority` int NOT NULL DEFAULT 10,
 `created_at` timestamp NULL DEFAULT current_timestamp(),
 `updated_at` timestamp NULL DEFAULT NULL,
 PRIMARY KEY (`idpais`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `departamentos` (
 `iddepartamento` int(11) NOT NULL AUTO_INCREMENT,
 `paises_idpais` int(11) NOT NULL,
 `nombre_departamento` varchar(70) NOT NULL,
 `priority` int NOT NULL DEFAULT 10,
 `created_at` timestamp NULL DEFAULT current_timestamp(),
 `updated_at` timestamp NULL DEFAULT NULL,
 PRIMARY KEY (`iddepartamento`,`paises_idpais`),
 KEY `fk_departamentos_paises1_idx` (`paises_idpais`),
 CONSTRAINT `fk_departamentos_paises1` FOREIGN KEY (`paises_idpais`) REFERENCES `paises` (`idpais`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `ciudades` (
 `idciudad` int(11) NOT NULL AUTO_INCREMENT,
 `departamentos_iddepartamento` int(11) NOT NULL,
 `nombre_ciudad` varchar(70) NOT NULL,
 `priority` int NOT NULL DEFAULT 10,
 `created_at` timestamp NULL DEFAULT current_timestamp(),
 `updated_at` timestamp NULL DEFAULT NULL,
 PRIMARY KEY (`idciudad`,`departamentos_iddepartamento`),
 KEY `fk_ciudades_departamentos1_idx` (`departamentos_iddepartamento`),
 CONSTRAINT `fk_ciudades_departamentos1` FOREIGN KEY (`departamentos_iddepartamento`) REFERENCES `departamentos` (`iddepartamento`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `places` (
    `idplace` int(11) NOT NULL AUTO_INCREMENT,
    `ciudades_idciudad` int(11) NOT NULL,
    `data_card_id` varchar(255) DEFAULT NULL, -- id del lugar en la api de google en things to do
    `place_id` varchar(255) DEFAULT NULL, -- id del lugar en la api de google
    `nombre_place_es` varchar(255) DEFAULT NULL,
    `nombre_place_en` varchar(255) DEFAULT NULL,
    `descripcion_ttt_es` TEXT DEFAULT NULL,
    `descripcion_ttt_en` TEXT DEFAULT NULL,
    `descripcion_short_es` TEXT DEFAULT NULL,
    `descripcion_short_en` TEXT DEFAULT NULL,
    `descripcion_long_es` TEXT DEFAULT NULL,
    `descripcion_long_en` TEXT DEFAULT NULL,
    `direccion_es` varchar(255) DEFAULT NULL,
    `direccion_en` varchar(255) DEFAULT NULL,
    `web` varchar(100) DEFAULT NULL,
    `telefono` varchar(20) DEFAULT NULL,
    `email` varchar(100) DEFAULT NULL,
    `lat` double DEFAULT NULL,
    `lng` double DEFAULT NULL,
    `imagenes` JSON DEFAULT NULL,
    `duracion` varchar(50) DEFAULT NULL,
    `rating` double DEFAULT NULL,
    `costos` JSON DEFAULT NULL,
    `horarios` JSON DEFAULT NULL,
    `reviews_es` JSON DEFAULT NULL,
    `reviews_en` JSON DEFAULT NULL,
    `categorias` JSON DEFAULT NULL,
    `maps_scraped` TINYINT(1) DEFAULT 0,
    `created_at` timestamp NULL DEFAULT current_timestamp(),
    `updated_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`idplace`,`ciudades_idciudad`),
    KEY `fk_places_ciudades1_idx` (`ciudades_idciudad`),
    CONSTRAINT `fk_places_ciudades1` FOREIGN KEY (`ciudades_idciudad`) REFERENCES `ciudades` (`idciudad`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

DROP TABLE IF EXISTS `cache`;
CREATE TABLE `cache` (
    `idciudad` int(11) NOT NULL AUTO_INCREMENT,
    `created_at` timestamp NULL DEFAULT current_timestamp(),
    PRIMARY KEY (`idciudad`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
