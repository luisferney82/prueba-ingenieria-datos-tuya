-- Paso de staging a tablas limpias.
--
-- Cada fila de staging termina en una de dos partes: en la tabla limpia, o
-- en dq_incidencias con la regla que incumplió. Hay casos que quedan en las
-- dos, porque el dato se corrige o se usa con alguna salvedad, y en ese
-- caso la incidencia lo deja dicho en la columna accion.

-------------------------------------------------------------------------------
-- 1. historia
-------------------------------------------------------------------------------

DROP TABLE IF EXISTS tmp_historia;

CREATE TEMP TABLE tmp_historia AS
WITH normalizada AS (
    SELECT
        fila_origen,
        upper(trim(identificacion))                                AS identificacion,
        date(corte_mes)                                            AS corte_original,
        date(corte_mes, 'start of month', '+1 month', '-1 day')    AS corte_mes,
        saldo
    FROM stg_historia
)
SELECT
    fila_origen,
    identificacion,
    corte_original,
    corte_mes,
    saldo,
    CASE
        WHEN identificacion IS NULL OR identificacion = ''          THEN 'identificacion_vacia'
        WHEN length(identificacion) <> 17
          OR identificacion GLOB '*[^A-Z0-9]*'                      THEN 'identificacion_formato_invalido'
        WHEN corte_original IS NULL                                 THEN 'corte_mes_invalido'
        WHEN saldo IS NULL OR typeof(saldo) NOT IN ('integer', 'real') THEN 'saldo_no_numerico'
        WHEN saldo < 0                                              THEN 'saldo_negativo'
    END AS motivo_rechazo
FROM normalizada;

INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT 'historia', fila_origen, identificacion, motivo_rechazo, 'rechazada',
       'corte=' || coalesce(corte_original, 'NULL') || ' saldo=' || coalesce(saldo, 'NULL')
FROM tmp_historia
WHERE motivo_rechazo IS NOT NULL;

-- Si el corte viene con un día distinto al último del mes, se lleva a fin de mes.
INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT 'historia', fila_origen, identificacion, 'corte_no_fin_de_mes', 'corregida',
       corte_original || ' -> ' || corte_mes
FROM tmp_historia
WHERE motivo_rechazo IS NULL
  AND corte_original <> corte_mes;

-- Duplicados por cliente y corte. Si las filas son idénticas se conserva una.
-- Si los saldos difieren se conserva el menor. En el archivo recibido el único
-- conflicto tiene un saldo que es exactamente el doble del otro, que es lo que
-- se ve cuando un registro se suma dos veces en el origen.
DROP TABLE IF EXISTS tmp_historia_rankeada;

CREATE TEMP TABLE tmp_historia_rankeada AS
SELECT
    fila_origen,
    identificacion,
    corte_mes,
    saldo,
    ROW_NUMBER() OVER (PARTITION BY identificacion, corte_mes
                       ORDER BY saldo, fila_origen) AS orden
FROM tmp_historia
WHERE motivo_rechazo IS NULL;

INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT
    'historia',
    descartada.fila_origen,
    descartada.identificacion,
    CASE WHEN descartada.saldo = conservada.saldo THEN 'duplicado_exacto'
         ELSE 'duplicado_con_conflicto' END,
    'descartada',
    'corte=' || descartada.corte_mes
        || ' saldo_descartado=' || descartada.saldo
        || ' saldo_conservado=' || conservada.saldo
        || ' fila_conservada=' || conservada.fila_origen
FROM tmp_historia_rankeada AS descartada
JOIN tmp_historia_rankeada AS conservada
  ON  conservada.identificacion = descartada.identificacion
  AND conservada.corte_mes      = descartada.corte_mes
  AND conservada.orden          = 1
WHERE descartada.orden > 1;

INSERT INTO historia (identificacion, corte_mes, saldo)
SELECT identificacion, corte_mes, saldo
FROM tmp_historia_rankeada
WHERE orden = 1;

-------------------------------------------------------------------------------
-- 2. retiros
-------------------------------------------------------------------------------

DROP TABLE IF EXISTS tmp_retiros;

CREATE TEMP TABLE tmp_retiros AS
WITH normalizada AS (
    SELECT
        fila_origen,
        upper(trim(identificacion)) AS identificacion,
        date(fecha_retiro)          AS fecha_retiro
    FROM stg_retiros
)
SELECT
    n.fila_origen,
    n.identificacion,
    n.fecha_retiro,
    CASE
        WHEN n.identificacion IS NULL OR n.identificacion = ''      THEN 'identificacion_vacia'
        WHEN length(n.identificacion) <> 17
          OR n.identificacion GLOB '*[^A-Z0-9]*'                    THEN 'identificacion_formato_invalido'
        WHEN n.fecha_retiro IS NULL                                 THEN 'fecha_retiro_invalida'
        WHEN NOT EXISTS (SELECT 1 FROM historia AS h
                         WHERE h.identificacion = n.identificacion) THEN 'retiro_sin_historia'
    END AS motivo_rechazo,
    ROW_NUMBER() OVER (PARTITION BY n.identificacion
                       ORDER BY n.fecha_retiro, n.fila_origen) AS orden
FROM normalizada AS n;

INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT 'retiros', fila_origen, identificacion, motivo_rechazo, 'rechazada',
       'fecha_retiro=' || coalesce(fecha_retiro, 'NULL')
FROM tmp_retiros
WHERE motivo_rechazo IS NOT NULL;

-- Si un cliente tuviera dos retiros, cuenta el primero.
INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT 'retiros', fila_origen, identificacion, 'retiro_duplicado', 'descartada',
       'fecha_retiro=' || fecha_retiro
FROM tmp_retiros
WHERE motivo_rechazo IS NULL
  AND orden > 1;

INSERT INTO retiros (identificacion, fecha_retiro)
SELECT identificacion, fecha_retiro
FROM tmp_retiros
WHERE motivo_rechazo IS NULL
  AND orden = 1;

-------------------------------------------------------------------------------
-- 3. Saldos reportados después del retiro
-------------------------------------------------------------------------------
-- Las filas siguen en historia, pero la consulta de rachas no las tiene en
-- cuenta, porque a partir de la fecha de retiro el cliente sale del cálculo.

INSERT INTO dq_incidencias (tabla_origen, fila_origen, identificacion, regla, accion, detalle)
SELECT 'historia', r.fila_origen, h.identificacion, 'saldo_posterior_al_retiro',
       'excluida_del_calculo',
       'corte=' || h.corte_mes || ' fecha_retiro=' || rt.fecha_retiro || ' saldo=' || h.saldo
FROM historia AS h
JOIN retiros  AS rt ON rt.identificacion = h.identificacion
JOIN tmp_historia_rankeada AS r
  ON  r.identificacion = h.identificacion
  AND r.corte_mes      = h.corte_mes
  AND r.orden          = 1
WHERE h.corte_mes > rt.fecha_retiro;

DROP TABLE tmp_historia;
DROP TABLE tmp_historia_rankeada;
DROP TABLE tmp_retiros;
