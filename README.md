# Prueba de Ingeniería de Datos, Tuya

Solución a los cuatro ejercicios de la prueba. Cada uno está en su propia carpeta, con todo lo necesario para revisarlo o ejecutarlo.

| Ejercicio | Carpeta | Qué contiene |
|---|---|---|
| 1. Dataset de teléfonos con CI/CD | [ejercicio_1_dataset_telefonos](ejercicio_1_dataset_telefonos/README.md) | Diseño del dataset y del proceso, con un workflow de ejemplo |
| 2. Veeduría de calidad y KPIs | [ejercicio_2_kpis_calidad](ejercicio_2_kpis_calidad/README.md) | Indicadores, trazabilidad y tablero para negocio |
| 3. Rachas | [ejercicio_3_rachas](ejercicio_3_rachas) | Carga a SQLite, reglas de calidad y consulta de rachas |
| 4. Imágenes de HTML a base64 | [ejercicio_4_html](ejercicio_4_html) | Paquete en Python (solo librería estándar) y una carpeta de ejemplo |

## Cómo ejecutarlo

Requiere Python 3.9 o superior. La única dependencia externa es `openpyxl`, que el ejercicio 3 usa para leer el Excel.

```bash
pip install -r requirements.txt

# Ejercicio 3
python ejercicio_3_rachas/cargar_datos.py
python ejercicio_3_rachas/consultar_rachas.py --fecha-base 2024-12-31 --n 3

# Ejercicio 4
cd ejercicio_4_html
python -m html_base64 ejemplo/
```

## Ejercicio 1. Dataset de teléfonos de clientes

Un dataset confiable de teléfonos no guarda un número por cliente. Guarda todos los que se conocen, con su origen, su estado y la evidencia de si funcionan, y elige el principal con reglas explícitas y versionadas. La validación revisa el formato según la numeración colombiana y también si el número es plausible, porque un 3000000000 o el celular de un asesor repetido en cuarenta clientes tienen un formato perfecto y no sirven. El dataset se mantiene vivo con la retroalimentación de los canales de contacto.

En el CI/CD separo el código de los datos. El código se valida en cada pull request con datos sintéticos y se despliega por ambientes, con aprobación antes de producción. Los datos se controlan en cada corrida con el patrón write-audit-publish: si no pasan los controles, no se publican y los consumidores siguen viendo la versión anterior.

## Ejercicio 2. Veeduría de calidad y KPIs

El mismo pipeline del ejercicio 1 escribe en cada corrida una tabla histórica de métricas, y de ahí se alimenta un tablero. Separo los indicadores técnicos (completitud, validez, unicidad, frescura) de los de negocio (cobertura contactable, contactabilidad efectiva, tasa de número errado), porque responden preguntas distintas a personas distintas. Cada indicador tiene una ficha con definición, fórmula, responsable y umbral. La trazabilidad funciona en dos niveles: el linaje entre tablas en un catálogo y, para cada cliente, la razón por la que tiene ese teléfono como principal.

## Ejercicio 3. Rachas

### Ejecución

`cargar_datos.py` crea `ejercicio_3_rachas/rachas.db` desde cero, carga las dos hojas del Excel y aplica las reglas de calidad. `consultar_rachas.py` ejecuta la consulta para la fecha_base y el n que se le indiquen; con `--csv archivo.csv` guarda el resultado en un archivo.

La consulta también se puede correr desde la consola de SQLite. La fecha va con comillas simples dentro de las dobles, porque sin ellas SQLite toma `2024-12-31` como una resta:

```
sqlite3 ejercicio_3_rachas/rachas.db
.parameter set :fecha_base "'2024-12-31'"
.parameter set :n 3
.read ejercicio_3_rachas/sql/02_rachas.sql
```

### Cómo está construido

| Script | Qué hace |
|---|---|
| `sql/00_esquema.sql` | Crea las tablas. Es idempotente: borra y recrea todo |
| `sql/01_limpieza.sql` | Pasa de staging a tablas limpias y registra cada incidencia |
| `sql/02_rachas.sql` | La consulta de rachas, con los parámetros `:fecha_base` y `:n` |
| `sql/03_resumen_calidad.sql` | Resumen de lo que dejó la carga |

La carga tiene dos capas. `stg_historia` y `stg_retiros` son una copia fiel de las hojas, con el número de fila del Excel, para poder rastrear cualquier dato hasta el archivo. A partir de ellas se construyen `historia` y `retiros`, con llave primaria y restricciones de formato. Lo que se descarta, se corrige o se excluye queda en `dq_incidencias`, junto con la regla que aplicó.

La consulta arma una malla con todos los meses de cada cliente, desde su primera aparición hasta el último corte de la fecha_base, y quita los meses posteriores al retiro. Luego clasifica cada mes por nivel y encuentra las rachas con la técnica de islas: dentro de una racha, el índice del mes y el número de fila por cliente y nivel avanzan juntos, así que su diferencia es constante y sirve para identificarla. El calendario se genera con un CTE recursivo, así no depende de que todos los meses vengan en el archivo.

### Lo que encontré en los datos

Antes de escribir la consulta revisé el archivo completo. En varios aspectos viene limpio: no hay nulos, los saldos son enteros positivos, las fechas de `historia` son fin de mes (24 cortes seguidos, de enero de 2023 a diciembre de 2024) y ningún saldo cae justo en un límite entre niveles. Aun así dejé esas validaciones en el script, porque una carga futura puede no venir igual. El script limpia espacios y minúsculas en la identificación, lleva a fin de mes las fechas que no lo son, rechaza saldos negativos o en texto, ignora filas vacías y deja un solo retiro por cliente. Los saldos no se redondean, porque redondear un 299,999.6 lo pasaría de N0 a N1.

Lo que sí encontré son seis casos que hay que resolver:

| Caso | Dónde | Qué hice |
|---|---|---|
| Fila repetida | `9NWFWJ38XN31WBFXG`, agosto de 2023 | Se conserva una sola |
| Un mismo corte con dos saldos | `R7Q4Z9AULIORDJQ9D`, diciembre de 2024 | Se conserva el menor |
| Identificación de 19 caracteres en retiros | `1LFTDYT2H0I9ZGED3S8` | Se rechaza y no se corrige |
| Saldos reportados después del retiro | `0TTW5R9RRCJ0A9E5F` y `THJ9OBJH3W6ANRCMS` | Se excluyen del cálculo |
| Retiro a mitad de mes | `869YG73INQB5W1NQT`, 5 de diciembre de 2024 | El corte del 31 de diciembre ya no cuenta |
| Retiro posterior a los datos | `6T645BU8TYM8VGXKO`, 10 de enero de 2025 | Solo cuenta si la fecha_base lo alcanza |

Tres de estas decisiones necesitan explicación.

En el corte de diciembre de 2024, `R7Q4Z9AULIORDJQ9D` tiene un saldo de 571,481 y otro de 1,142,962. El segundo es exactamente el doble del primero, que es lo que pasa cuando un registro se suma dos veces en el origen. Por eso me quedé con 571,481, y ese mes queda en N1 y no en N2. La regla general es conservar el menor y dejar registro del conflicto. Es una regla que habría que validar con el dueño del dato.

En retiros, `1LFTDYT2H0I9ZGED3S8` tiene dos caracteres más que cualquier otra identificación y no existe en la historia. Se parece mucho a `1LFTDYT2H0I9ZG3S8`, a la que solo le sobra "ED", pero ese cliente reporta saldos todos los meses hasta diciembre de 2024, más de un año después de la supuesta fecha de retiro (11 de noviembre de 2023). Aplicar la corrección le cortaría la historia por una suposición, así que la fila queda rechazada y el posible match queda anotado aquí para que alguien lo confirme.

`0TTW5R9RRCJ0A9E5F` se retiró el 10 de octubre de 2024 y tiene saldos en los tres cortes siguientes. `THJ9OBJH3W6ANRCMS` se retiró el 20 de enero de 2024 y tiene saldos de enero a noviembre. El enunciado solo dice que después del retiro no se imputa N0, pero calcular rachas de un cliente retirado con datos que no deberían existir no tiene sentido. Esos 14 registros siguen en `historia`; la consulta no los usa y quedan reportados como `saldo_posterior_al_retiro`.

Con eso, de 2,925 filas de historia quedan 2,923, y de 5 retiros quedan 4:

| Tabla | Regla | Acción | Filas |
|---|---|---|---|
| historia | duplicado_con_conflicto | descartada | 1 |
| historia | duplicado_exacto | descartada | 1 |
| historia | saldo_posterior_al_retiro | excluida_del_calculo | 14 |
| retiros | identificacion_formato_invalido | rechazada | 1 |

### Cómo interpreté las reglas

La fecha_base es el día en que uno se "para" a mirar. Solo cuentan los cortes menores o iguales a ella y los retiros que ya habían ocurrido. Si no es fin de mes, se toma el último corte anterior; con 2024-06-15, por ejemplo, el último corte es 2024-05-31.

Un cliente que no aparece en un mes, después de su primera aparición, se toma como N0. Esto llega hasta el último corte de la fecha_base, pero no más allá del último corte que existe en los datos. Con una fecha_base de 2025-06-30 no tendría sentido llenar de N0 seis meses de los que todavía no llegó información, porque eso inventaría rachas. Por eso esa fecha da el mismo resultado que 2024-12-31. Para el cálculo da igual que el N0 venga de un saldo bajo o de un mes sin información: un saldo de 100,000 en marzo seguido de un abril ausente son dos meses seguidos en N0.

De las rachas que llegan a n meses, se toma la más larga y, si hay empate, la que termina más cerca de la fecha_base. No puede haber un segundo empate, porque dos rachas de un mismo cliente no terminan en el mismo mes. Los clientes sin ninguna racha de al menos n meses no aparecen en el resultado.

### Resultado

Con fecha_base 2024-12-31 y n = 3 salen 91 clientes. Estas son las primeras filas:

```
identificacion       racha  fecha_fin   nivel
09SYGN7IXDQV5X9IP        3  2023-04-30  N4
0TQ17VI65FDDKT227        3  2024-03-31  N2
0TTW5R9RRCJ0A9E5F        4  2023-11-30  N2
15J0ZCH8C1O665RTF        3  2023-07-31  N3
1LFTDYT2H0I9ZG3S8        3  2024-10-31  N4
2XCK13Y6KY3FTUJ0T        3  2024-09-30  N3
375WULANW2HVOVK5J        3  2024-11-30  N0
```

Por nivel quedan 16 clientes en N0, 1 en N1, 29 en N2, 15 en N3 y 30 en N4. Que haya tan pocos en N1 es esperable, porque es el rango más angosto (de 300,000 a 1,000,000).

### Cómo comprobarlo

El cliente `375WULANW2HVOVK5J` sirve para seguir la lógica a mano. Termina con una racha de 3 meses en N0 en noviembre de 2024. En su historia se ve por qué: en agosto de 2024 tiene 469,149 (N1), no aparece en septiembre, octubre ni noviembre, y en diciembre vuelve con 3,819,605 (N3). Esos tres meses sin información se toman como N0 y forman la racha.

```bash
sqlite3 ejercicio_3_rachas/rachas.db "SELECT corte_mes, saldo FROM historia WHERE identificacion = '375WULANW2HVOVK5J' ORDER BY corte_mes"
```

Los casos de la tabla anterior están en `dq_incidencias`, cada uno con la fila del Excel de donde salió:

```bash
sqlite3 -header -column ejercicio_3_rachas/rachas.db "SELECT fila_origen, identificacion, regla, detalle FROM dq_incidencias"
```

Mientras desarrollaba, comparé además el resultado del SQL con un cálculo mes a mes hecho en Python, para varias combinaciones de fecha_base y n, y coincidieron.

## Ejercicio 4. Imágenes de HTML a base64

### Ejecución

Desde la carpeta `ejercicio_4_html`:

```bash
python -m html_base64 ejemplo/
python -m html_base64 pagina.html otra/carpeta/ --salida salida/ --reporte reporte.json
```

Recibe cualquier mezcla de archivos HTML y directorios. Los directorios se recorren completos, con sus subdirectorios, buscando archivos `.html` y `.htm`. Por cada archivo se genera uno nuevo con el sufijo `.base64` (`index.html` produce `index.base64.html`), junto al original o dentro de `--salida`, conservando la estructura de carpetas. El original nunca se modifica. Con `--sin-remotas` no se descargan imágenes por HTTP.

También se puede usar desde código:

```python
from html_base64 import ProcesadorHtml

resultado = ProcesadorHtml().procesar(["ejemplo/"])
```

### Resultado

El objeto tiene la forma que pide el enunciado, `{success: {}, fail: {}}`, con las dos llaves indexadas por la ruta del HTML. En `success` va la lista de imágenes convertidas. En `fail` va cada imagen que no se pudo convertir con el motivo, porque saber que algo falló sin saber por qué no ayuda a corregirlo. La carpeta de ejemplo trae a propósito casos buenos y malos, y da esto (rutas acortadas):

```json
{
  "success": {
    "ejemplo/blog/2024/nota.htm": ["../../img/icono.svg", "../../img/banner.png"],
    "ejemplo/blog/entrada.html": ["../img/logo.png"],
    "ejemplo/index.html": ["img/logo.png", "img/icono.svg", "img/banner.png"]
  },
  "fail": {
    "ejemplo/index.html": [
      {"src": "img/no_existe.jpg", "motivo": "no se encontró el archivo .../img/no_existe.jpg"},
      {"src": "img/notas.png", "motivo": "el contenido no corresponde a una imagen"},
      {"src": null, "motivo": "etiqueta <img> sin atributo src"},
      {"src": "data:image/gif;base64,R0lGODlhAQABAAAAACw=", "motivo": "la imagen ya viene embebida como data URI"}
    ]
  }
}
```

### Diseño

| Clase | Responsabilidad |
|---|---|
| `BuscadorHtml` | Convierte las rutas de entrada en la lista de archivos, sin repetidos y sin los `.base64.html` de corridas anteriores |
| `CodificadorImagen` | Recibe el `src` de una imagen y devuelve el data URI |
| `ReescritorHtml` | Encuentra las etiquetas `<img>` y les cambia el `src` |
| `ProcesadorHtml` | Coordina a las otras tres y arma el resultado |

Las dependencias se pasan en el constructor, así que se puede cambiar una pieza, por ejemplo el codificador, sin tocar el procesador.

La decisión más importante es que el HTML no se regenera. `html.parser` sirve para encontrar las etiquetas, pero reconstruir el documento a partir de lo que entrega el parser cambia espacios, comentarios, mayúsculas y el orden de los atributos. Por eso uso la posición de cada etiqueta para cambiar solo el valor del `src` sobre el texto original, y todo lo demás queda igual byte por byte. Los atributos se recorren uno por uno, de modo que un `data-src`, o un `alt` que contenga el texto "src=", no se confunden con el `src` real.

Las rutas se resuelven como lo haría un navegador: un `src` relativo se busca desde la carpeta del HTML y no desde donde se ejecuta el script. También se aceptan rutas absolutas, `file://` y URLs `http(s)`, que se descargan con un timeout. Antes de convertir, se revisa que el contenido sea de verdad una imagen mirando sus primeros bytes, y de ahí sale el tipo MIME. Así, un archivo de texto con extensión `.png` termina en `fail` y no como una imagen rota dentro del HTML. El HTML se lee en UTF-8 o, si no lo es, en latin-1, y se escribe en la misma codificación. Si dos entradas llegan al mismo destino dentro de `--salida`, como `a/index.html` y `b/index.html`, el segundo archivo se numera en lugar de sobrescribir al primero.

Dejé por fuera las imágenes en `srcset`, en `<picture><source>` y en fondos de CSS, porque el enunciado se limita a la etiqueta `<img>`. Agregarlas solo tocaría el reescritor. Un `src` que empieza por `/` se toma como ruta del sistema de archivos y no como la raíz de un sitio web, porque el script no tiene forma de saber dónde está esa raíz.

### Cómo comprobarlo

Al comparar el original con el archivo generado se ve que solo cambian los `src` de las imágenes convertidas:

```bash
diff ejemplo/index.html ejemplo/index.base64.html
```

El `diff` muestra únicamente tres líneas. Si se copia `index.base64.html` a cualquier otra carpeta y se abre en el navegador, las imágenes se siguen viendo, porque ya van dentro del HTML.
