-- Las correcciones se detectan y calculan en python/limpieza.py con Pandas.
-- Este archivo se ejecuta después, dentro de la misma transacción.

-- Todas las fechas pasan a un tipo que impide guardar fechas inexistentes.
ALTER TABLE operaciones ALTER COLUMN fecha TYPE date USING fecha::date;
UPDATE operaciones o SET id_region=d.codigo_region
FROM departamentos d WHERE o.id_departamento=d.id_departamento;


ALTER TABLE productos ADD PRIMARY KEY (id_producto);
ALTER TABLE productos ADD CONSTRAINT productos_precio CHECK (precio>0);
ALTER TABLE departamentos ADD CONSTRAINT departamentos_region_fk FOREIGN KEY (codigo_region) REFERENCES regiones(id_region);
ALTER TABLE departamentos ADD CONSTRAINT departamento_region_uk UNIQUE (id_departamento,codigo_region);
ALTER TABLE municipios ADD CONSTRAINT municipios_dep_fk FOREIGN KEY (id_departamento) REFERENCES departamentos(id_departamento);
ALTER TABLE municipios ADD CONSTRAINT municipio_dep_uk UNIQUE (id_municipio,id_departamento);
ALTER TABLE operaciones ADD PRIMARY KEY (id_registro);
ALTER TABLE operaciones ADD CONSTRAINT operacion_municipio_dep_fk FOREIGN KEY (id_municipio,id_departamento) REFERENCES municipios(id_municipio,id_departamento);
ALTER TABLE operaciones ADD CONSTRAINT operacion_departamento_region_fk FOREIGN KEY (id_departamento,id_region) REFERENCES departamentos(id_departamento,codigo_region);
ALTER TABLE operaciones ADD CONSTRAINT operacion_producto_fk FOREIGN KEY (id_producto) REFERENCES productos(id_producto);
ALTER TABLE operaciones ADD CONSTRAINT operacion_region_fk FOREIGN KEY (id_region) REFERENCES regiones(id_region);
ALTER TABLE operaciones ALTER COLUMN fecha SET NOT NULL;
ALTER TABLE operaciones ALTER COLUMN cantidad SET NOT NULL;
ALTER TABLE operaciones ALTER COLUMN id_region SET NOT NULL;
ALTER TABLE operaciones ADD CONSTRAINT cantidad_positiva CHECK (cantidad>0);
ALTER TABLE operaciones ADD CONSTRAINT validacion_coherente CHECK
 ((validacion='valido' AND causa_modificacion='') OR
 (validacion='modificado' AND causa_modificacion<>''));
