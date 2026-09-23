"""Adaptación del algoritmo de Jaime E. Soto U. Conserva los datos aleatorios.
Mide generación + INSERT por lotes + confirmación final, sin extrapolar tiempos.
Una sola ejecución por tamaño: resultados descriptivos del entorno utilizado.
"""
import argparse
import csv
import json
import platform
import random
import time
from pathlib import Path
from psycopg2.extras import execute_values
from conexion import conectar

BASE=Path(__file__).resolve().parents[1]

def cargarOperaciones(conn,cur,filas):
    execute_values(cur,'INSERT INTO tamanio (id_registro,id_departamento,id_municipio,id_producto,fecha,cantidad,estado) VALUES %s',filas,page_size=len(filas))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--registros',type=int,nargs='+',default=[10000,100000,1000000,10000000])
    parser.add_argument('--lote',type=int,default=10000)
    parser.add_argument('--prefijo',default='mediciones',help='Nombre base para los archivos de resultados.')
    args=parser.parse_args()
    if args.lote<1 or any(n<1 for n in args.registros): parser.error('Los tamaños deben ser positivos.')
    conn=conectar(); resultados=[]
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT version(),current_database()'); version,bd=cur.fetchone()
            cur.execute('SELECT id_departamento,id_municipio FROM municipios ORDER BY id_municipio'); municipios=cur.fetchall()
            if not municipios: raise RuntimeError('Primero ejecute el ETL.')
            for n in args.registros:
                cur.execute('TRUNCATE tamanio'); conn.commit()
                random.seed(20260923); filas=[]
                inicio=time.perf_counter()
                for reg in range(1,n+1):
                    producto=random.randint(1,4); cantidad=random.randint(1,5000)
                    fecha=f'{random.randint(1,28):02d}-{random.randint(1,12):02d}-2023'
                    dep,mun=random.choice(municipios)
                    filas.append((reg,dep,mun,producto,fecha,cantidad,'F'))
                    if len(filas)==args.lote:
                        cargarOperaciones(conn,cur,filas); filas=[]
                if filas: cargarOperaciones(conn,cur,filas)
                conn.commit()
                tiempo_ms=(time.perf_counter()-inicio)*1000
                cur.execute("SELECT count(*) FROM tamanio"); assert cur.fetchone()[0]==n
                cur.execute("SELECT pg_total_relation_size('public.tamanio'),pg_database_size(current_database())")
                tabla_bytes,bd_bytes=cur.fetchone()
                fila=dict(registros=n,tiempo_ms=round(tiempo_ms,3),tabla_bytes=tabla_bytes,
                    bd_bytes=bd_bytes,tabla_kib=tabla_bytes/1024,bd_mib=bd_bytes/1048576,
                    porcentaje=100*tabla_bytes/bd_bytes)
                resultados.append(fila); print(json.dumps(fila),flush=True)
                salida=BASE/'resultados'
                (salida/(args.prefijo+'.json')).write_text(json.dumps(dict(entorno=version,base=bd,
                    python=platform.python_version(),plataforma=platform.platform(),lote=args.lote,
                    semilla=20260923,repeticiones=1,resultados=resultados),ensure_ascii=False,indent=2))
                with (salida/(args.prefijo+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=resultados[0]); w.writeheader();w.writerows(resultados)
    finally: conn.close()

if __name__=='__main__': main()
