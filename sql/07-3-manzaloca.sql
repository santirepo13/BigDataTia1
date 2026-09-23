SELECT departamento, SUM(cantidad) AS cantidad_total
FROM vista_operaciones
WHERE producto='MANZALOCA'
GROUP BY departamento
ORDER BY cantidad_total DESC, departamento ASC
LIMIT 5;
