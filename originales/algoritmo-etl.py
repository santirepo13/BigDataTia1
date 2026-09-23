# -*- coding: utf-8 -*-
"""
@author: jaimesoto
"""
# -*- coding: utf-8 -*-
"""
@Institución : IU Pascual Bravo
@author      : Profesor Jaime E Soto U
@email       : jaime.soto@pascualbravo.edu.co
@Departamento: Facultad de Ingeniería - Departamento de Sistemas Digitales
@asignatura  : ET01555 - Fundamentos de Bigdata 
@Tarea       : Tarea UNIDAD 1 - Procesamiento ETL (Extraction-Transformation-Load)

Data de Colombia
https://www.datos.gov.co/Mapas-Nacionales/Departamentos-y-municipios-de-Colombia/xdk5-pm3f/data
"""
#-------------------------------------------------------------------------
# UTILIZAR ESTE ALGORTIMO PARA VARIOS PROPÓSTIOS:
# 1.- Realizar el procedimiento de carga de los departamentos y municipios
# 2.- Incluir la modificación para agregar el campo "id_region" en la tabla "operaciones".
# 3.- Valorizar el código "id_region"
# NOTA: Previo a eso, se debe crear una tabla regiones y modificar
# la tabla "operaciones" para agregar el campo "id_region".  
# REQUERIMIENTO: Debe modificar el nombre del archivo y colocar el equipo (X)
#-------------------------------------------------------------------------


#-------------------------------------------------------------------------
# Paquetes y librerías
#-------------------------------------------------------------------------
import time
import sys
import re
import random
import pandas as pd
import psycopg2
from   psycopg2 import Error
import csv

# -------------------------------------------------------------------------
# Variables globales
# -------------------------------------------------------------------------
error_con = False
id_pais   = 57

#--------------------------------------------------------------------------
# Parámetros de conexión de la Base de datos local
# Estos son los parámteros que permiten la conexión con el PostgreSQL Local
#--------------------------------------------------------------------------
v_host	   = "localhost"
v_port	   = "5432"
v_database = "20252-bigdata"
v_user	   = "postgres"
v_password = "postgres"

#-----------------------------------------------------------------------------
# Función: Obtener número de código de Región
#-----------------------------------------------------------------------------
def getCodigoRegion(region):
    codigo_region = 0
    if region == "Region Eje Cafetero - Antioquia":
        codigo_region = 1
    elif region == "Region Centro Oriente":
         codigo_region = 2
    elif region == "Region Centro Sur":
         codigo_region = 3
    elif region == "Region Caribe":
         codigo_region = 4
    elif region == "Region Llano":
         codigo_region = 5
    elif region == "Region Pacifico":
         codigo_region = 6
    else:
         codigo_region = 0
    return codigo_region    
    # Fin función getCodigoRegion


#-----------------------------------------------------------------------------
# Función:  Carga Tabla Temporal
#-----------------------------------------------------------------------------
def cargarTablaTemporal(conn, cursor, contador, 
                        nombre_region, codigo_region, 
                        codigo_dep, departamento, 
                        codigo_mun, municipio):
    
    # Mensaje al usuario 
    print("Cargando temporal ... -> ", len(codigo_mun) , contador, 
          codigo_dep, codigo_mun, codigo_region, 
          departamento, municipio, nombre_region)

    # Control de tamaño del códgio de municipio 
    if (len(codigo_mun) > 10):
        print("Problemas con el código de departamento ... fila -> ",contador+1)
        return
    try:
        # - Los porcentajes después de VALUES (%s,%s,%s,%s,%s,%s)
        #   representan los parametros que se pasan en la instrucción "cursor.execute". 
        # - En este caso el primer % representa el codigo_region y así en adelante con los demás
        # --------------------------------------------------------------------------------------------------
        comando_sql = '''INSERT INTO temporal(codigo_region, codigo_dep, codigo_mun, departamento, municipio, region) 
                     VALUES (%s,%s,%s,%s,%s,%s);'''
        # --------------------------------------------------------------------------------------------------
        # En esta instrucción se ejecuta la sentencia SQL anterior con los  parámetros (datos) recibidos
        # --------------------------------------------------------------------------------------------------
        cursor.execute(comando_sql, 
                       (codigo_region, codigo_dep, codigo_mun, departamento, municipio, nombre_region))
        # --------------------------------------------------------------------------------------------------
        conn.commit()
    except (Exception, Error) as error:
        print("Error: ", error)
        sys.exit("Error: Carga tabla temporal!")
    finally:
        return
    # Fin función cargarTablaTemporal


#----------------------------------------------------------------------------------
# Clase:  Cargar Departamentos (desde la información obtenida en la tabla temporal)
# Aquí se "construye" el nuevo código de departamento
#----------------------------------------------------------------------------------
def cargarDepartamento(conn, cursor, 
                       codigo_departamento, nombre_departamento, 
                       codigo_region,
                       cantidad):
    id_pais         = 57
    sufijo          = str(codigo_departamento).zfill(2)
    id_departamento = int(str(id_pais) + sufijo)    
    nombre_dep      = nombre_departamento[0:50]
    print(sufijo, id_departamento, nombre_dep, codigo_departamento, codigo_region, cantidad)
    # Comando SQL
    comando_sql = '''INSERT INTO departamentos (id_departamento, codigo_dane, nombre, codigo_region) 
                 VALUES (%s,%s,%s,%s);'''
    # 
    cursor.execute(comando_sql, 
                   (id_departamento, codigo_departamento, nombre_dep, codigo_region))
    conn.commit()
    return
    # Fin función cargarDepartamento
    

#-----------------------------------------------------------------------------
# Clase:  Cargar Municipios (desde la información obtenida en la tabla temporal)
# Aquí se "construye" el nuevo código de municipio
#-----------------------------------------------------------------------------
def cargarMunicipio(conn, cursor, contador, codigo_dep, codigo_mun, municipio):
    try:
        sufijo          = str(codigo_dep).zfill(2)
        id_departamento = int(str(57) + sufijo)    
        sufijo          = str(contador).zfill(3)
        id_municipio    = int(str(id_departamento) + sufijo)    
        nombre_mun      = municipio[0:50]
        #
        print("Carga de munipios: contador, sufijo, id_dep, id_mun, nom_mun, cod_mun: ", 
              contador, sufijo, id_departamento, id_municipio, nombre_mun, codigo_mun, end="\n") 
    
        comando_sql = '''INSERT INTO municipios (id_departamento, id_municipio, nombre, codigo_dane) 
                     VALUES (%s,%s,%s,%s);'''
        cursor.execute(comando_sql, 
                       (id_departamento, id_municipio, nombre_mun, codigo_mun))
        conn.commit()
    except (Exception, Error) as error:
        print("Error en carga de Municipios: ", error)
        sys.exit("Error: Carga Municipios!")
    finally:
        return    
    # Fin función cargarMunicipio

         
# --------------------------------------------------------------------------
# INICIO DEL PROGRAMA
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# CONEXIÓN A LA BASE DE DATOS
# --------------------------------------------------------------------------
try:
    # Conexión local a la base de datos
    # Se utilizan los parámetros valorizados al inicio del programa
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
    # instrucción "TRUNCATE" realiza la misma operación que DELETE FROM "table"
    # -------------------------------------------------------------------------
    command = '''TRUNCATE temporal;'''
    cursor.execute(command)    
    command = '''TRUNCATE departamentos;'''
    cursor.execute(command)
    command = '''TRUNCATE municipios;'''
    cursor.execute(command)
    connection.commit()    
except (Exception, Error) as error:
    print("Error: ", error)
    error_con = True
finally:
    if (error_con):            
        sys.exit("Error de conexión con servidor PostgreSQL")



# ------------------------------------------------------------------------- 
# Extracción de Datos - Hoja de Cálculo (CSV)
# Carga en archivo temporal de la base de datos
# ------------------------------------------------------------------------- 
try:
    #---------------------------------------------------------------------------------
    # CABECERA ARCHIVO CSV
    # REGION, CODIGO DANE DEPARTAMENTO, DEPARTAMENTO, CODIGO DANE MUNICIPIO, MUNICIPIO    
    #   region              = row[0] - Primera columna - tiene índice "0"
    #   codigo_departamento = row[1] - Segunda columna
    #   departamento        = row[2] - Tercera columna
    #   codigo_municipio    = row[3] - Cuarta  columna
    #   municipio           = row[4] - Quinta  columna
    #---------------------------------------------------------------------------------
    archivo_fisico = 'colombia-dane-departamentos.csv'

    # ---------------------------------------------------------------------------------
    # Recorrido/Lectura de los registros de la hoja de cálculo
    # - Se recorre fila por fila (excluyendo el primero por ser cabecera)
    # - Toma cada fila (un registro), lo captura y lo lleva a una talba temporal
    # ---------------------------------------------------------------------------------
    with open(archivo_fisico) as File:
        # "reader" contiene la Hoja de Cálculo con los datos del DANE
        hoja_calculo = csv.reader(File, delimiter=',', quotechar=',', quoting=csv.QUOTE_MINIMAL)   
        
        # -----------------------------------------------------------------------------
        # columnas archivo hoja de cálculo con datos de región, departamento, municipio
        # -----------------------------------------------------------------------------
        col_nom_reg = 0 # Índice columna - Nombre Región
        col_cod_dep = 1 # Código departamento
        col_nom_dep = 2 # Nombre departamento
        col_cod_mun = 3 # Código municipio
        col_nom_mun = 4 # Nombre municipio
        # ---------------------------------------------------------------------------
        # Toma cada fila de la hoja de cálculo, extrae la info y carga tabla temporal
        # ---------------------------------------------------------------------------
        contador_registros = 0        
        for fila in hoja_calculo:
            # ---------------------------------------------------------------------
            # Saltar la cabecera de la hoja de cálculo
            # No se toma en cuenta las cabeceras de descripción de las columnas
            # ---------------------------------------------------------------------
            if (contador_registros > 0):
                # -----------------------------------------------------------------
                # fila[col_1] = Segunda o siguiente fila, tupla o registro de la hoja de cálculo
                # -----------------------------------------------------------------                
                nombre_region = fila[col_nom_reg]
                codigo_region = getCodigoRegion(nombre_region)  
                # ---------------------------------------------------------------------                
                # Carga de tabla temporal
                # Esta tabla servirá de pivote para cargar departamentos y municipios
                # posteriormente
                # ---------------------------------------------------------------------
                cargarTablaTemporal(connection, cursor, contador_registros, 
                                    nombre_region, 
                                    codigo_region,
                                    fila[col_cod_dep], 
                                    fila[col_nom_dep], 
                                    fila[col_cod_mun],
                                    fila[col_nom_mun])
              
            # Fin ciclo de recorrido de la hoja de cálculo
            contador_registros = contador_registros + 1
except (Exception, Error) as error:
    print("Error (excepción): ", error)
    sys.exit("Error ->  Fase Excel - Extracción hoja de cálculo -> carga tabla temporal")
finally:
    File.close()
    print("Tabla Temporal cargada ....")




# --------------------------------------------------------------------------
# CUERPO PRINCIPAL DEL PROGRAMA - PROCESAMIENTO DE DEPARTAMENTOS
# --------------------------------------------------------------------------
try:
    # Código de carga en tablas
    print("Inicia la carga de información ...")

    # -------------------------------------------------------------------------
    # DEPARTAMENTOS 
    # -------------------------------------------------------------------------    
    print("DEPARTAMENTOS")    
    # ATENCIÓN: Ponga especial atención en la select y el uso de "distinct"
    # Agrupamiento/Ordenamiento tabla temporal
    # El resultado de la consulta es el agrupamiento de los departamentos
    comando_sql = '''SELECT distinct codigo_dep, departamento, codigo_region, count(*) as veces from temporal 
            group by codigo_dep, departamento, codigo_region order by departamento'''
    #
    cursor.execute(comando_sql)
    #
    tuplas_tabla_temporal = cursor.fetchall()

    contador_tuplas = 0
    # Índices del arreglo de registros de la tabla temporal
    campo_cod_dep = 0   # Canpo código departamento
    campo_nom_dep = 1   # Nombre departamento
    campo_cod_reg = 2   # Campo código región
    campo_can_mun = 3   # Cantidad de municipios por departamento
   
    # -----------------------------------------------------
    # Recorrido de todos los registros de la tabla temporal
    # -----------------------------------------------------
    for tupla in tuplas_tabla_temporal:
        contador_tuplas= contador_tuplas + 1
        codigo_dep     = tupla[campo_cod_dep] # Primer campo de la selección
        departamento   = tupla[campo_nom_dep]
        codigo_region  = tupla[campo_cod_reg]
        cantidad_mun   = tupla[campo_can_mun]
        # -----------------------------------------------------
        # Pasaje de parámetros y carga en tabla "departamentos"
        # -----------------------------------------------------
        cargarDepartamento(connection, cursor,
                           codigo_dep, departamento,codigo_region,
                           cantidad_mun) 
   # -------------------------------------------------------------------------


    # -------------------------------------------------------------------------
    # MUNICIPIOS        
    # -------------------------------------------------------------------------
    print("MUNICIPIOS")    
    comando_sql = '''SELECT codigo_dep, codigo_mun, municipio from temporal order by departamento, municipio'''
    cursor.execute(comando_sql)    
    tuplas_tabla_temporal = cursor.fetchall()
    # Recorrido de todos los registros de la tabla temporal
    campo_1  = 0 # codigo del departamento del cursor resultado del comando_sql
    campo_2  = 1 # codigo del municipio
    campo_3  = 2 # Nombre del municipio
    contador = 0 # Ne3cesario para construir el nuevo código de municipio
    codigo_old = ''
    for tupla in tuplas_tabla_temporal:
        codigo_dep  = tupla[campo_1] # Campo codigo_dep
        codigo_mun  = tupla[campo_2] # campo codigo_mun
        municipio   = tupla[campo_3] # Campo noombre del municipio
        # Resetea el contador para un nuevo departamento
        if (codigo_dep == codigo_old):
            contador   = contador + 1
        else:
            contador   = 1
        #
        codigo_old = codigo_dep
        #
        cargarMunicipio(connection, cursor, contador, codigo_dep, codigo_mun, municipio) 
    # -------------------------------------------------------------------------        

    # -------------------------------------------------------------------------
    connection.commit()
    connection.close()    
    
except (Exception, Error) as error:
    print("Error de procesamiento de la tabla!", error)
finally:
    if (connection):
        connection.close()
        print("Conexión PostgreSQL cerrada")    
        
print("Fin del proceso ETL")
# Fin del algoritmo
