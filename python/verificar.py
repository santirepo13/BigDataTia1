"""Verificaciones de integridad y comparación independiente de las consultas."""
import csv,json
from pathlib import Path
from conexion import conectar
BASE=Path(__file__).resolve().parents[1]
with conectar() as c:
 with c.cursor() as cur:
  cur.execute("SELECT count(*),count(DISTINCT id_registro),count(*) FILTER(WHERE cantidad<=0 OR fecha IS NULL OR id_region IS NULL) FROM operaciones")
  assert cur.fetchone()==(10000,10000,0)
  join='''(SELECT o.*, d.nombre departamento, m.nombre municipio,p.nombre producto,r.nombre region,
  o.cantidad::bigint*p.precio venta FROM operaciones o JOIN departamentos d USING(id_departamento)
  JOIN municipios m ON o.id_municipio=m.id_municipio JOIN productos p USING(id_producto)
  JOIN regiones r ON o.id_region=r.id_region) independiente'''
  consultas={}
  for f in sorted((BASE/'sql').glob('07-*.sql')):
   q=f.read_text();cur.execute(q); vista=cur.fetchall();nombres=[x.name for x in cur.description]
   consultas[f.stem]=[dict(zip(nombres,r)) for r in vista]
   with (BASE/'resultados'/(f.stem+'.csv')).open('w',encoding='utf-8-sig',newline='') as archivo:
    w=csv.writer(archivo);w.writerow(nombres);w.writerows(vista)
   cur.execute(q.replace('vista_operaciones',join));assert cur.fetchall()==vista,f.name
   print(f.name,'coincide con uniones directas;',len(vista),'filas')
  (BASE/'resultados/consultas.json').write_text(json.dumps(consultas,ensure_ascii=False,indent=2,default=str))
  cur.execute("SELECT table_name,column_name,data_type,character_maximum_length,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' AND table_name<>'vista_operaciones' ORDER BY table_name,ordinal_position")
  cols=[x.name for x in cur.description]
  (BASE/'resultados/diccionario_bd.json').write_text(json.dumps([dict(zip(cols,x)) for x in cur.fetchall()],ensure_ascii=False,indent=2,default=str))
  cur.execute("SELECT d.id_departamento,d.nombre,count(o.id_registro) registros,coalesce(sum(o.cantidad),0) unidades,coalesce(sum(o.cantidad::bigint*p.precio),0) monto FROM departamentos d LEFT JOIN operaciones o USING(id_departamento) LEFT JOIN productos p USING(id_producto) GROUP BY d.id_departamento,d.nombre ORDER BY monto DESC")
  cols=[x.name for x in cur.description]
  (BASE/'resultados/analisis_departamentos.json').write_text(json.dumps([dict(zip(cols,x)) for x in cur.fetchall()],ensure_ascii=False,indent=2,default=str))
  cur.execute("SELECT m.nombre,d.nombre departamento FROM municipios m JOIN departamentos d USING(id_departamento) LEFT JOIN operaciones o USING(id_municipio) WHERE o.id_registro IS NULL ORDER BY d.nombre,m.nombre")
  print('Municipios sin registros de venta (no equivalen a ventas cero):',cur.fetchall())
  cur.execute("SELECT count(*),min(id_registro),max(id_registro),min(cantidad),max(cantidad) FROM tamanio"); print('Última prueba de volumen:',cur.fetchone())
  print('Integridad, ausencia de pérdida y seis comparaciones SQL: CORRECTAS.')
