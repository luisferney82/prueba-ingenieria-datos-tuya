-- Rachas de nivel de deuda por cliente, calculadas a una fecha_base.
--
-- Parámetros:
--   :fecha_base  fecha 'AAAA-MM-DD' en la que nos "paramos". No tiene que ser
--                fin de mes; se usan los cortes menores o iguales a ella.
--   :n           longitud mínima de racha (meses), entero mayor o igual a 1.
--
-- Desde la consola de sqlite3:
--   .parameter set :fecha_base "'2024-12-31'"
--   .parameter set :n 3
--   .read ejercicio_3_rachas/sql/02_rachas.sql
-- La fecha va entre comillas dobles y simples. Si se escribe 2024-12-31 sin
-- comillas, sqlite la toma como una resta y queda el número 1981.

WITH parametros AS (
    SELECT
        date(:fecha_base)     AS fecha_base,
        CAST(:n AS INTEGER)   AS n
),

-- Último corte que entra al cálculo. Es el último fin de mes que no supera
-- fecha_base, sin pasar del último corte cargado. Lo segundo evita que se
-- imputen N0 en meses de los que todavía no hay información.
corte_limite AS (
    SELECT min(
               date(p.fecha_base, '+1 day', 'start of month', '-1 day'),
               (SELECT max(corte_mes) FROM historia)
           ) AS corte_final
    FROM parametros AS p
),

-- Primer corte en que aparece cada cliente, mirando solo lo conocido a fecha_base.
primera_aparicion AS (
    SELECT
        h.identificacion,
        min(h.corte_mes) AS primer_corte
    FROM historia AS h
    CROSS JOIN corte_limite AS cl
    WHERE h.corte_mes <= cl.corte_final
    GROUP BY h.identificacion
),

-- Todos los fines de mes entre el primer corte conocido y el corte final.
-- Se genera aparte para no depender de que todos los meses vengan en el archivo.
calendario (corte_mes) AS (
    SELECT min(primer_corte) FROM primera_aparicion
    UNION ALL
    SELECT date(c.corte_mes, 'start of month', '+2 months', '-1 day')
    FROM calendario AS c
    CROSS JOIN corte_limite AS cl
    WHERE c.corte_mes < cl.corte_final
),

-- Solo cuentan los retiros que ya habían ocurrido en fecha_base.
retiros_conocidos AS (
    SELECT r.identificacion, r.fecha_retiro
    FROM retiros AS r
    CROSS JOIN parametros AS p
    WHERE r.fecha_retiro <= p.fecha_base
),

-- Una fila por cliente y mes, desde su primera aparición. Se quitan los cortes
-- posteriores a la fecha de retiro: ahí no se imputa N0 y tampoco se usan los
-- saldos que lleguen reportados (quedan en dq_incidencias).
malla AS (
    SELECT
        pa.identificacion,
        c.corte_mes
    FROM primera_aparicion AS pa
    JOIN calendario AS c
      ON c.corte_mes >= pa.primer_corte
    LEFT JOIN retiros_conocidos AS rc
      ON rc.identificacion = pa.identificacion
    WHERE rc.fecha_retiro IS NULL
       OR c.corte_mes <= rc.fecha_retiro
),

-- Nivel de cada mes. Un mes sin saldo reportado se toma como N0.
niveles AS (
    SELECT
        m.identificacion,
        m.corte_mes,
        CAST(strftime('%Y', m.corte_mes) AS INTEGER) * 12
            + CAST(strftime('%m', m.corte_mes) AS INTEGER) AS indice_mes,
        CASE
            WHEN h.saldo IS NULL      THEN 'N0'
            WHEN h.saldo <   300000   THEN 'N0'
            WHEN h.saldo <  1000000   THEN 'N1'
            WHEN h.saldo <  3000000   THEN 'N2'
            WHEN h.saldo <  5000000   THEN 'N3'
            ELSE                           'N4'
        END AS nivel
    FROM malla AS m
    LEFT JOIN historia AS h
      ON  h.identificacion = m.identificacion
      AND h.corte_mes      = m.corte_mes
),

-- Meses seguidos en un mismo nivel. Dentro de una racha, el índice del mes y
-- el número de fila por (cliente, nivel) avanzan juntos, así que su diferencia
-- se mantiene constante y sirve para identificar la racha.
grupos AS (
    SELECT
        identificacion,
        corte_mes,
        nivel,
        indice_mes - ROW_NUMBER() OVER (
            PARTITION BY identificacion, nivel
            ORDER BY corte_mes
        ) AS grupo
    FROM niveles
),

rachas AS (
    SELECT
        identificacion,
        nivel,
        count(*)       AS racha,
        max(corte_mes) AS fecha_fin
    FROM grupos
    GROUP BY identificacion, nivel, grupo
),

-- Entre las rachas que llegan a n, gana la más larga. Si hay empate, gana la
-- que termina más cerca de fecha_base.
seleccion AS (
    SELECT
        r.identificacion,
        r.racha,
        r.fecha_fin,
        r.nivel,
        ROW_NUMBER() OVER (
            PARTITION BY r.identificacion
            ORDER BY r.racha DESC, r.fecha_fin DESC
        ) AS prioridad
    FROM rachas AS r
    CROSS JOIN parametros AS p
    WHERE r.racha >= p.n
)

SELECT
    identificacion,
    racha,
    fecha_fin,
    nivel
FROM seleccion
WHERE prioridad = 1
ORDER BY identificacion;
