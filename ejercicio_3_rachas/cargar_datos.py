"""Carga Rachas.xlsx en una base SQLite y aplica las reglas de calidad.

Uso:
    python ejercicio_3_rachas/cargar_datos.py
    python ejercicio_3_rachas/cargar_datos.py --excel ejercicio_3_rachas/datos/Rachas.xlsx --db rachas.db
"""

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path
from typing import Iterator, List, Sequence, Tuple

from openpyxl import load_workbook

RAIZ = Path(__file__).resolve().parent
SQL_DIR = RAIZ / "sql"
EXCEL_POR_DEFECTO = RAIZ / "datos" / "Rachas.xlsx"
DB_POR_DEFECTO = RAIZ / "rachas.db"

HOJAS = {
    "historia": ("identificacion", "corte_mes", "saldo"),
    "retiros": ("identificacion", "fecha_retiro"),
}


def a_texto_fecha(valor):
    """Las fechas se guardan como texto ISO, que es lo que entiende SQLite."""
    if isinstance(valor, dt.datetime):
        return valor.date().isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    return valor


def leer_hoja(libro, nombre: str, columnas: Sequence[str]) -> Iterator[Tuple]:
    """Devuelve (fila_excel, valores...) por cada fila con datos."""
    if nombre not in libro.sheetnames:
        raise ValueError(f"El archivo no tiene la hoja '{nombre}'")

    hoja = libro[nombre]
    filas = hoja.iter_rows(values_only=True)
    primera = next(filas, None)
    if primera is None:
        raise ValueError(f"La hoja '{nombre}' está vacía")

    encabezado = tuple(str(c).strip().lower() if c is not None else "" for c in primera)
    if encabezado[: len(columnas)] != tuple(columnas):
        raise ValueError(
            f"Encabezado inesperado en '{nombre}': {encabezado}, se esperaba {columnas}"
        )

    for numero, fila in enumerate(filas, start=2):
        # En modo de solo lectura una fila puede traer menos celdas que columnas.
        valores = tuple(fila[: len(columnas)]) + (None,) * (len(columnas) - len(fila))
        if all(v is None for v in valores):
            continue
        yield (numero,) + tuple(a_texto_fecha(v) for v in valores)


def ejecutar_script(conexion: sqlite3.Connection, nombre: str) -> None:
    conexion.executescript((SQL_DIR / nombre).read_text(encoding="utf-8"))


def cargar(excel: Path, db: Path) -> None:
    libro = load_workbook(excel, read_only=True, data_only=True)
    historia: List[Tuple] = list(leer_hoja(libro, "historia", HOJAS["historia"]))
    retiros: List[Tuple] = list(leer_hoja(libro, "retiros", HOJAS["retiros"]))
    libro.close()

    with sqlite3.connect(db) as conexion:
        ejecutar_script(conexion, "00_esquema.sql")
        conexion.executemany(
            "INSERT INTO stg_historia (fila_origen, identificacion, corte_mes, saldo) "
            "VALUES (?, ?, ?, ?)",
            historia,
        )
        conexion.executemany(
            "INSERT INTO stg_retiros (fila_origen, identificacion, fecha_retiro) "
            "VALUES (?, ?, ?)",
            retiros,
        )
        ejecutar_script(conexion, "01_limpieza.sql")
        imprimir_resumen(conexion)


def imprimir_resumen(conexion: sqlite3.Connection) -> None:
    conteos = conexion.execute(
        "SELECT (SELECT count(*) FROM stg_historia), (SELECT count(*) FROM historia), "
        "(SELECT count(*) FROM stg_retiros), (SELECT count(*) FROM retiros)"
    ).fetchone()
    print(f"historia: {conteos[0]} filas leídas, {conteos[1]} cargadas")
    print(f"retiros:  {conteos[2]} filas leídas, {conteos[3]} cargadas")

    incidencias = conexion.execute(
        "SELECT tabla_origen, regla, accion, count(*) FROM dq_incidencias "
        "GROUP BY tabla_origen, regla, accion ORDER BY tabla_origen, regla"
    ).fetchall()
    if incidencias:
        print("\nIncidencias de calidad:")
        for tabla, regla, accion, filas in incidencias:
            print(f"  {tabla:<9} {regla:<32} {accion:<21} {filas}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--excel", type=Path, default=EXCEL_POR_DEFECTO)
    parser.add_argument("--db", type=Path, default=DB_POR_DEFECTO)
    args = parser.parse_args(argv)

    if not args.excel.is_file():
        print(f"No se encontró el archivo {args.excel}", file=sys.stderr)
        return 1

    try:
        cargar(args.excel, args.db)
    except ValueError as error:
        print(f"No se pudo cargar el archivo: {error}", file=sys.stderr)
        return 1
    print(f"\nBase creada en {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
