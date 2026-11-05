# Ejercicio 2. Veeduría de calidad y KPIs de teléfonos

## Para quién es

El enunciado dice que este recurso es para los equipos de negocio, y eso define el diseño. A un gerente de cobranza o de servicio no le sirve saber que una regla de validación falló en 312 filas. Le sirve saber a qué porcentaje de sus clientes en mora puede llamar hoy, si ese porcentaje va mejorando y, cuando algo se ve raro, poder preguntar de dónde salió un dato sin depender de un ingeniero.

Por eso propongo una sola fuente de métricas con dos tipos de lectura. Una es técnica, para el equipo de datos. La otra es de negocio, para las áreas que usan los teléfonos.

## De dónde salen los números

Las métricas no se calculan aparte. El mismo pipeline del ejercicio 1, al final de cada corrida, escribe sus resultados en una tabla histórica:

| Campo | Descripción |
|---|---|
| `fecha_proceso` | corrida a la que pertenece la medición |
| `id_carga` | enlaza con el log de ejecución y con la versión del código |
| `metrica` | nombre estable de la métrica, por ejemplo `pct_clientes_movil_valido` |
| `dimension` | segmento, región, producto o fuente, según aplique |
| `valor`, `numerador`, `denominador` | se guardan los tres para poder recalcular y agregar bien |
| `umbral_alerta`, `estado` | verde, amarillo o rojo según el umbral vigente |

Tener una sola tabla evita que el tablero muestre un número y el dataset diga otro, y permite ver tendencias sin reprocesar nada. Guardar numerador y denominador, y no solo el porcentaje, es lo que permite sumar regiones o meses sin promediar porcentajes, un error muy común en estos tableros.

## Indicadores de calidad del dato

Estos son para el equipo de datos y para el dueño del dataset.

| Dimensión | Indicador | Cálculo |
|---|---|---|
| Completitud | Clientes activos con al menos un teléfono | clientes con teléfono / clientes activos |
| Validez | Números que pasan formato y plausibilidad | números válidos / números recibidos |
| Unicidad | Números compartidos por más de N clientes | conteo, con detalle por fuente |
| Consistencia | Clientes cuyo principal difiere entre fuentes | clientes en conflicto / clientes con más de una fuente |
| Frescura | Horas desde la última carga exitosa de cada fuente | ahora menos la última fecha de carga |
| Estabilidad | Variación del total de clientes frente a la corrida anterior | diferencia porcentual |

Validez y exactitud no son lo mismo. Un número puede tener el formato perfecto y ser de otra persona. La única forma de medir exactitud es con los resultados reales de contacto, y por eso el indicador más importante de la siguiente tabla depende de la retroalimentación que describí en el ejercicio 1.

## Indicadores de negocio

| Indicador | Pregunta que responde | Cálculo |
|---|---|---|
| Cobertura contactable | ¿A cuántos clientes puedo contactar? | clientes con principal válido y autorización vigente / clientes activos |
| Contactabilidad efectiva | ¿Los números de verdad funcionan? | intentos con contacto exitoso / intentos realizados, por canal |
| Tasa de número errado | ¿Cuánto estoy perdiendo en llamadas inútiles? | intentos marcados como número equivocado / intentos |
| Teléfonos confirmados recientes | ¿Qué tan actualizada está la base? | principales con contacto exitoso en los últimos 6 meses / principales |
| Cobertura de móvil | ¿A cuántos les puedo enviar SMS o WhatsApp? | clientes con móvil válido / clientes activos |

Todos se pueden abrir por segmento, región, tramo de mora y producto. Para cobranza, por ejemplo, ver la cobertura contactable de los clientes que entran a mora en el mes tiene mucho más valor que el promedio de toda la cartera.

## Trazabilidad

Hay dos niveles y los dos hacen falta.

El primero es el linaje entre tablas: qué fuentes alimentan el dataset, por qué transformaciones pasa y qué tableros o procesos lo consumen. Esto se registra en un catálogo de datos (DataHub, OpenMetadata o Atlas, que viene con Cloudera). Si el orquestador emite eventos OpenLineage, el linaje se actualiza solo en cada corrida.

El segundo es la trazabilidad por registro, que es la que de verdad usa el negocio. Para cualquier cliente debe poder responderse por qué tiene este teléfono como principal. La respuesta sale de las columnas que ya guarda el dataset: la fuente, la fecha en que se vio, la regla de selección que lo eligió, el `id_carga` y el valor original antes de normalizar. Encima de eso basta una pantalla de consulta por cliente, con acceso restringido, que muestre la historia de sus números.

## El tablero

Propongo un tablero en la herramienta de BI que ya use la organización (Power BI, Tableau o la que sea). Lo que importa es que lea de la tabla de métricas y no calcule nada por su cuenta. Tendría tres vistas:

**Resumen.** Los cinco indicadores de negocio con su tendencia de los últimos 12 meses, en semáforo frente a la meta.

**Detalle.** Los mismos indicadores abiertos por las dimensiones de negocio, con filtro por fecha de proceso para ver cómo estaba la base en un corte específico.

**Salud del dato.** Los indicadores técnicos, el estado de la última corrida de cada fuente y la lista de incidencias abiertas. Esta vista es la que revisa primero el equipo de datos cada mañana.

Cada indicador lleva su ficha: definición en lenguaje de negocio, fórmula, fuente, frecuencia de actualización, responsable y umbral. Si dos áreas entienden distinto "cliente contactable", la discusión se resuelve una vez en la ficha y no en cada comité.

## Alertas y responsables

Un indicador en rojo que nadie atiende no sirve para nada. Cada métrica tiene un dueño de negocio, que decide la meta y qué hacer si no se cumple, y un responsable técnico, que investiga cuando la causa es el dato. Las alertas técnicas (fuente que no llegó, caída brusca de volumen) van al canal del equipo de datos apenas termina la corrida. Las de negocio (cobertura por debajo de la meta durante dos cortes seguidos) se revisan en el seguimiento mensual del área.

## Ejemplo de cálculo

Así se calcularía la cobertura contactable por región en una corrida, ya en el formato de la tabla de métricas:

```sql
WITH base AS (
    SELECT
        c.id_cliente,
        c.region,
        max(CASE WHEN t.es_principal
                  AND t.estado_validacion = 'VALIDO'
                  AND t.autoriza_contacto
                 THEN 1 ELSE 0 END) AS es_contactable
    FROM clientes_activos AS c
    LEFT JOIN telefonos_cliente AS t
      ON  t.id_cliente = c.id_cliente
      AND t.vigente
    GROUP BY c.id_cliente, c.region
)
INSERT INTO dq_metricas (fecha_proceso, id_carga, metrica, dimension,
                         numerador, denominador, valor)
SELECT
    p.fecha_proceso,
    p.id_carga,
    'pct_cobertura_contactable'                              AS metrica,
    b.region                                                 AS dimension,
    sum(b.es_contactable)                                    AS numerador,
    count(*)                                                 AS denominador,
    round(100.0 * sum(b.es_contactable) / nullif(count(*), 0), 2) AS valor
FROM base AS b
CROSS JOIN parametros_corrida AS p
GROUP BY p.fecha_proceso, p.id_carga, b.region;
```
