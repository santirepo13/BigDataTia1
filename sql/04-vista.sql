CREATE OR REPLACE VIEW vista_operaciones AS
SELECT o.id_registro,d.nombre AS departamento,o.id_departamento,
 m.nombre AS municipio,o.id_municipio,p.nombre AS producto,o.id_producto,
 o.fecha,o.cantidad,p.precio,o.cantidad::bigint*p.precio AS venta,o.estado,
 o.id_region,r.nombre AS region,o.validacion,o.causa_modificacion
FROM operaciones o
JOIN departamentos d ON o.id_departamento=d.id_departamento
JOIN municipios m ON o.id_municipio=m.id_municipio AND o.id_departamento=m.id_departamento
JOIN productos p ON o.id_producto=p.id_producto
JOIN regiones r ON o.id_region=r.id_region;
