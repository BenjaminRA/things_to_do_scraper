CREATE TABLE `paises` (
 `idpais` int(11) NOT NULL AUTO_INCREMENT,
 `nombre_pais` varchar(70) NOT NULL,
 `created_at` timestamp NULL DEFAULT current_timestamp(),
 `updated_at` timestamp NULL DEFAULT NULL,
 PRIMARY KEY (`idpais`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `departamentos` (
 `iddepartamento` int(11) NOT NULL AUTO_INCREMENT,
 `paises_idpais` int(11) NOT NULL,
 `nombre_departamento` varchar(70) NOT NULL,
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
 `created_at` timestamp NULL DEFAULT current_timestamp(),
 `updated_at` timestamp NULL DEFAULT NULL,
 PRIMARY KEY (`idciudad`,`departamentos_iddepartamento`),
 KEY `fk_ciudades_departamentos1_idx` (`departamentos_iddepartamento`),
 CONSTRAINT `fk_ciudades_departamentos1` FOREIGN KEY (`departamentos_iddepartamento`) REFERENCES `departamentos` (`iddepartamento`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `places` (
    `idplace` int(11) NOT NULL AUTO_INCREMENT,
    `ciudades_idciudad` int(11) NOT NULL,
    `nombre_place` varchar(255) NOT NULL,
    `created_at` timestamp NULL DEFAULT current_timestamp(),
    `updated_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`idplace`,`ciudades_idciudad`),
    KEY `fk_places_ciudades1_idx` (`ciudades_idciudad`),
    CONSTRAINT `fk_places_ciudades1` FOREIGN KEY (`ciudades_idciudad`) REFERENCES `ciudades` (`idciudad`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `places_description` (
    `idplace_description` int(11) NOT NULL AUTO_INCREMENT,
    `lang` varchar(10) NOT NULL,
    `nombre` varchar(255),
    `descripcion_corta` TEXT,
    `descripcion_larga` TEXT,
    `descripcion` TEXT,
    `direccion` TEXT,
    `rating` DOUBLE,
    `duracion_aprox` DOUBLE,
    `lat` DOUBLE,
    `long` DOUBLE,
    `costo` DOUBLE,
    `web` VARCHAR(255),
    `email` VARCHAR(255),
    `phone` VARCHAR(50),
    `idplace` int(11) NOT NULL,
    `created_at` timestamp NULL DEFAULT current_timestamp(),
    `updated_at` timestamp NULL DEFAULT NULL,
    PRIMARY KEY (`idplace_description`,`idplace`),
    KEY `fk_places_description_places1_idx` (`idplace`),
    CONSTRAINT `fk_places_description_places1` FOREIGN KEY (`idplace`) REFERENCES `places` (`idplace`) ON DELETE NO ACTION ON UPDATE NO ACTION
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;