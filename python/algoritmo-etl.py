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
    'A': ('fecha', 'Date not in YYYY-MM-DD format or missing'),
    'B': ('cantidad', 'Quantity is zero or missing'),
    'C': ('cantidad', 'Negative quantity'),
    'D': ('id_departamento', 'Missing department code'),
    'E': ('id_producto', 'Missing product code'),
    'F': ('id_registro', 'Duplicate operation identifier'),
    'G': ('id_municipio', 'Municipality code is missing or unknown'),
    'H': ('id_region', 'Region code is missing or inconsistent'),
    'I': ('id_departamento', 'Department code is not an integer'),
    'J': ('id_producto', 'Product code is not an integer'),
    'K': ('id_registro', 'Operation identifier is missing, zero, or negative'),
    'L': ('id_departamento', 'Department code is not present in the catalog'),
    'M': ('id_municipio', 'Municipality code is not present in the catalog'),
    'N': ('id_producto', 'Product code is not present in the catalog'),
    'O': ('id_region', 'Region code is unknown or inconsistent with the department'),
    'P': ('id_departamento', 'Municipality does not belong to the informed department'),
    'Q': ('estado', 'State is missing or invalid'),
    'R': ('validacion', 'Validation status is missing or invalid'),
    'S': ('causa_modificacion', 'Modification reason is inconsistent with the validation status'),
    'T': ('fecha', 'Date has a valid format but is in the future'),
}

VALID_STATES = {'F'}
VALID_VALIDATIONS = {'valido', 'modificado', 'pendiente'}


def is_date_valid(value):
    text = str(value)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return False
    try:
        date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _catalog_id_set(frame, column):
    if frame is None or column not in frame.columns or frame.empty:
        return set()
    return set(pd.to_numeric(frame[column], errors='coerce').dropna().astype('int64').tolist())


def _catalog_map(frame, key, value):
    if frame is None or key not in frame.columns or value not in frame.columns or frame.empty:
        return {}
    keys = pd.to_numeric(frame[key], errors='coerce')
    values = pd.to_numeric(frame[value], errors='coerce')
    return {float(k): float(v) for k, v in zip(keys, values) if pd.notna(k) and pd.notna(v)}


def _is_future(value, today):
    try:
        return date.fromisoformat(str(value)) > today
    except (ValueError, TypeError):
        return False


def detect_issues(data, departments=None, municipalities=None, products=None, regions=None):
    quantity = pd.to_numeric(data['cantidad'], errors='coerce')
    department = pd.to_numeric(data['id_departamento'], errors='coerce')
    product = pd.to_numeric(data['id_producto'], errors='coerce')
    operation_id = pd.to_numeric(data['id_registro'], errors='coerce')
    municipality = pd.to_numeric(data['id_municipio'], errors='coerce')
    region = pd.to_numeric(data['id_region'], errors='coerce')
    department_text = data['id_departamento'].astype('string')
    product_text = data['id_producto'].astype('string')
    state = data['estado'].astype('string').fillna('')
    has_status = 'validacion' in data.columns
    status = data['validacion'].astype('string').fillna('') if has_status else pd.Series('', index=data.index)
    cause = data['causa_modificacion'].astype('string').fillna('') if 'causa_modificacion' in data.columns else pd.Series('', index=data.index)
    no_status = pd.Series(False, index=data.index)
    today = date.today()
    masks = {
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
        'K': operation_id.isna() | operation_id.le(0),
        'Q': ~state.isin(VALID_STATES),
        'R': no_status if not has_status else ~status.isin(VALID_VALIDATIONS),
        'S': no_status if not has_status else (
            (status.eq('modificado') & cause.str.strip().eq(''))
            | (status.eq('valido') & cause.str.strip().ne(''))),
        'T': data['fecha'].map(lambda value: _is_future(value, today)),
    }
    valid_departments = _catalog_id_set(departments, 'id_departamento')
    valid_municipalities = _catalog_id_set(municipalities, 'id_municipio')
    valid_products = _catalog_id_set(products, 'id_producto')
    valid_regions = _catalog_id_set(regions, 'id_region')
    if valid_departments:
        masks['L'] = department.notna() & department.ne(0) & ~department.isin(valid_departments)
    if valid_municipalities:
        masks['M'] = municipality.notna() & municipality.ne(0) & ~municipality.isin(valid_municipalities)
    if valid_products:
        masks['N'] = product.notna() & product.ne(0) & ~product.isin(valid_products)
    department_region = _catalog_map(departments, 'id_departamento', 'codigo_region')
    if department_region:
        expected_region = department.map(department_region)
        masks['O'] = region.notna() & expected_region.notna() & region.ne(expected_region)
        if valid_regions:
            masks['O'] = masks['O'] | (region.notna() & ~region.isin(valid_regions))
    municipality_department = _catalog_map(municipalities, 'id_municipio', 'id_departamento')
    if municipality_department:
        expected_department = municipality.map(municipality_department)
        masks['P'] = department.gt(0) & expected_department.notna() & department.ne(expected_department)
    return masks


def summarize_issues(data, departments=None, municipalities=None, products=None, regions=None):
    masks = detect_issues(data, departments, municipalities, products, regions)
    summary = pd.DataFrame([
        {'type': issue_type, 'problem': ISSUE_TYPES[issue_type][1], 'count': int(mask.sum())}
        for issue_type, mask in masks.items()
    ])
    affected = pd.concat(masks.values(), axis=1).any(axis=1)
    return summary, int(affected.sum())


def detect_catalog_issues(departments, municipalities, products, regions):
    findings = []

    def add(table, field, problem, mask):
        findings.append({'table': table, 'field': field, 'problem': problem, 'count': int(mask.sum())})

    def empty(series):
        return series.isna() | series.astype('string').str.strip().eq('')

    if departments is not None and not departments.empty:
        add('departamentos', 'id_departamento', 'Duplicate identifier', departments['id_departamento'].duplicated(keep=False))
        add('departamentos', 'nombre', 'Missing or empty name', empty(departments['nombre']))
        add('departamentos', 'nombre', 'Duplicate name', departments['nombre'].duplicated(keep=False))
        add('departamentos', 'codigo_dane', 'Missing or empty DANE code', empty(departments['codigo_dane']))
        add('departamentos', 'codigo_dane', 'Duplicate DANE code', departments['codigo_dane'].duplicated(keep=False))
        add('departamentos', 'codigo_region', 'Region outside 1..6 or missing', ~pd.to_numeric(departments['codigo_region'], errors='coerce').isin([1, 2, 3, 4, 5, 6]))
        if 'poblacion' in departments.columns:
            add('departamentos', 'poblacion', 'Population not informed (zero)', pd.to_numeric(departments['poblacion'], errors='coerce').fillna(0).eq(0))
        if 'abb' in departments.columns:
            add('departamentos', 'abb', 'Abbreviation not informed', empty(departments['abb']))
    if municipalities is not None and not municipalities.empty:
        add('municipios', 'id_municipio', 'Duplicate identifier', municipalities['id_municipio'].duplicated(keep=False))
        valid_departments = _catalog_id_set(departments, 'id_departamento')
        if valid_departments:
            department_of_municipality = pd.to_numeric(municipalities['id_departamento'], errors='coerce')
            add('municipios', 'id_departamento', 'Unknown department', department_of_municipality.isna() | ~department_of_municipality.isin(valid_departments))
        add('municipios', 'nombre', 'Missing or empty name', empty(municipalities['nombre']))
        add('municipios', 'nombre', 'Duplicate name within department', municipalities.duplicated(subset=['id_departamento', 'nombre'], keep=False))
        add('municipios', 'codigo_dane', 'Missing or empty DANE code', empty(municipalities['codigo_dane']))
        add('municipios', 'codigo_dane', 'Duplicate DANE code', municipalities['codigo_dane'].duplicated(keep=False))
        if 'poblacion' in municipalities.columns:
            add('municipios', 'poblacion', 'Population not informed (zero)', pd.to_numeric(municipalities['poblacion'], errors='coerce').fillna(0).eq(0))
        if 'abb' in municipalities.columns:
            add('municipios', 'abb', 'Abbreviation not informed', empty(municipalities['abb']))
    if products is not None and not products.empty:
        add('productos', 'id_producto', 'Duplicate identifier', products['id_producto'].duplicated(keep=False))
        add('productos', 'nombre', 'Missing or empty name', empty(products['nombre']))
        add('productos', 'nombre', 'Duplicate name', products['nombre'].duplicated(keep=False))
        if 'precio' in products.columns:
            unit_price = pd.to_numeric(products['precio'], errors='coerce')
            add('productos', 'precio', 'Missing, zero, or negative price', unit_price.isna() | unit_price.le(0))
    if regions is not None and not regions.empty:
        add('regiones', 'id_region', 'Duplicate identifier', regions['id_region'].duplicated(keep=False))
        add('regiones', 'id_region', 'Region outside 1..6', ~pd.to_numeric(regions['id_region'], errors='coerce').isin([1, 2, 3, 4, 5, 6]))
        add('regiones', 'nombre', 'Missing or empty name', empty(regions['nombre']))
        add('regiones', 'nombre', 'Duplicate name', regions['nombre'].duplicated(keep=False))
    return pd.DataFrame(findings)


def read_table(cursor, table_name):
    cursor.execute('SELECT * FROM ' + table_name + ' ORDER BY 1')
    return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])


def normalize_name(value):
    return ''.join(character for character in unicodedata.normalize('NFD', str(value))
                   if unicodedata.category(character) != 'Mn').upper().strip()


def abbreviation(value):
    letters = ''.join(character for character in normalize_name(value) if character.isalnum())
    return letters[:3]


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
                            'INSERT INTO departamentos (id_departamento, nombre, abb, codigo_dane, codigo_region) VALUES (%s,%s,%s,%s,%s)',
                            (department_id, row[1], abbreviation(row[1]), row[0], row[2])
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
                            'INSERT INTO municipios (id_departamento, id_municipio, nombre, abb, codigo_dane) VALUES (%s,%s,%s,%s,%s)',
                            (department_id, municipality_id, municipality_name, abbreviation(municipality_name), municipality_code)
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
                departments = read_table(cursor, 'departamentos')
                municipalities = read_table(cursor, 'municipios')
                products = read_table(cursor, 'productos')
                regions = read_table(cursor, 'regiones')
                summary, affected_count = summarize_issues(data, departments, municipalities, products, regions)
                print('\nISSUE DETECTION (A-T)\n' + summary.to_string(index=False), flush=True)
                print('Distinct records with issues:', affected_count, flush=True)
                catalog_summary = detect_catalog_issues(departments, municipalities, products, regions)
                print('\nCATALOG FIELD CHECKS\n' + catalog_summary.to_string(index=False), flush=True)
                masks = detect_issues(data, departments, municipalities, products, regions)
                findings = pd.DataFrame({
                    'id_registro': data['id_registro'],
                    'issue_types': [';'.join(issue for issue, mask in masks.items() if bool(mask.iloc[index]))
                                    for index in range(len(data))],
                })
                findings.to_csv(output_directory / 'issue_findings.csv', index=False, encoding='utf-8-sig')
                catalog_summary.to_csv(output_directory / 'catalog_findings.csv', index=False, encoding='utf-8-sig')
                print('Detection results saved to resultados/issue_findings.csv (' +
                      str(int(findings['issue_types'].ne('').sum())) + ' records) and catalog_findings.csv', flush=True)
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
