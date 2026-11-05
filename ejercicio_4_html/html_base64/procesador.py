"""Une la búsqueda, la codificación y la reescritura, y arma el resultado."""

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .buscador import SUFIJO_GENERADO, ArchivoHtml, BuscadorHtml
from .codificador import CodificadorImagen, ErrorImagen
from .reescritor import EtiquetaImagen, ReescritorHtml

Resultado = Dict[str, Dict[str, list]]


class ProcesadorHtml:
    """Procesa los HTML y devuelve {"success": {...}, "fail": {...}}.

    Las dos llaves se indexan por la ruta del HTML. En success va la lista de
    src que se convirtieron, y en fail cada src que no se pudo convertir,
    junto con el motivo. El HTML original nunca se modifica: el resultado se
    escribe en un archivo nuevo con el sufijo .base64 (pagina.base64.html).
    """

    def __init__(
        self,
        buscador: Optional[BuscadorHtml] = None,
        codificador: Optional[CodificadorImagen] = None,
        reescritor: Optional[ReescritorHtml] = None,
        carpeta_salida: Optional[Path] = None,
    ) -> None:
        self._buscador = buscador or BuscadorHtml()
        self._codificador = codificador or CodificadorImagen()
        self._reescritor = reescritor or ReescritorHtml()
        self._carpeta_salida = carpeta_salida
        self._destinos_usados: Set[Path] = set()

    def procesar(self, rutas: Iterable[Path]) -> Resultado:
        resultado: Resultado = {"success": {}, "fail": {}}
        self._destinos_usados.clear()
        busqueda = self._buscador.buscar(rutas)

        for ruta in busqueda.rutas_invalidas:
            self._agregar_fallo(resultado, str(ruta), None, "la ruta no existe o no es un HTML")

        for archivo in busqueda.archivos:
            self._procesar_archivo(archivo, resultado)

        return resultado

    def _procesar_archivo(self, archivo: ArchivoHtml, resultado: Resultado) -> None:
        clave = str(archivo.ruta)
        try:
            html, codificacion = self._leer(archivo.ruta)
        except OSError as error:
            self._agregar_fallo(resultado, clave, None, f"no se pudo leer el HTML: {error}")
            return

        nuevos_src: Dict[EtiquetaImagen, str] = {}
        for etiqueta in self._reescritor.buscar_imagenes(html):
            if etiqueta.src is None:
                self._agregar_fallo(resultado, clave, None, "etiqueta <img> sin atributo src")
                continue
            try:
                nuevos_src[etiqueta] = self._codificador.codificar(
                    etiqueta.src, archivo.ruta.parent
                )
            except ErrorImagen as error:
                self._agregar_fallo(resultado, clave, etiqueta.src, str(error))
                continue
            resultado["success"].setdefault(clave, []).append(etiqueta.src)

        destino = self._ruta_salida(archivo)
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            # Se escribe en bytes para conservar los saltos de línea originales.
            nuevo_html = self._reescritor.reemplazar(html, nuevos_src)
            destino.write_bytes(nuevo_html.encode(codificacion))
        except OSError as error:
            # Si no se pudo escribir el archivo nuevo, ninguna de sus imágenes
            # quedó procesada de verdad.
            motivo = f"no se pudo escribir la salida: {error}"
            for src in resultado["success"].pop(clave, []):
                self._agregar_fallo(resultado, clave, src, motivo)

    @staticmethod
    def _leer(ruta: Path) -> Tuple[str, str]:
        datos = ruta.read_bytes()
        try:
            return datos.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            # latin-1 acepta cualquier byte, así que el archivo se reescribe sin
            # perder caracteres aunque no venga en UTF-8.
            return datos.decode("latin-1"), "latin-1"

    def _ruta_salida(self, archivo: ArchivoHtml) -> Path:
        nombre = f"{archivo.ruta.stem}{SUFIJO_GENERADO}{archivo.ruta.suffix}"
        if self._carpeta_salida is None:
            return archivo.ruta.with_name(nombre)

        destino = self._carpeta_salida / archivo.ruta_relativa.with_name(nombre)
        # Dos entradas pueden llegar al mismo destino, por ejemplo a/index.html
        # y b/index.html pasados como archivos sueltos. En ese caso se numera
        # el segundo para no sobrescribir el primero.
        contador = 2
        while destino in self._destinos_usados:
            destino = destino.with_name(
                f"{archivo.ruta.stem}_{contador}{SUFIJO_GENERADO}{archivo.ruta.suffix}"
            )
            contador += 1
        self._destinos_usados.add(destino)
        return destino

    @staticmethod
    def _agregar_fallo(resultado: Resultado, clave: str, src: Optional[str], motivo: str) -> None:
        fallos: List[dict] = resultado["fail"].setdefault(clave, [])
        fallos.append({"src": src, "motivo": motivo})
