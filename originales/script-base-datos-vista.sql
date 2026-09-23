
--
-- ESTA VISTA  ES UNA HERRAMIENTA ESPECIAL PARA REALIZAR CONSULTAS
-- 
-- Operaciones completas
-- Nombres de departamento, municipio, producto, cantidad, precio y monto 
-- DROP VIEW vista_operaciones
CREATE VIEW vista_operaciones AS
SELECT 	ope.id_registro,
        dep.nombre as departamento, ope.id_departamento, 
       	mun.nombre as municipio,    ope.id_municipio,
       	pro.nombre as producto,     ope.id_producto,
   		ope.fecha,
        ope.cantidad, 
		pro.precio,
	   	ope.cantidad * pro.precio as venta,
		ope.estado
FROM operaciones ope
JOIN departamentos dep on dep.id_departamento = ope.id_departamento
JOIN municipios    mun on mun.id_municipio    = ope.id_municipio
JOIN productos     pro on pro.id_producto     = ope.id_producto
ORDER BY dep.nombre, mun.nombre, pro.nombre