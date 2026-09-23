import csv
import argparse
import json
import time
from pathlib import Path
import pandas as pd
from conexion import conectar
from limpieza import limpiar, resumen_problemas

BASE=Path(__file__).resolve().parents[1]
REGIONES={'Region Eje Cafetero - Antioquia':1,'Region Centro Oriente':2,
 'Region Centro Sur':3,'Region Caribe':4,'Region Llano':5,'Region Pacifico':6}

def getCodigoRegion(region):
    if region not in REGIONES:
        raise ValueError('Región desconocida: '+region)
    return REGIONES[region]

def cargarTablaTemporal(conn,cursor,contador,nombre_region,codigo_region,codigo_dep,departamento,codigo_mun,municipio):
    cursor.execute('INSERT INTO temporal VALUES (%s,%s,%s,%s,%s,%s)',
        (codigo_dep,codigo_mun,codigo_region,departamento,municipio,nombre_region))

def cargarDepartamento(conn,cursor,codigo_departamento,nombre_departamento,codigo_region,cantidad):
    id_departamento=int('57'+str(codigo_departamento).zfill(2))
    cursor.execute('INSERT INTO departamentos (id_departamento,nombre,codigo_dane,codigo_region) VALUES (%s,%s,%s,%s)',
        (id_departamento,nombre_departamento,codigo_departamento,codigo_region))

def cargarMunicipio(conn,cursor,contador,codigo_dep,codigo_mun,municipio):
    id_departamento=int('57'+str(codigo_dep).zfill(2))
    id_municipio=int(str(id_departamento)+str(contador).zfill(3))
    cursor.execute('INSERT INTO municipios (id_departamento,id_municipio,nombre,codigo_dane) VALUES (%s,%s,%s,%s)',
        (id_departamento,id_municipio,municipio,codigo_mun))

def exportar(cursor,consulta,ruta):
    cursor.execute(consulta)
    nombres=[col.name for col in cursor.description]
    registros=cursor.fetchall()
    with ruta.open('w',encoding='utf-8-sig',newline='') as archivo:
        writer=csv.writer(archivo); writer.writerow(nombres); writer.writerows(registros)
    return [dict(zip(nombres,r)) for r in registros]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fecha-ambigua',choices=['dia-mes','mes-dia'],
        help='Decisión explícita para fechas ambiguas; sin opción se detiene para revisión.')
    args=parser.parse_args()
    inicio=time.perf_counter()
    salida=BASE/'resultados'; salida.mkdir(exist_ok=True)
    conn=conectar()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('SELECT version(),current_database()'); print('ENTORNO:',cur.fetchone(),flush=True)
                cur.execute("SELECT to_regclass('public.operaciones')")
                if cur.fetchone()[0] is not None:
                    raise RuntimeError('Ya existe operaciones. Use una base vacía para no sobrescribir datos.')
                cur.execute((BASE/'originales/script-base-datos-creacion.sql').read_text(encoding='utf-8-sig'))
                cur.execute((BASE/'sql/02-regiones.sql').read_text())
                csv_corregidos=[]
                with (BASE/'datos/colombia-dane-departamentos.csv').open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.reader(f); next(reader)
                    for numero,fila in enumerate(reader,2):
                        if len(fila)==1:
                            fila=next(csv.reader(fila)); csv_corregidos.append(numero)
                        if len(fila)!=5: raise ValueError(f'CSV inválido en línea {numero}: {fila}')
                        region,dep,nombre_dep,mun,nombre_mun=fila
                        cargarTablaTemporal(conn,cur,numero,region,getCodigoRegion(region),dep,nombre_dep,mun,nombre_mun)
                print('CSV: 1123 filas; comillas reparadas en líneas',csv_corregidos,flush=True)
                cur.executemany('INSERT INTO regiones VALUES (%s,%s)',[(v,k) for k,v in REGIONES.items()])
                cur.execute('SELECT codigo_dep,departamento,codigo_region,count(*) FROM temporal GROUP BY 1,2,3 ORDER BY departamento')
                for fila in cur.fetchall(): cargarDepartamento(conn,cur,*fila)
                # Orden C explícito: conserva los IDs internos del archivo de ventas.
                cur.execute('SELECT codigo_dep,codigo_mun,municipio FROM temporal ORDER BY departamento COLLATE "C",municipio COLLATE "C"')
                anterior=None; contador=0
                for dep,mun,nombre in cur.fetchall():
                    contador=contador+1 if dep==anterior else 1; anterior=dep
                    cargarMunicipio(conn,cur,contador,dep,mun,nombre)
                cur.execute("SELECT id_municipio FROM municipios WHERE nombre='Tamesis' AND id_departamento=5705")
                assert cur.fetchone()[0]==5705108, 'La numeración municipal no coincide con las ventas.'
                # Solo sentencias INSERT del dump; se evita alterar parámetros de sesión.
                texto=(BASE/'datos/script-base-datos-operaciones.sql').read_text(encoding='utf-8-sig')
                inserciones='\n'.join(line for line in texto.splitlines() if line.startswith('INSERT INTO public.operaciones'))
                cur.execute(inserciones)
                originales=exportar(cur,'SELECT * FROM operaciones ORDER BY id_registro',salida/'operaciones_antes.csv')
                print('CARGA: operaciones originales =',len(originales),flush=True)
                datos=pd.DataFrame(originales)
                resumen,afectados=resumen_problemas(datos)
                print('EXPLORACIÓN INICIAL:\n'+resumen.to_string(index=False),flush=True)
                print('Registros distintos con problemas:',afectados,flush=True)
                catalogos={}
                for tabla in ['departamentos','municipios','productos']:
                    catalogos[tabla]=pd.DataFrame(exportar(cur,'SELECT * FROM '+tabla+' ORDER BY 1',salida/(tabla+'.csv')))
                limpios,detalle=limpiar(datos,catalogos['municipios'],catalogos['departamentos'],
                    catalogos['productos'],args.fecha_ambigua)
                resumen.to_csv(salida/'diagnostico_inicial.csv',index=False,encoding='utf-8-sig')
                detalle.to_csv(salida/'detalle_limpieza.csv',index=False,encoding='utf-8-sig')
                pendientes=detalle.loc[detalle['estado'].eq('pendiente')]
                pendientes.to_csv(salida/'pendientes.csv',index=False,encoding='utf-8-sig')
                if len(pendientes):
                    raise RuntimeError('Hay problemas pendientes. Revise resultados/pendientes.csv. '
                        'No se confirmó la transacción. Para la decisión día-mes-año use --fecha-ambigua dia-mes.')
                cambios_df=limpios.loc[limpios['validacion'].eq('modificado')]
                valores=[(str(r.fecha),int(r.cantidad),int(r.id_departamento),int(r.id_producto),
                    r.validacion,r.causa_modificacion,int(r.id_registro)) for r in cambios_df.itertuples()]
                cur.executemany('UPDATE operaciones SET fecha=%s,cantidad=%s,id_departamento=%s,'
                    'id_producto=%s,validacion=%s,causa_modificacion=%s WHERE id_registro=%s',valores)
                # La limpieza ya se calculó en Pandas; el SQL asigna regiones y valida la estructura.
                cur.execute((BASE/'sql/03-limpieza.sql').read_text())
                cur.execute((BASE/'sql/04-vista.sql').read_text())
                cur.execute("SELECT (SELECT count(*) FROM operaciones),(SELECT count(*) FROM vista_operaciones),(SELECT count(*) FROM operaciones WHERE validacion='modificado')")
                control=cur.fetchone(); assert control==(len(originales),len(originales),len(cambios_df)),control
                print(f'CONTROL: operaciones = {control[0]}; vista = {control[1]}; modificados = {control[2]}; '
                    f'válidos sin cambios = {control[0]-control[2]}.',flush=True)
                exportar(cur,'SELECT * FROM vista_operaciones ORDER BY id_registro',salida/'operaciones_limpias.csv')
                cambios=exportar(cur,"SELECT id_registro,validacion,causa_modificacion FROM operaciones WHERE validacion='modificado' ORDER BY id_registro",salida/'correcciones.csv')
                resultados={}
                for script in sorted((BASE/'sql').glob('07-*.sql')):
                    resultados[script.stem]=exportar(cur,script.read_text(),salida/(script.stem+'.csv'))
                for tabla in ['regiones','departamentos','municipios','productos']:
                    exportar(cur,'SELECT * FROM '+tabla+' ORDER BY 1',salida/(tabla+'.csv'))
                resumen=exportar(cur,"SELECT count(*) AS registros,sum(cantidad) AS unidades,sum(venta) AS monto,min(fecha) AS fecha_inicial,max(fecha) AS fecha_final FROM vista_operaciones",salida/'resumen.csv')[0]
                (salida/'consultas.json').write_text(json.dumps(resultados,ensure_ascii=False,indent=2,default=str))
                (salida/'resumen.json').write_text(json.dumps(resumen,ensure_ascii=False,indent=2,default=str))
                (salida/'correcciones.json').write_text(json.dumps(cambios,ensure_ascii=False,indent=2))
        print('CONFIRMADO. Duración total ms:',round((time.perf_counter()-inicio)*1000,3),flush=True)
    finally:
        conn.close()

if __name__=='__main__': main()
