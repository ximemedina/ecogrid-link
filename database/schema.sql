-- EcoGrid-Link — Esquema de referencia para phpMyAdmin
-- Rol: Integrante 2 (Datos y Visualización)
--
-- El backend (FastAPI) ya crea estas tablas automáticamente al arrancar
-- (SQLAlchemy `Base.metadata.create_all`), así que en un stack recién
-- levantado NO hace falta correr este script. Se incluye como referencia
-- documentada del modelo de datos y como script reproducible si necesitas
-- recrear la base desde phpMyAdmin en un volumen de MySQL vacío.

CREATE TABLE IF NOT EXISTS nodos (
    id_nodo             VARCHAR(50)  NOT NULL,
    zona                VARCHAR(50)  NOT NULL,
    tipo_nodo           VARCHAR(30)  NOT NULL, -- generacion | consumo_prioritario | consumo_no_prioritario
    limite_alerta_watts FLOAT        DEFAULT 100.0,
    PRIMARY KEY (id_nodo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS historico_mediciones (
    id_medicion    INT AUTO_INCREMENT,
    id_nodo        VARCHAR(50) NOT NULL,
    voltaje        FLOAT       NOT NULL,
    corriente      FLOAT       NOT NULL,
    potencia_watts FLOAT       NOT NULL, -- calculado por el backend (P = V * I) al insertar
    fecha_hora     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_medicion),
    KEY idx_historico_id_nodo (id_nodo),
    KEY idx_historico_fecha_hora (fecha_hora)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Nota sobre integridad referencial:
-- A propósito NO se agregó una FOREIGN KEY estricta de
-- historico_mediciones.id_nodo hacia nodos.id_nodo: el backend inserta
-- telemetría en cuanto llega por MQTT, incluso si ese nodo todavía no fue
-- registrado con POST /api/nodos (por ejemplo la primera vez que se
-- enciende un ESP32 nuevo). Si tu equipo garantiza que todos los nodos se
-- registran antes de emitir telemetría, puedes activarla con:
--
--   ALTER TABLE historico_mediciones
--     ADD CONSTRAINT fk_historico_nodo FOREIGN KEY (id_nodo)
--     REFERENCES nodos(id_nodo) ON DELETE CASCADE;

-- Datos semilla de ejemplo (opcional) — reflejan los 4 nodos reales de la
-- maqueta física: hospital, estación de bomberos y dos casas. Hospital y
-- bomberos son cargas críticas (consumo_prioritario, nunca se desconectan);
-- las casas son consumo_no_prioritario (candidatas a desconexión automática
-- si hay sobrecarga). Útil para ver algo en Grafana/phpMyAdmin sin esperar
-- a que el ESP32 o el simulador empiecen a publicar.
INSERT INTO nodos (id_nodo, zona, tipo_nodo, limite_alerta_watts) VALUES
    ('hospital', 'Hospital', 'consumo_prioritario', 100.0),
    ('bomberos', 'Bomberos', 'consumo_prioritario', 100.0),
    ('casa1', 'Casa 1', 'consumo_no_prioritario', 50.0),
    ('casa2', 'Casa 2', 'consumo_no_prioritario', 50.0)
ON DUPLICATE KEY UPDATE zona = VALUES(zona);
