"""Localiza los archivos HTML a partir de rutas de archivos o directorios."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

EXTENSIONES_HTML = (".html", ".htm")
SUFIJO_GENERADO = ".base64"


@dataclass(frozen=True)
class ArchivoHtml:
    """Un HTML encontrado y la carpeta desde la que se encontró.

    La carpeta base sirve para replicar la estructura de subdirectorios
    cuando los resultados se escriben en otra carpeta.
    """

    ruta: Path
    base: Path

    @property
    def ruta_relativa(self) -> Path:
        return self.ruta.relative_to(self.base)


@dataclass
class ResultadoBusqueda:
    archivos: List[ArchivoHtml]
    rutas_invalidas: List[Path]


class BuscadorHtml:
    """Recibe una mezcla de archivos y directorios y devuelve los HTML a procesar.

    Los directorios se recorren completos, incluyendo subdirectorios. Se
    ignoran los archivos que este mismo proceso generó en una corrida anterior,
    para no volver a procesar lo ya procesado.
    """

    def buscar(self, rutas: Iterable[Path]) -> ResultadoBusqueda:
        encontrados: List[ArchivoHtml] = []
        invalidas: List[Path] = []
        vistos = set()

        for ruta in map(Path, rutas):
            if ruta.is_dir():
                candidatos = [
                    ArchivoHtml(p.resolve(), ruta.resolve())
                    for p in sorted(ruta.rglob("*"))
                    if p.is_file() and self._es_html(p)
                ]
            elif ruta.is_file() and self._es_html(ruta):
                candidatos = [ArchivoHtml(ruta.resolve(), ruta.resolve().parent)]
            else:
                invalidas.append(ruta)
                continue

            for archivo in candidatos:
                if archivo.ruta not in vistos:
                    vistos.add(archivo.ruta)
                    encontrados.append(archivo)

        return ResultadoBusqueda(encontrados, invalidas)

    @staticmethod
    def _es_html(ruta: Path) -> bool:
        return (
            ruta.suffix.lower() in EXTENSIONES_HTML
            and not ruta.stem.endswith(SUFIJO_GENERADO)
        )
