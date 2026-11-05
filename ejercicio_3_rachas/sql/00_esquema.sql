-- Esquema de la base de rachas (SQLite).
--
-- Hay dos capas:
--   stg_*   copia fiel del Excel, sin reglas, con el número de fila de origen
--           para poder rastrear cualquier dato hasta la hoja.
--   historia / retiros   datos ya validados, que son los que usa la consulta.
-- Lo que no pasa las validaciones queda registrado en dq_incidencias.
--
-- El script es idempotente: borra y recrea todo en cada carga.

DROP TABLE IF EXISTS dq_incidencias;
DROP TABLE IF EXISTS historia;
DROP TABLE IF EXISTS retiros;
DROP TABLE IF EXISTS stg_historia;
DROP TABLE IF EXISTS stg_retiros;

CREATE TABLE stg_historia (
    fila_origen     INTEGER PRIMARY KEY,
    identificacion  TEXT,
    corte_mes       TEXT,
    saldo           NUMERIC
);

CREATE TABLE stg_retiros (
    fila_origen     INTEGER PRIMARY KEY,
    identificacion  TEXT,
    fecha_retiro    TEXT
);

CREATE TABLE historia (
    identificacion  TEXT    NOT NULL,
    corte_mes       TEXT    NOT NULL,
    -- NUMERIC y no INTEGER: redondear un 299,999.6 lo pasaría de N0 a N1.
    saldo           NUMERIC NOT NULL,
    PRIMARY KEY (identificacion, corte_mes),
    CHECK (length(identificacion) = 17),
    CHECK (saldo >= 0),
    -- corte_mes debe ser un último día de mes en formato AAAA-MM-DD
    CHECK (corte_mes = date(corte_mes, 'start of month', '+1 month', '-1 day'))
) WITHOUT ROWID;

CREATE TABLE retiros (
    identificacion  TEXT NOT NULL PRIMARY KEY,
    fecha_retiro    TEXT NOT NULL,
    CHECK (fecha_retiro = date(fecha_retiro))
) WITHOUT ROWID;

CREATE TABLE dq_incidencias (
    id_incidencia   INTEGER PRIMARY KEY,
    tabla_origen    TEXT NOT NULL,
    fila_origen     INTEGER,
    identificacion  TEXT,
    regla           TEXT NOT NULL,
    accion          TEXT NOT NULL,
    detalle         TEXT
);

CREATE INDEX ix_historia_corte ON historia (corte_mes);
CREATE INDEX ix_dq_regla ON dq_incidencias (regla);
