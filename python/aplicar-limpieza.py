'''Applies the corrections detected by algoritmo-etl.py (resultados/issue_findings.csv).'''
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd
from conexion import connect


ISSUE_TYPES = {
    'A': ('fecha', 'Date outside YYYY-MM-DD format or missing'),
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


def read_query(cursor, query, parameters=None):
    cursor.execute(query, parameters)
    return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])


def load_findings():
    findings_file = Path(__file__).resolve().parents[1] / 'resultados' / 'issue_findings.csv'
    if not findings_file.is_file():
        raise FileNotFoundError('resultados/issue_findings.csv not found. Run algoritmo-etl.py first.')
    return pd.read_csv(findings_file, encoding='utf-8-sig').set_index('id_registro')['issue_types']


def normalize_date(value, years, ambiguous_order=None):
    parts = str(value).strip().split('-')
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None, 'Unrecognized format; review the source.'
    year_positions = []
    endpoints = [position for position in (0, 2) if len(parts[position]) == 4] or [0, 2]
    for position in endpoints:
        text = parts[position]
        if len(text) == 4:
            year_positions.append((position, int(text)))
        elif len(text) in (2, 3):
            matches = [year for year in years if year % (10 ** len(text)) == int(text)]
            if len(matches) == 1:
                year_positions.append((position, matches[0]))
    if len(year_positions) != 1:
        return None, 'The year cannot be determined from valid dataset values.'
    year_position, year = year_positions[0]
    year_note = '' if len(parts[year_position]) == 4 else f' Year {year} based on complete dataset dates.'
    candidates = {}

    def add_candidate(order, month, day):
        try:
            candidates[order] = date(year, month, day).isoformat()
        except ValueError:
            pass

    if year_position == 0:
        second, third = int(parts[1]), int(parts[2])
        if second <= 12:
            add_candidate('year-month-day', second, third)
        else:
            add_candidate('year-day-month', third, second)
    else:
        first, second = int(parts[0]), int(parts[1])
        add_candidate('day-month', second, first)
        add_candidate('month-day', first, second)
    unique_values = set(candidates.values())
    if len(unique_values) == 1:
        return next(iter(unique_values)), 'Normalization by format and calendar.' + year_note
    if len(unique_values) > 1:
        options = '; '.join(f'{key}: {value}' for key, value in candidates.items())
        if ambiguous_order in candidates:
            return candidates[ambiguous_order], f'Ambiguous date ({options}); explicit decision: {ambiguous_order}.' + year_note
        return None, f'Ambiguous date ({options}); explicit decision required.'
    return None, 'Impossible calendar date; review the source.'


def normalize_name(value):
    return ''.join(character for character in unicodedata.normalize('NFD', str(value))
                   if unicodedata.category(character) != 'Mn').upper().strip()


def abbreviation(value):
    letters = ''.join(character for character in normalize_name(value) if character.isalnum())
    return letters[:3]


def clean_catalogs(cursor, default_population=10000):
    repairs = []
    for table, key in (('departamentos', 'id_departamento'), ('municipios', 'id_municipio')):
        rows = read_query(cursor, f'SELECT {key}, nombre, abb, poblacion FROM {table} ORDER BY {key}')
        missing_abbreviation = rows['abb'].isna() | rows['abb'].astype('string').str.strip().eq('')
        zero_population = pd.to_numeric(rows['poblacion'], errors='coerce').fillna(0).eq(0)
        for index, record in rows.iterrows():
            identifier = int(record[key])
            if missing_abbreviation.at[index]:
                value = abbreviation(record['nombre'])
                cursor.execute(f'UPDATE {table} SET abb=%s WHERE {key}=%s', (value, identifier))
                repairs.append({'table': table, 'field': 'abb', 'id': identifier, 'value': value})
            if zero_population.at[index]:
                cursor.execute(f'UPDATE {table} SET poblacion=%s WHERE {key}=%s', (default_population, identifier))
                repairs.append({'table': table, 'field': 'poblacion', 'id': identifier, 'value': default_population})
    return pd.DataFrame(repairs)


def clean(operations, findings, municipalities, departments, products, ambiguous_order=None):
    data = operations.copy(deep=True).reset_index(drop=True)
    originals = data.copy(deep=True)
    for field in ['id_registro', 'id_municipio', 'cantidad', 'id_departamento', 'id_producto']:
        data[field] = pd.to_numeric(data[field], errors='coerce')
    issue_labels = data['id_registro'].map(findings).fillna('')
    issues = {issue_type: issue_labels.str.contains(issue_type, regex=False) for issue_type in ISSUE_TYPES}
    data['validacion'] = 'valido'
    data['causa_modificacion'] = ''

    audit = []
    years = {int(str(value)[:4]) for value in data.loc[~issues['A'], 'fecha']}

    def record_change(index, issue_type, new_value, criterion):
        field = ISSUE_TYPES[issue_type][0]
        previous_value = originals.at[index, field]
        status = 'pending' if new_value is None else 'corrected'
        audit.append({'type': issue_type, 'id_registro': int(data.at[index, 'id_registro']),
                      'field': field, 'problem': ISSUE_TYPES[issue_type][1],
                      'original_value': previous_value, 'corrected_value': new_value,
                      'criterion': criterion, 'status': status})
        if new_value is None:
            previous_reason = data.at[index, 'causa_modificacion']
            data.at[index, 'causa_modificacion'] = previous_reason + (' | ' if previous_reason else '') + f'{issue_type}: pending. {criterion}'
            return
        data.at[index, field] = new_value
        data.at[index, 'validacion'] = 'modificado'
        reason = f'{issue_type}: {field} {previous_value} -> {new_value}. {criterion}'
        previous_reason = data.at[index, 'causa_modificacion']
        data.at[index, 'causa_modificacion'] = previous_reason + (' | ' if previous_reason else '') + reason

    for index in data.index[issues['A']]:
        new_value, criterion = normalize_date(data.at[index, 'fecha'], years, ambiguous_order)
        record_change(index, 'A', new_value, criterion)
    for index in data.index[issues['C']]:
        record_change(index, 'C', abs(int(data.at[index, 'cantidad'])), 'Remove the negative sign with abs().')
    positive_values = data.loc[data['cantidad'].gt(0)]
    averages = positive_values.groupby('id_municipio')['cantidad'].agg(['sum', 'count'])
    for index in data.index[issues['B']]:
        municipality = data.at[index, 'id_municipio']
        if municipality not in averages.index:
            record_change(index, 'B', None, 'The municipality has no positive quantities for an average.')
            continue
        group = averages.loc[municipality]
        average = Decimal(int(group['sum'])) / Decimal(int(group['count']))
        new_quantity = int(average.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        record_change(index, 'B', new_quantity, f'Municipal average {average:.6f} from {int(group["count"])} positive quantities; rounded to unit.')
    department_map = municipalities.set_index('id_municipio')['id_departamento']
    for index in data.index[issues['D']]:
        municipality = data.at[index, 'id_municipio']
        new_department = int(department_map[municipality]) if municipality in department_map.index else None
        record_change(index, 'D', new_department, 'Department obtained from the municipality catalog.' if new_department else 'Unknown municipality; review the source.')
    antioquia = departments.loc[departments['nombre'].map(normalize_name).eq('ANTIOQUIA'), 'id_departamento']
    tamesis = municipalities.loc[municipalities['nombre'].map(normalize_name).eq('TAMESIS') & municipalities['id_departamento'].isin(antioquia), 'id_municipio']
    naranjita = products.loc[products['nombre'].map(normalize_name).eq('NARANJITA'), 'id_producto']
    for index in data.index[issues['E']]:
        if data.at[index, 'id_municipio'] in set(tamesis) and len(naranjita) == 1:
            record_change(index, 'E', int(naranjita.iloc[0]), 'Case rule: only NARANJITA is sold in Támesis, Antioquia.')
        else:
            record_change(index, 'E', None, 'The Támesis rule cannot infer this product.')
    region_map = {}
    if 'codigo_region' in departments.columns:
        region_map = {int(k): int(v) for k, v in zip(
            pd.to_numeric(departments['id_departamento'], errors='coerce').dropna().astype('int64'),
            pd.to_numeric(departments['codigo_region'], errors='coerce').dropna().astype('int64'))}
    empty_mask = pd.Series(False, index=data.index)

    def department_from_municipality(index):
        municipality = data.at[index, 'id_municipio']
        return int(department_map[municipality]) if municipality in department_map.index else None

    for issue_type in ('L', 'P'):
        for index in data.index[issues.get(issue_type, empty_mask)]:
            new_department = department_from_municipality(index)
            record_change(index, issue_type, new_department,
                          'Department obtained from the municipality catalog.' if new_department
                          else 'Unknown municipality; review the source.')
    for index in data.index[issues.get('O', empty_mask)]:
        department = data.at[index, 'id_departamento']
        new_region = region_map.get(int(department)) if pd.notna(department) else None
        record_change(index, 'O', new_region,
                      'Region obtained from the department catalog.' if new_region
                      else 'Department region unknown; review the source.')
    for index in data.index[issues.get('N', empty_mask)]:
        if data.at[index, 'id_municipio'] in set(tamesis) and len(naranjita) == 1:
            record_change(index, 'N', int(naranjita.iloc[0]), 'Case rule: only NARANJITA is sold in Támesis, Antioquia.')
        else:
            record_change(index, 'N', None, 'The Támesis rule cannot infer this product.')
    for index in data.index[issues.get('Q', empty_mask)]:
        record_change(index, 'Q', 'F', 'The only valid state is F.')
    for index in data.index[issues.get('R', empty_mask)]:
        record_change(index, 'R', 'valido', 'Reset to the default validation status.')
    for index in data.index[issues.get('S', empty_mask)]:
        if str(data.at[index, 'validacion']) == 'modificado':
            record_change(index, 'S', None, 'Modified record without a documented cause.')
        else:
            record_change(index, 'S', '', 'Cleared cause for a valid record.')
    for issue_type, criterion in (
            ('K', 'Cannot infer a new operation identifier.'),
            ('M', 'Cannot infer the municipality; review the source.'),
            ('T', 'Future date cannot be inferred; review the source.')):
        for index in data.index[issues.get(issue_type, empty_mask)]:
            record_change(index, issue_type, None, criterion)
    columns = ['type', 'id_registro', 'field', 'problem', 'original_value', 'corrected_value', 'criterion', 'status']
    details = pd.DataFrame(audit, columns=columns).sort_values(['id_registro', 'type'])
    pending_ids = details.loc[details['status'].eq('pending'), 'id_registro']
    data.loc[data['id_registro'].isin(pending_ids), 'validacion'] = 'pendiente'
    return data, details


def main():
    findings = load_findings()
    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database()')
                print('DATABASE:', cursor.fetchone()[0], flush=True)
                data = read_query(cursor, 'SELECT * FROM operaciones ORDER BY id_registro FOR UPDATE')
                municipalities = read_query(cursor, 'SELECT * FROM municipios')
                departments = read_query(cursor, 'SELECT * FROM departamentos')
                products = read_query(cursor, 'SELECT * FROM productos')
                catalog_repairs = clean_catalogs(cursor)
                if not catalog_repairs.empty:
                    repair_summary = catalog_repairs.groupby(['table', 'field']).agg(count=('id', 'size')).reset_index()
                    print('CATALOG REPAIRS\n' + repair_summary.to_string(index=False), flush=True)
                cleaned_data, details = clean(data, findings, municipalities, departments, products, 'day-month')
                print('\nCHANGES CALCULATED WITH PANDAS\n' + details.to_string(index=False), flush=True)
                changes = cleaned_data.loc[cleaned_data['validacion'].eq('modificado')]
                original_data = data.set_index('id_registro')
                for row in changes.itertuples():
                    previous_reason = original_data.loc[row.id_registro].get('causa_modificacion', '')
                    previous_reason = '' if pd.isna(previous_reason) else str(previous_reason)
                    reason = previous_reason + (' | ' if previous_reason else '') + row.causa_modificacion
                    region_value = None if pd.isna(row.id_region) else int(row.id_region)
                    cursor.execute('UPDATE operaciones SET fecha=%s,cantidad=%s,id_departamento=%s,id_producto=%s,id_region=%s,estado=%s,validacion=%s,causa_modificacion=%s WHERE id_registro=%s',
                                   (str(row.fecha), int(row.cantidad), int(row.id_departamento), int(row.id_producto),
                                    region_value, str(row.estado), 'modificado', reason, int(row.id_registro)))
                cursor.execute('UPDATE operaciones o SET id_region=d.codigo_region FROM departamentos d WHERE o.id_departamento=d.id_departamento AND o.id_region IS DISTINCT FROM d.codigo_region')
                corrected = len(changes)
                repaired = len(catalog_repairs)
        print(f'\nCOMMIT CONFIRMED: {corrected} operations corrected, {repaired} catalog fields repaired.', flush=True)
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f'ERROR - Cleaning interrupted: {error}')
        raise SystemExit(1)
