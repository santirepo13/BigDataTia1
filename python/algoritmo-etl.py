import csv
import argparse
import time
import re
import unicodedata
from datetime import date
from pathlib import Path
import pandas as pd
from conexion import connect

BASE = Path(__file__).resolve().parents[1]
REGIONS = {
    'Region Eje Cafetero - Antioquia': 1,
    'Region Centro Oriente': 2,
    'Region Centro Sur': 3,
    'Region Caribe': 4,
    'Region Llano': 5,
    'Region Pacifico': 6
}

ISSUE_TYPES = {
    'A': ('date', 'Date not in YYYY-MM-DD format or missing'),
    'B': ('quantity', 'Quantity is zero or missing'),
    'C': ('quantity', 'Negative quantity'),
    'D': ('department_id', 'Missing department code'),
    'E': ('product_id', 'Missing product code'),
    'F': ('id_registro', 'Duplicate operation identifier'),
    'G': ('id_municipio', 'Municipality code is missing or unknown'),
    'H': ('id_region', 'Region code is missing or inconsistent'),
    'I': ('id_departamento', 'Department code is not an integer'),
    'J': ('id_producto', 'Product code is not an integer'),
    'K': ('nombre', 'Catalog name is empty'),
}


def is_date_valid(value):
    text = str(value)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def detect_issues(data):
    quantity = pd.to_numeric(data['cantidad'], errors='coerce')
    department = pd.to_numeric(data['id_departamento'], errors='coerce')
    product = pd.to_numeric(data['id_producto'], errors='coerce')
    operation_id = pd.to_numeric(data['id_registro'], errors='coerce')
    municipality = pd.to_numeric(data['id_municipio'], errors='coerce')
    region = pd.to_numeric(data['id_region'], errors='coerce')
    department_text = data['id_departamento'].astype('string')
    product_text = data['id_producto'].astype('string')
    return {
        'A': ~data['fecha'].map(is_date_valid),
        'B': quantity.isna() | quantity.eq(0),
        'C': quantity.lt(0),
        'D': department.isna() | department.eq(0),
        'E': product.isna() | product.eq(0),
        'F': operation_id.duplicated(keep=False),
        'G': municipality.isna() | municipality.eq(0),
        'H': region.isna() | region.eq(0),
        'I': data['id_departamento'].notna() & ~department_text.str.fullmatch(r'\d+'),
        'J': data['id_producto'].notna() & ~product_text.str.fullmatch(r'\d+'),
    }


def summarize_issues(data):
    masks = detect_issues(data)
    summary = pd.DataFrame([
        {'type': issue_type, 'problem': ISSUE_TYPES[issue_type][1], 'count': int(mask.sum())}
        for issue_type, mask in masks.items()
    ])
    affected = pd.concat(masks.values(), axis=1).any(axis=1)
    return summary, int(affected.sum())


def normalize_name(value):
    return ''.join(character for character in unicodedata.normalize('NFD', str(value))
                   if unicodedata.category(character) != 'Mn').upper().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ambiguous-date', choices=['day-month', 'month-day'],
        help='Explicit decision for ambiguous dates. Default: day-month.')
    arguments = parser.parse_args()
    if arguments.ambiguous_date is None:
        arguments.ambiguous_date = 'day-month'

    start_time = time.perf_counter()
    output_directory = BASE / 'resultados'
    output_directory.mkdir(exist_ok=True)

    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT version(), current_database()')
                print('ENVIRONMENT:', cursor.fetchone(), flush=True)
                cursor.execute((BASE / 'originales/script-base-datos-creacion.sql').read_text(encoding='utf-8-sig'))
                cursor.execute((BASE / 'sql/02-regiones.sql').read_text())

                corrected_csv_lines = []
                with (BASE / 'datos/colombia-dane-departamentos.csv').open(encoding='utf-8-sig', newline='') as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)
                    for line_number, row in enumerate(reader, start=2):
                        if len(row) == 1:
                            row = next(csv.reader(row))
                            corrected_csv_lines.append(line_number)
                        if len(row) != 5:
                            raise ValueError(f'Invalid CSV at line {line_number}: {row}')
                        region, department_code, department_name, municipality_code, municipality_name = row
                        cursor.execute(
                            'INSERT INTO temporal VALUES (%s,%s,%s,%s,%s,%s)',
                            (department_code, municipality_code, REGIONS[region], department_name, municipality_name, region)
                        )
                print('CSV: 1123 rows; quotes fixed in lines', corrected_csv_lines, flush=True)

                cursor.execute('SELECT COUNT(*) FROM regiones')
                if cursor.fetchone()[0] == 0:
                    cursor.executemany('INSERT INTO regiones VALUES (%s,%s)', [(value, key) for key, value in REGIONS.items()])
                cursor.execute('SELECT COUNT(*) FROM departamentos')
                if cursor.fetchone()[0] == 0:
                    cursor.execute('SELECT codigo_dep, departamento, codigo_region, count(*) FROM temporal GROUP BY 1,2,3 ORDER BY departamento')
                    for row in cursor.fetchall():
                        department_id = int('57' + str(row[0]).zfill(2))
                        cursor.execute(
                            'INSERT INTO departamentos (id_departamento, nombre, codigo_dane, codigo_region) VALUES (%s,%s,%s,%s)',
                            (department_id, row[1], row[0], row[2])
                        )
                cursor.execute('SELECT COUNT(*) FROM municipios')
                if cursor.fetchone()[0] == 0:
                    cursor.execute('SELECT codigo_dep, codigo_mun, municipio FROM temporal ORDER BY departamento COLLATE "C", municipio COLLATE "C"')
                    previous_department, municipality_counter = None, 0
                    for department_code, municipality_code, municipality_name in cursor.fetchall():
                        municipality_counter = municipality_counter + 1 if department_code == previous_department else 1
                        previous_department = department_code
                        department_id = int('57' + str(department_code).zfill(2))
                        municipality_id = int(str(department_id) + str(municipality_counter).zfill(3))
                        cursor.execute(
                            'INSERT INTO municipios (id_departamento, id_municipio, nombre, codigo_dane) VALUES (%s,%s,%s,%s)',
                            (department_id, municipality_id, municipality_name, municipality_code)
                        )
                cursor.execute("SELECT id_municipio FROM municipios WHERE nombre='Tamesis' AND id_departamento=5705")
                assert cursor.fetchone()[0] == 5705108, 'Municipal numbering does not match sales data.'
                cursor.execute('SELECT COUNT(*) FROM operaciones')
                if cursor.fetchone()[0] == 0:
                    operations_sql = (BASE / 'datos/script-base-datos-operaciones.sql').read_text(encoding='utf-8-sig')
                    insert_statements = '\n'.join(line for line in operations_sql.splitlines() if line.startswith('INSERT INTO public.operaciones'))
                    cursor.execute(insert_statements)
                cursor.execute('UPDATE operaciones o SET id_region=d.codigo_region FROM departamentos d WHERE o.id_departamento=d.id_departamento')
                cursor.execute('DROP VIEW IF EXISTS vista_operaciones')
                cursor.execute((BASE / 'sql/04-script-base-datos-vista.sql').read_text())

                for table_name in ['regiones', 'departamentos', 'municipios', 'productos']:
                    cursor.execute('SELECT * FROM ' + table_name + ' ORDER BY 1')
                    column_names = [column.name for column in cursor.description]
                    records = cursor.fetchall()
                    with (output_directory / (table_name + '.csv')).open('w', encoding='utf-8-sig', newline='') as output_file:
                        writer = csv.writer(output_file)
                        writer.writerow(column_names)
                        writer.writerows(records)
                cursor.execute('SELECT * FROM operaciones ORDER BY id_registro')
                column_names = [column.name for column in cursor.description]
                records = cursor.fetchall()
                with (output_directory / 'operaciones.csv').open('w', encoding='utf-8-sig', newline='') as output_file:
                    writer = csv.writer(output_file)
                    writer.writerow(column_names)
                    writer.writerows(records)
                print('LOADED: operations =', len(records), flush=True)

                data = pd.DataFrame(records, columns=column_names)
                summary, affected_count = summarize_issues(data)
                print('\nISSUE DETECTION (A-E)\n' + summary.to_string(index=False), flush=True)
                print('Distinct records with issues:', affected_count, flush=True)
                findings = pd.DataFrame({
                    'id_registro': data['id_registro'],
                    'issue_types': [';'.join(issue_type for issue_type, mask in detect_issues(data).items() if mask.iloc[index])
                                    for index in range(len(data))]
                })
                findings.to_csv(output_directory / 'issue_findings.csv', index=False, encoding='utf-8-sig')
                query_results = {}
                for query_file in sorted((BASE / 'sql').glob('07-*.sql')):
                    cursor.execute(query_file.read_text())
                    column_names = [column.name for column in cursor.description]
                    query_results[query_file.stem] = [dict(zip(column_names, row)) for row in cursor.fetchall()]
                    with (output_directory / (query_file.stem + '.csv')).open('w', encoding='utf-8-sig', newline='') as output_file:
                        writer = csv.writer(output_file)
                        writer.writerow(column_names)
                        writer.writerows([list(row.values()) for row in query_results[query_file.stem]])
                cursor.execute("SELECT count(*) AS records, sum(cantidad) AS units, sum(venta) AS amount, min(fecha) AS initial_date, max(fecha) AS final_date FROM vista_operaciones")
                final_summary = dict(zip(['records', 'units', 'amount', 'initial_date', 'final_date'], cursor.fetchone()))
                with (output_directory / 'summary.csv').open('w', encoding='utf-8-sig', newline='') as output_file:
                    writer = csv.writer(output_file)
                    writer.writerow(final_summary.keys())
                    writer.writerow(final_summary.values())
                print('COMPLETED. Total duration ms:', round((time.perf_counter() - start_time) * 1000, 3), flush=True)
    finally:
        connection.close()


if __name__ == '__main__':
    main()
