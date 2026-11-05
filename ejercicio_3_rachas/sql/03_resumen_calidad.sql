-- Resumen de lo que dejó la carga: cuántas filas entraron y qué pasó con las que no.

SELECT 'stg_historia' AS tabla, count(*) AS filas FROM stg_historia
UNION ALL SELECT 'historia',     count(*) FROM historia
UNION ALL SELECT 'stg_retiros',  count(*) FROM stg_retiros
UNION ALL SELECT 'retiros',      count(*) FROM retiros;

SELECT
    tabla_origen,
    regla,
    accion,
    count(*) AS filas
FROM dq_incidencias
GROUP BY tabla_origen, regla, accion
ORDER BY tabla_origen, regla;

SELECT
    tabla_origen,
    fila_origen,
    identificacion,
    regla,
    accion,
    detalle
FROM dq_incidencias
ORDER BY tabla_origen, regla, identificacion, fila_origen;
