# -*- coding: utf-8 -*-
"""
@Institución: IU Pascual Bravo
@Docente    : Jaime E Soto U
@asignatura : ET0155 -Fundamentos de BigData
@Grupo      : G0100
@Tarea      : Tarea Unidad 2
@Módulo     : Carga aleatoria de operaciones de venta
@Periodo    : 2024-2
@Función    : Calculo de tiempo de procesamiento y tamaño de almacenamiento
"""
import time
import sys
import re
import random
import psycopg2
from   psycopg2 import Error
# Variables globales
error_con = False
# Parámetros de conexión de la Base de datos local
v_host	   = "localhost"
v_port	   = "5432"
v_database = "bigdata"
v_user	   = "postgres"
v_password = "postgres"

#-----------------------------------------------------------------------------
# Función:  Cargar Operaciones
#-----------------------------------------------------------------------------
def cargarOperaciones(conn, cur, reg, dep, mun, prod, fec, cant):
    try:
        print("Registro: ", reg, dep, mun, prod, fec, cant, end="\n") 
    
        command='''INSERT INTO tamanio (id_registro, 
                                        id_departamento, id_municipio, id_producto, 
                                        fecha, cantidad, estado) 
                     VALUES (%s,%s,%s,%s,%s,%s,%s);'''
        cur.execute(command, (reg, dep, mun, prod, fec, cant, 'V'))
        conn.commit()
    except (Exception, Error) as error:
        print("Error en carga de operaciones: ", error)
        sys.exit("Error: Carga Operaciones!")
    finally:
        return    
    # Fin función cargarVentas
          


# --------------------------------------------------------------------------
# CONEXIÓN A LA BASE DE DATOS
# --------------------------------------------------------------------------
try:
    # Conexión local a la base de datos
    connection = psycopg2.connect(user= v_user, password=v_password, host= v_host,
                                  port= v_port, database= v_database)
    # Creación cursor para realizar operaciones en la basedatos
    cursor = connection.cursor()
    # Ejecución de SQL query
    cursor.execute("SELECT version();")
    # Fetch result
    record = cursor.fetchone()
    # Imprime detalles de PostgreSQL
    print("PostgreSQL Información del Servidor")
    print(connection.get_dsn_parameters(), "\n")    
    print("Python version: ",sys.version)    
    print("Estás conectado a - ", record, "\n")
    print("Base de datos:", v_database, "\n")
    # -------------------------------------------------------------------------
    # LIMPIEZA DE TABLAS
    # -------------------------------------------------------------------------
    command = '''TRUNCATE tamanio;'''
    cursor.execute(command)    
    connection.commit()    
except (Exception, Error) as error:
    print("Error: ", error)
    error_con = True
finally:
    if (error_con):            
        sys.exit("Error de conexión con servidor PostgreSQL")
# Fin conexión y limpieza de tabla "ventas"


# --------------------------------------------------------------------------
# Generación aleatoria de operaciones de ventas
# --------------------------------------------------------------------------
try:
    # -------------------------------------------------------------------------
    # Debe ejecutar el programa para la siguiente cantidad de registros
    # 10000
    # 100000
    # 1000000
    # Cambie el valor de la variable registros para cada cantidad y ejecute el programa
    # -------------------------------------------------------------------------
    registros = 10000
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # TIEMPO INICIO
    # AQUI DEBE REGISTRAR EL INICIO DEL TIEMPO DE PROCESAMIENTO
    # -------------------------------------------------------------------------
    
    # -------------------------------------------------------------------------
    # Carga aleatoria de registros de operaciones de venta
    # -------------------------------------------------------------------------
    for iteracion in range(1, registros+1):
        # -----------------------------------------
        # Generación aleatora de código de producto 
        # -----------------------------------------
        id_producto = random.randint(1, 4)                    
        # -----------------------------------------------------------------
        # Generación aleatoria de cantidad de unidades vendidas de producto
        # -----------------------------------------------------------------
        cantidad = random.randint(1, 5000)            
        # ----------------------------------------------------
        # Generación aleatoria de fechas - Formato: DD-MM-AAAA
        # ----------------------------------------------------
        dia   = str(random.randint(1, 28))
        mes   = str(random.randint(1, 12))
        dia   = "0" + dia if len(dia) == 1 else dia
        mes   = "0" + mes if len(mes) == 1 else mes
        anio  = "2023"
        fecha = dia + "-" + mes + "-" + anio

        # Selección aleatoria de un municipio
        # Se carga el resultado en la variable "record"
        # De esta, se obtienen los datos de departamento y municipio
        command   = '''SELECT * FROM municipios ORDER BY RANDOM() LIMIT 1;'''
        resultado = cursor.execute(command)
        record    = cursor.fetchall()
        # Se obtienen los valores de departamento y municipio         
        id_departamento = record[0][0];
        id_municipio    = record[0][1];
        # ---------------------------------------------------------------------
        # Carga de operación de venta
        # ---------------------------------------------------------------------        
        cargarOperaciones(connection, cursor, iteracion, id_departamento, 
                     id_municipio, id_producto, fecha, cantidad)

    # -------------------------------------------------------------------------
    # TIEMPO FINAL
    # AQUI DEBE REGISTRAR EL FIN DEL TIEMPO DE PROCESAMIENTO
    # CALCULAR EL TIEMPO DE PROCESAMIENTO = TIEMPO FINAL - TIEMPO INICIAL
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Tamaño de la Base de datos "bigdata" y la Tabla "tamanio"
    # -------------------------------------------------------------------------
    command   = '''SELECT pg_size_pretty(pg_database_size('bigdata-g050'));'''
    resultado = cursor.execute(command)
    record    = cursor.fetchall()
    print("Tamaño de la base de datos: ", record)
    # -------------------------------------------------------------------------
    command   = '''SELECT relname as "Table", 
       pg_size_pretty(pg_total_relation_size(relid)) As "Size" 
	   FROM pg_catalog.pg_statio_user_tables 
	   ORDER BY pg_total_relation_size(relid) DESC;'''
    resultado = cursor.execute(command)
    record    = cursor.fetchall()
    print("Tamaño de las tablas: ", record)
    # -------------------------------------------------------------------------
    connection.commit()
except (Exception, Error) as error:
    print("Error de procesamiento de operaciones!", error)
    sys.exit("Error ->  Generación aleatoria de datos")
finally:
    if (connection):
        connection.close()
        print("Conexión PostgreSQL cerrada")    
        
print("Fin del proceso de carga aleatoria de operaciones - LOADING")
# Fin del algoritmo


