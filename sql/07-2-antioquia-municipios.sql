SELECT municipio, SUM(cantidad) AS cantidad_total
FROM vista_operaciones
WHERE id_departamento=5705
GROUP BY id_municipio, municipio
ORDER BY cantidad_total DESC, municipio ASC
LIMIT 15;
