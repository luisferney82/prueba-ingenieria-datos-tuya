"""Convierte la referencia de una imagen en un data URI con su contenido en base64."""

import base64
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlsplit

TAMANO_MAXIMO = 20 * 1024 * 1024  # 20 MB

# Firmas de los formatos más comunes. Con ellas se confirma que el contenido
# es de verdad una imagen y no se depende solo de la extensión.
FIRMAS = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
    (b"\x00\x00\x01\x00", "image/x-icon"),
)
TIPOS_CON_FIRMA = {tipo for _, tipo in FIRMAS} | {
    "image/webp",
    "image/svg+xml",
    "image/vnd.microsoft.icon",
}


class ErrorImagen(Exception):
    """La imagen no se pudo convertir. El mensaje explica el motivo."""


class CodificadorImagen:
    """Lee una imagen local o remota y la devuelve como data URI.

    Las rutas relativas se resuelven contra la carpeta del HTML que las usa,
    igual que lo haría un navegador.
    """

    def __init__(self, permitir_remotas: bool = True, timeout: float = 10.0) -> None:
        self._permitir_remotas = permitir_remotas
        self._timeout = timeout

    def codificar(self, src: str, carpeta_html: Path) -> str:
        src = src.strip()
        if not src:
            raise ErrorImagen("el atributo src está vacío")

        esquema = urlsplit(src).scheme.lower()
        if esquema == "data":
            raise ErrorImagen("la imagen ya viene embebida como data URI")
        if esquema in ("http", "https"):
            contenido, tipo_declarado = self._descargar(src)
        elif esquema in ("", "file") or len(esquema) == 1:
            # Un esquema de una letra es una unidad de Windows (C:\...).
            contenido, tipo_declarado = self._leer_local(src, carpeta_html)
        else:
            raise ErrorImagen(f"esquema no soportado: {esquema}")

        tipo = self._tipo_mime(contenido, tipo_declarado)
        codificado = base64.b64encode(contenido).decode("ascii")
        return f"data:{tipo};base64,{codificado}"

    def _leer_local(self, src: str, carpeta_html: Path) -> Tuple[bytes, Optional[str]]:
        partes = urlsplit(src)
        if partes.scheme.lower() == "file":
            ruta = Path(unquote(partes.path))
        elif len(partes.scheme) == 1:
            ruta = Path(src)
        else:
            ruta = Path(unquote(partes.path))
            if not ruta.is_absolute():
                ruta = carpeta_html / ruta

        if not ruta.is_file():
            raise ErrorImagen(f"no se encontró el archivo {ruta}")
        if ruta.stat().st_size > TAMANO_MAXIMO:
            raise ErrorImagen("la imagen supera el tamaño máximo permitido")
        try:
            contenido = ruta.read_bytes()
        except OSError as error:
            raise ErrorImagen(f"no se pudo leer el archivo: {error}") from error
        return contenido, mimetypes.guess_type(ruta.name)[0]

    def _descargar(self, url: str) -> Tuple[bytes, Optional[str]]:
        if not self._permitir_remotas:
            raise ErrorImagen("las imágenes remotas están deshabilitadas")

        solicitud = urllib.request.Request(url, headers={"User-Agent": "html-base64/1.0"})
        try:
            with urllib.request.urlopen(solicitud, timeout=self._timeout) as respuesta:
                contenido = respuesta.read(TAMANO_MAXIMO + 1)
                tipo = respuesta.headers.get_content_type()
        except (urllib.error.URLError, OSError, ValueError) as error:
            raise ErrorImagen(f"no se pudo descargar: {error}") from error

        if len(contenido) > TAMANO_MAXIMO:
            raise ErrorImagen("la imagen supera el tamaño máximo permitido")
        return contenido, tipo

    @staticmethod
    def _tipo_mime(contenido: bytes, tipo_declarado: Optional[str]) -> str:
        if not contenido:
            raise ErrorImagen("el archivo está vacío")
        for firma, tipo in FIRMAS:
            if contenido.startswith(firma):
                return tipo
        if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
            return "image/webp"
        if CodificadorImagen._es_svg(contenido):
            return "image/svg+xml"
        if (
            tipo_declarado
            and tipo_declarado.startswith("image/")
            and tipo_declarado not in TIPOS_CON_FIRMA
        ):
            # Formato del que no se revisa la firma (avif, tiff...). Se confía
            # en lo declarado. Si dice ser png o jpeg y la firma no coincide,
            # se rechaza.
            return tipo_declarado
        raise ErrorImagen("el contenido no corresponde a una imagen")

    @staticmethod
    def _es_svg(contenido: bytes) -> bool:
        # Un SVG empieza por <svg, o por la declaración XML, un comentario o
        # un DOCTYPE seguidos de <svg. Un HTML con un <svg> adentro no cuenta.
        inicio = contenido[:2048].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
        if inicio.startswith(b"<svg"):
            return True
        if inicio.startswith((b"<?xml", b"<!--", b"<!doctype svg")):
            return b"<svg" in inicio and b"<html" not in inicio
        return False
