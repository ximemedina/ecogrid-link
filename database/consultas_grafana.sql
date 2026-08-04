-- Consultas de referencia para los paneles de Grafana.
-- Ya están cargadas en el dashboard auto-provisionado
-- (grafana/provisioning/dashboards/ecogrid_dashboard.json). Este archivo es
-- para copiar/pegar si agregas paneles nuevos o quieres ajustarlos.

-- 1) Serie de tiempo: potencia (W) por nodo
SELECT
    fecha_hora AS "time",
    potencia_watts AS "value",
    id_nodo AS "metric"
FROM historico_mediciones
WHERE $__timeFilter(fecha_hora)
ORDER BY fecha_hora ASC;

-- 2) Stat: potencia total actual (suma de la última lectura de cada nodo)
SELECT COALESCE(SUM(h.potencia_watts), 0) AS "Potencia Total"
FROM historico_mediciones h
INNER JOIN (
    SELECT id_nodo, MAX(fecha_hora) AS ultima
    FROM historico_mediciones
    GROUP BY id_nodo
) m ON h.id_nodo = m.id_nodo AND h.fecha_hora = m.ultima;

-- 3) Tabla: última lectura por nodo, con zona y tipo
SELECT
    h.id_nodo,
    n.zona,
    n.tipo_nodo,
    h.voltaje,
    h.corriente,
    h.potencia_watts,
    h.fecha_hora
FROM historico_mediciones h
INNER JOIN (
    SELECT id_nodo, MAX(fecha_hora) AS ultima
    FROM historico_mediciones
    GROUP BY id_nodo
) m ON h.id_nodo = m.id_nodo AND h.fecha_hora = m.ultima
LEFT JOIN nodos n ON n.id_nodo = h.id_nodo
ORDER BY h.potencia_watts DESC;

-- 4) Barras: consumo acumulado por zona en la última hora
SELECT
    COALESCE(n.zona, 'Sin registrar') AS metric,
    SUM(h.potencia_watts) AS value
FROM historico_mediciones h
LEFT JOIN nodos n ON n.id_nodo = h.id_nodo
WHERE h.fecha_hora >= NOW() - INTERVAL 1 HOUR
GROUP BY metric
ORDER BY value DESC;
