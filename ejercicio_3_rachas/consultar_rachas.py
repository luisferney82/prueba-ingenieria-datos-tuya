"""Ejecuta la consulta de rachas para una fecha_base y un n.

Uso:
    python ejercicio_3_rachas/consultar_rachas.py --fecha-base 2024-12-31 --n 3
    python ejercicio_3_rachas/consultar_rachas.py --fecha-base 2024-06-15 --n 2 --csv salida.csv
"""

import argparse
import csv
import datetime as dt
import sqlite3
import sys
from pathlib import Path
from typing import List, Tuple

RAIZ = Path(__file__).resolve().parent
CONSULTA = RAIZ / "sql" / "02_rachas.sql"
DB_POR_DEFECTO = RAIZ / "rachas.db"
COLUMNAS = ("identificacion", "racha", "fecha_fin", "nivel")


def fecha_valida(texto: str) -> str:
    try:
        return dt.date.fromisoformat(texto).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{texto}' no es una fecha AAAA-MM-DD")


def entero_positivo(texto: str) -> int:
    valor = int(texto)
    if valor < 1:
        raise argparse.ArgumentTypeError("n debe ser mayor o igual a 1")
    return valor


def consultar(db: Path, fecha_base: str, n: int) -> List[Tuple]:
    consulta = CONSULTA.read_text(encoding="utf-8")
    with sqlite3.connect(db) as conexion:
        return conexion.execute(consulta, {"fecha_base": fecha_base, "n": n}).fetchall()


def imprimir(filas: List[Tuple]) -> None:
    print(f"{COLUMNAS[0]:<20}{COLUMNAS[1]:>6}  {COLUMNAS[2]:<11} {COLUMNAS[3]}")
    for identificacion, racha, fecha_fin, nivel in filas:
        print(f"{identificacion:<20}{racha:>6}  {fecha_fin:<11} {nivel}")
    print(f"\n{len(filas)} clientes")


def guardar_csv(filas: List[Tuple], destino: Path) -> None:
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS)
        escritor.writerows(filas)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fecha-base", required=True, type=fecha_valida)
    parser.add_argument("--n", required=True, type=entero_positivo)
    parser.add_argument("--db", type=Path, default=DB_POR_DEFECTO)
    parser.add_argument("--csv", type=Path, help="guarda el resultado en un CSV")
    args = parser.parse_args(argv)

    if not args.db.is_file():
        print(f"No existe {args.db}. Primero corra cargar_datos.py", file=sys.stderr)
        return 1

    filas = consultar(args.db, args.fecha_base, args.n)
    if args.csv:
        guardar_csv(filas, args.csv)
        print(f"{len(filas)} filas guardadas en {args.csv}")
    else:
        imprimir(filas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
