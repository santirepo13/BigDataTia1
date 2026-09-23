# Unidad 1 — Procesamiento ETL de Gaseosas Poderosas

La carpeta contiene el desarrollo técnico del caso, datos originales, algoritmos adaptados, seis consultas SQL, resultados medidos, diagramas, informe y libro de Excel.

## Resultados obtenidos

- 6 regiones, 33 entradas departamentales y 1.123 municipios.
- 10.000 ventas conservadas; 30 registros corregidos y 9.970 válidos sin cambio.
- 1.007.755 unidades y COP 929.809.400 después de limpiar los datos.
- 10.000 filas tanto en `operaciones` como en `vista_operaciones`.
- Las seis consultas coinciden con una comprobación independiente por uniones directas.
- Cuatro pruebas reales: 10.000, 100.000, 1.000.000 y 10.000.000 de filas.

## Archivos

| Carpeta | Contenido |
|---|---|
| `documentos` | Informe Word y libro Excel |
| `python` | ETL adaptado, medición, conexión y verificaciones |
| `sql` | Regiones, limpieza, vista y las seis consultas |
| `datos` | CSV geográfico y SQL de ventas suministrados |
| `originales` | Código y datos de partida conservados sin modificaciones |
| `resultados` | Antes y después de limpiar, causas, consultas y mediciones |
| `evidencias` | Capturas, registros de ejecución y diagramas |

## Ejecutar en PostgreSQL local

Se necesita Python 3, PostgreSQL y una base **vacía** llamada `bigdata`. El ETL se detiene si ya existe `operaciones`, para no sobrescribir un trabajo anterior. No se deben ejecutar por separado los scripts que el ETL ya ejecuta.

Desde esta carpeta:

```bash
python -m pip install -r requirements.txt
python python/algoritmo-etl.py
python python/algoritmo-calculo-tamanio.py
python python/verificar.py
```

La conexión usa `localhost:5432`, usuario `postgres`, base `bigdata` y contraseña inicial `postgres`, como en el material suministrado. Se puede cambiar con las variables de entorno `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` y `PGSSLMODE`. No guardar contraseñas personales en Git.

Para la demostración de 10.000 registros del video, sin sustituir los cuatro resultados anteriores:

```bash
python python/algoritmo-calculo-tamanio.py --registros 10000 --prefijo mediciones_video
```

El cálculo vacía y vuelve a cargar **solo** la tabla de prueba `tamanio`. El tiempo incluye generación, inserción por lotes y confirmación final. No mide conexión, lectura del catálogo, vaciado previo ni consultas posteriores de tamaño.

En pgAdmin, abrir la base usada y ejecutar por separado los seis archivos `sql/07-*.sql`. Todos consultan exclusivamente `vista_operaciones`. `verificar.py` compara los resultados con uniones directas únicamente como comprobación adicional.

## Decisiones documentadas

- Dos filas del CSV, líneas 917 y 950, se vuelven a interpretar por tener comillas exteriores. No se pierden municipios.
- Los nombres del CSV se conservan, incluso grafías como `Togñi`. No se reemplazaron con otro catálogo.
- Se explicita el orden de texto `COLLATE "C"` al construir los códigos municipales. Támesis debe resultar 5705108.
- Primero se corrigen negativos y después se calculan promedios municipales positivos sin ceros. Se redondea a unidades enteras.
- Las fechas cortas se interpretan en 2024. `16558`, con `01-02-24`, se interpreta como 2024-02-01; la causa conserva la ambigüedad con 2024-01-02.
- La consulta 7.5 se ordena por cantidad total descendente; cada torta usa solo una región.
- Para 7.4 el resultado SQL queda ascendente. El Pareto reordena las mismas cinco filas en sentido descendente.
- Los Pareto usan barras y curva acumulada en dos paneles editables de cada pestaña. El acumulado corresponde al subconjunto seleccionado.
- 7.1 y su gráfico usan monto en COP, tal como pide la consulta, aunque el texto del apartado 8.1.2 menciona cantidades.
- `estado` conserva `F`. La validación solicitada está en los nuevos campos `validacion` y `causa_modificacion`.

## Entorno de las mediciones incluidas

Python 3.12.14; PostgreSQL 18.3 en PGlite 0.5.8; Linux x86_64; semilla 20260923; lotes de 10.000; una corrida por tamaño. Se utilizaron los algoritmos Python conectados por el protocolo PostgreSQL. **No son mediciones de un servidor PostgreSQL nativo**. Se entregan los scripts para repetirlas en el entorno de clase. No se extrapoló ninguna de las cuatro filas de resultados.

El conjunto tiene 32 entradas departamentales con ventas. Los dos municipios del archipiélago están en el catálogo, pero no tienen ventas en el SQL entregado. No se les imputaron ventas cero.

## Pendiente antes de presentar la entrega grupal

1. Capturar las seis consultas en pgAdmin. Las consultas ya se ejecutaron y verificaron; las capturas de esa interfaz no se incluyen.
2. Identificar el número o letra del equipo y todos sus integrantes en la portada. Renombrar los productos con la etiqueta `equipo_` y el identificador real que exige la guía.
3. Incorporar las conclusiones personales de cada integrante, identificadas individualmente. Las conclusiones actuales son técnicas y no se atribuyen a personas.
4. Grabar la sustentación de 5 a 15 minutos con todos los integrantes visibles, código en ejecución, pgAdmin y Excel. Añadir el enlace real en la sección 14. Consultar `guion_sustentacion.md`.
5. Colocar esta carpeta en el repositorio Git del semestre y entregar **solo su enlace** en el campus. No se ha creado ni publicado un repositorio remoto.

Estos elementos no se inventaron y no están acreditados como cumplidos. Los archivos técnicos se pueden revisar y ejecutar antes de añadir los datos del equipo.

## Autoría del material base

Los dos algoritmos originales identifican al profesor Jaime E. Soto U., IU Pascual Bravo. Sus originales se conservan y las adaptaciones los reconocen en el encabezado. La guía, la plantilla y la rúbrica proceden de los materiales de la actividad. Los resultados de ventas son cálculos sobre los archivos suministrados.
