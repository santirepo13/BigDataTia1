"""Checks data and queries; only reads PostgreSQL and displays results."""
from pathlib import Path
import re
from conexion import connect

BASE = Path(__file__).resolve().parents[1]
QUERIES = [
    '07-1-departamentos-monto.sql',
    '07-2-antioquia-municipios.sql',
    '07-3-manzaloca.sql',
    '07-4-menores-municipios.sql',
    '07-5-productos-regiones.sql',
    '07-6-antioquia-productos.sql',
]
DIRECT_QUERY = '''(
    SELECT o.id_registro, o.id_departamento, d.nombre AS departamento,
           o.id_municipio, m.nombre AS municipio, o.id_producto,
           p.nombre AS producto, o.fecha, o.cantidad, p.precio,
           o.cantidad::bigint * p.precio AS venta, o.estado,
           o.id_region, r.nombre AS region, o.validacion,
           o.causa_modificacion
    FROM public.operaciones o
    JOIN public.departamentos d ON d.id_departamento = o.id_departamento
    JOIN public.municipios m ON m.id_municipio = o.id_municipio
                           AND m.id_departamento = o.id_departamento
    JOIN public.productos p ON p.id_producto = o.id_producto
    JOIN public.regiones r ON r.id_region = o.id_region
) AS independent_query'''


def main():
    failures = 0

    def check(name, correct, detail=''):
        nonlocal failures
        failures += not correct
        print(f"{'OK' if correct else 'ERROR'} - {name}" +
              (f': {detail}' if detail else ''))

    connection = connect()
    try:
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            print('Database:', cursor.fetchone()[0])
            cursor.execute('''SELECT count(*), count(DISTINCT id_registro),
                count(*) FILTER (WHERE cantidad IS NULL OR cantidad <= 0
                    OR id_departamento IS NULL OR id_departamento = 0
                    OR id_producto IS NULL OR id_producto = 0
                    OR id_region IS NULL OR id_region = 0)
                FROM public.operaciones''')
            total, unique_ids, problems = cursor.fetchone()
            check('10,000 operations and unique identifiers',
                  total == unique_ids == 10000, f'{total} rows; {unique_ids} IDs')
            check('Complete quantities and codes', problems == 0,
                  f'{problems} records with problems')
            cursor.execute('SELECT fecha::text FROM public.operaciones')
            from datetime import date
            invalid_dates = 0
            for (date_value,) in cursor.fetchall():
                try:
                    if not date_value or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_value):
                        raise ValueError()
                    date.fromisoformat(date_value)
                except ValueError:
                    invalid_dates += 1
            check('Valid dates YYYY-MM-DD', invalid_dates == 0,
                  f'{invalid_dates} dates with problems')
            cursor.execute('''SELECT
                (SELECT count(*) FROM public.vista_operaciones),
                (SELECT count(*) FROM (
                    (SELECT id_registro FROM public.operaciones
                     EXCEPT ALL SELECT id_registro FROM public.vista_operaciones)
                    UNION ALL
                    (SELECT id_registro FROM public.vista_operaciones
                     EXCEPT ALL SELECT id_registro FROM public.operaciones)
                ) differences)''')
            view_rows, differences = cursor.fetchone()
            check('View preserves all records without duplicates',
                  view_rows == total and differences == 0,
                  f'{view_rows} rows; {differences} differences')
            cursor.execute('''SELECT
                count(*) FILTER (WHERE validacion = 'modificado'),
                count(*) FILTER (WHERE validacion = 'valido'),
                count(*) FILTER (WHERE NOT COALESCE(
                    (validacion = 'valido' AND causa_modificacion = '') OR
                    (validacion = 'modificado'
                     AND length(trim(causa_modificacion)) > 0), false))
                FROM public.operaciones''')
            modified, valid, inconsistent = cursor.fetchone()
            check('Correction status and cause',
                  modified == 30 and valid == 9970 and inconsistent == 0,
                  f'{modified} modified; {valid} valid; {inconsistent} inconsistent marks')
            for query_name in QUERIES:
                query_file = BASE / 'sql' / query_name
                if not query_file.is_file():
                    check(query_name, False, 'SQL file was not found')
                    continue
                query = query_file.read_text(encoding='utf-8-sig')
                direct_query, replacements = re.subn(
                    r'\bFROM\s+(?:public\.)?vista_operaciones\b',
                    lambda _: 'FROM ' + DIRECT_QUERY, query, flags=re.IGNORECASE)
                if replacements != 1:
                    check(query_name, False, 'Expected a FROM vista_operaciones query')
                    continue
                cursor.execute(query)
                view_result = cursor.fetchall()
                cursor.execute(direct_query)
                check(query_name, view_result == cursor.fetchall(),
                      f'{len(view_result)} rows; comparison with direct tables')
        print('\n' + ('All checks passed.' if failures == 0
                        else f'{failures} checks failed.'))
        return 0 if failures == 0 else 1
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f'ERROR - Verification interrupted: {error}')
        raise SystemExit(1)
