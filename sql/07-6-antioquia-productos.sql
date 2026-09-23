SELECT producto, SUM(venta) AS monto_total
FROM vista_operaciones
WHERE id_departamento=5705
GROUP BY producto
ORDER BY monto_total DESC, producto ASC;
