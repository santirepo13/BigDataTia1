SELECT region, producto, SUM(cantidad) AS cantidad_total
FROM vista_operaciones
GROUP BY id_region, region, producto
ORDER BY cantidad_total DESC, region ASC, producto ASC;
