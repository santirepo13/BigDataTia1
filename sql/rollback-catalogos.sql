-- =====================================================================
-- ROLLBACK de las correcciones de catalogo (departamentos / municipios)
-- Deja la base como estaba ANTES de la limpieza:
--   poblacion = 0   y   abb = NULL
-- Sirve para demostrar la correccion en el video (antes -> despues).
-- Ejecutar en pgAdmin sobre la base de datos "bigdata".
-- =====================================================================

BEGIN;

UPDATE public.departamentos SET poblacion = 0, abb = NULL;
UPDATE public.municipios   SET poblacion = 0, abb = NULL;

-- Estado deshecho (debe mostrar 33 y 1123 en las dos columnas)
SELECT 'departamentos' AS tabla,
       count(*) FILTER (WHERE poblacion = 0) AS poblacion_cero,
       count(*) FILTER (WHERE abb IS NULL)   AS abb_nulo
FROM public.departamentos
UNION ALL
SELECT 'municipios',
       count(*) FILTER (WHERE poblacion = 0),
       count(*) FILTER (WHERE abb IS NULL)
FROM public.municipios;

COMMIT;
