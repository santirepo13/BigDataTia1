-- Se aplica después de la creación original y antes de cargar los datos.
CREATE TABLE regiones (
 id_region integer PRIMARY KEY CHECK (id_region BETWEEN 1 AND 6),
 nombre varchar(70) NOT NULL UNIQUE
);
ALTER TABLE operaciones ADD COLUMN id_region integer;
ALTER TABLE operaciones ADD COLUMN validacion varchar(10) NOT NULL DEFAULT 'valido';
ALTER TABLE operaciones ADD COLUMN causa_modificacion text NOT NULL DEFAULT '';
