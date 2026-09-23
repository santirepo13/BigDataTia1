SELECT departamento, municipio, SUM(venta) AS monto_total
FROM vista_operaciones
GROUP BY id_municipio, departamento, municipio
ORDER BY monto_total ASC, departamento ASC, municipio ASC
LIMIT 5;
