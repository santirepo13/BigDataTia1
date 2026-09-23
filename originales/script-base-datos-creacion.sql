-- BASE DE DATOS "bigdata"


-- DROP TABLE IF EXISTS public.temporal;
CREATE TABLE IF NOT EXISTS public.temporal(
    codigo_dep character varying(10) COLLATE pg_catalog."default",
    codigo_mun character varying(10) COLLATE pg_catalog."default",
    codigo_region integer,
    departamento text COLLATE pg_catalog."default",
    municipio text COLLATE pg_catalog."default",
    region text COLLATE pg_catalog."default"
);

-- Table: public.departamentos
-- DROP TABLE IF EXISTS public.departamentos;
CREATE TABLE IF NOT EXISTS public.departamentos(
    id_departamento integer NOT NULL,
    nombre character varying(70) COLLATE pg_catalog."default" NOT NULL,
    abb character varying(3) COLLATE pg_catalog."default",
    codigo_dane character varying(10) COLLATE pg_catalog."default" DEFAULT ''::character varying,
    codigo_region integer DEFAULT 0,
    poblacion integer DEFAULT 0,
    CONSTRAINT departamentos_pkey PRIMARY KEY (id_departamento)
);

-- DROP TABLE IF EXISTS public.municipios;
CREATE TABLE IF NOT EXISTS public.municipios(
    id_departamento integer NOT NULL,
    id_municipio integer NOT NULL,
    nombre character varying(70) COLLATE pg_catalog."default" NOT NULL,
    abb character varying(5) COLLATE pg_catalog."default",
    codigo_dane character varying(10) COLLATE pg_catalog."default" DEFAULT ''::character varying,
    poblacion integer DEFAULT 0,
    CONSTRAINT municipios_pkey PRIMARY KEY (id_municipio)
);

-- DROP TABLE IF EXISTS public.productos;
CREATE TABLE IF NOT EXISTS public.productos(
    id_producto integer NOT NULL,
    nombre character varying(20) COLLATE pg_catalog."default" NOT NULL,
    precio integer DEFAULT 0
);

-- DROP TABLE IF EXISTS public.operaciones;
CREATE TABLE IF NOT EXISTS public.operaciones(
    id_registro integer NOT NULL,
    id_departamento integer NOT NULL,
    id_municipio integer NOT NULL,
    id_producto integer NOT NULL,
    fecha character varying(10), 
    cantidad integer DEFAULT 0,
    estado character varying(1)
);


-- Productos 
INSERT INTO productos (id_producto,nombre,precio)
VALUES
    (1,'COLOMBIANITA',1200),
    (2,'MANZALOCA',   1000),
    (3,'MANGOSON',     900),
    (4,'NARANJITA',    600);


-- Esta tabla se utiliza EXCLUSIVAMENTE PARA LOS CÁLCULOS DE TIEMPOS
-- NO SE UTILIZA PARA LAS CONSULTAS NI LOS GRÁFICOS
-- DROP TABLE IF EXISTS public.tamanio;
CREATE TABLE IF NOT EXISTS public.tamanio(
    id_registro integer NOT NULL,
    id_departamento integer NOT NULL,
    id_municipio integer NOT NULL,
    id_producto integer NOT NULL,
    fecha character varying(10), 
    cantidad integer DEFAULT 0,
    estado character varying(1)
);
