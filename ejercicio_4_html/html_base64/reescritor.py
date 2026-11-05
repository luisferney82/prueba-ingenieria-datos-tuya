"""Ubica las etiquetas <img> de un HTML y les reemplaza el src."""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Dict, List, Optional

# Nombre de la etiqueta y cada atributo con su valor, en el orden en que
# aparecen. Se recorren uno por uno para que un texto como "src=" dentro del
# valor de otro atributo (un alt, por ejemplo) no se confunda con el src real.
PATRON_NOMBRE_ETIQUETA = re.compile(r"<\s*[^\s/>]+")
PATRON_ATRIBUTO = re.compile(
    r"""([^\s"'>/=]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s"'=<>`]+))?"""
)


@dataclass(frozen=True)
class EtiquetaImagen:
    inicio: int          # posición de la etiqueta en el texto del HTML
    texto: str           # la etiqueta tal como está escrita
    src: Optional[str]   # valor del atributo, ya sin entidades HTML


class _ExtractorImagenes(HTMLParser):
    def __init__(self, inicios_linea: List[int]) -> None:
        super().__init__(convert_charrefs=True)
        self._inicios_linea = inicios_linea
        self.etiquetas: List[EtiquetaImagen] = []

    def handle_starttag(self, tag, attrs):
        if tag != "img":
            return
        linea, columna = self.getpos()
        src = next((valor for nombre, valor in attrs if nombre == "src"), None)
        self.etiquetas.append(
            EtiquetaImagen(
                inicio=self._inicios_linea[linea - 1] + columna,
                texto=self.get_starttag_text(),
                src=src,
            )
        )

    handle_startendtag = handle_starttag


class ReescritorHtml:
    """Hace los reemplazos sobre el texto original.

    No vuelve a generar el documento. Solo cambia el valor del src, así que
    el resto del HTML (espacios, comentarios, mayúsculas, orden de los
    atributos) queda tal cual estaba.
    """

    def buscar_imagenes(self, html: str) -> List[EtiquetaImagen]:
        # HTMLParser cuenta las líneas por "\n", así que se usa el mismo criterio.
        inicios = [0] + [m.end() for m in re.finditer("\n", html)]
        extractor = _ExtractorImagenes(inicios)
        extractor.feed(html)
        extractor.close()
        return extractor.etiquetas

    def reemplazar(self, html: str, nuevos_src: Dict[EtiquetaImagen, str]) -> str:
        partes: List[str] = []
        cursor = 0
        for etiqueta in sorted(nuevos_src, key=lambda e: e.inicio):
            fin = etiqueta.inicio + len(etiqueta.texto)
            if html[etiqueta.inicio:fin] != etiqueta.texto:
                raise ValueError(f"La etiqueta en la posición {etiqueta.inicio} no coincide")
            partes.append(html[cursor:etiqueta.inicio])
            partes.append(self._cambiar_src(etiqueta.texto, nuevos_src[etiqueta]))
            cursor = fin
        partes.append(html[cursor:])
        return "".join(partes)

    @staticmethod
    def _cambiar_src(etiqueta: str, nuevo_src: str) -> str:
        inicio = PATRON_NOMBRE_ETIQUETA.match(etiqueta).end()
        for atributo in PATRON_ATRIBUTO.finditer(etiqueta, inicio):
            if atributo.group(1).lower() == "src" and atributo.group(2) is not None:
                return (
                    etiqueta[:atributo.start(2)]
                    + f'"{nuevo_src}"'
                    + etiqueta[atributo.end(2):]
                )
        raise ValueError(f"No se encontró el atributo src en {etiqueta[:60]}")
