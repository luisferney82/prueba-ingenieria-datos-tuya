"""Convierte las imágenes de archivos HTML a base64, sin modificar los originales."""

from .buscador import BuscadorHtml
from .codificador import CodificadorImagen, ErrorImagen
from .procesador import ProcesadorHtml
from .reescritor import ReescritorHtml

__all__ = [
    "BuscadorHtml",
    "CodificadorImagen",
    "ErrorImagen",
    "ProcesadorHtml",
    "ReescritorHtml",
]
