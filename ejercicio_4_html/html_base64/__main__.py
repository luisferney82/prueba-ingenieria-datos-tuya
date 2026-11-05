"""Línea de comandos.

    python -m html_base64 pagina.html otra_carpeta/ --salida salida/ --reporte reporte.json
"""

import argparse
import json
import sys
from pathlib import Path

from .codificador import CodificadorImagen
from .procesador import ProcesadorHtml


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="html_base64",
        description="Reemplaza las imágenes de archivos HTML por su versión en base64.",
    )
    parser.add_argument("rutas", nargs="+", type=Path, help="archivos HTML o directorios")
    parser.add_argument(
        "--salida", type=Path,
        help="carpeta donde se escriben los HTML nuevos (por defecto, junto al original)",
    )
    parser.add_argument("--reporte", type=Path, help="guarda el resultado en un JSON")
    parser.add_argument("--sin-remotas", action="store_true", help="no descarga imágenes http(s)")
    parser.add_argument("--timeout", type=float, default=10.0, help="segundos por descarga")
    return parser


def main(argv=None) -> int:
    args = crear_parser().parse_args(argv)
    procesador = ProcesadorHtml(
        codificador=CodificadorImagen(not args.sin_remotas, args.timeout),
        carpeta_salida=args.salida,
    )
    resultado = procesador.procesar(args.rutas)

    salida = json.dumps(resultado, indent=2, ensure_ascii=False)
    print(salida)
    if args.reporte:
        args.reporte.write_text(salida + "\n", encoding="utf-8")

    return 1 if resultado["fail"] and not resultado["success"] else 0


if __name__ == "__main__":
    sys.exit(main())
