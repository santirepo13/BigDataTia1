"""Cleans operations with Pandas and displays the results in the console."""
import re
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import pandas as pd
from conexion import connect


ISSUE_TYPES = {
    'A': ('date', 'Date outside YYYY-MM-DD format or missing'),
    'B': ('quantity', 'Quantity is zero or missing'),
    'C': ('quantity', 'Negative quantity'),
    'D': ('department_id', 'Missing department code'),
    'E': ('product_id', 'Missing product code'),
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
    return {
        'A': ~data['fecha'].map(is_date_valid),
        'B': quantity.isna() | quantity.eq(0),
        'C': quantity.lt(0),
        'D': department.isna() | department.eq(0),
        'E': product.isna() | product.eq(0),
    }


def summarize_issues(data):
    masks = detect_issues(data)
    summary = pd.DataFrame([
        {'type': issue_type, 'problem': ISSUE_TYPES[issue_type][1], 'count': int(mask.sum())}
        for issue_type, mask in masks.items()
    ])
    affected = pd.concat(masks.values(), axis=1).any(axis=1)
    return summary, int(affected.sum())


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


def clean(operations, municipalities, departments, products, ambiguous_order=None):
    data = operations.copy(deep=True).reset_index(drop=True)
    originals = data.copy(deep=True)
    for field in ['id_registro', 'id_municipio', 'cantidad', 'id_departamento', 'id_producto']:
        data[field] = pd.to_numeric(data[field], errors='coerce')
    if data['id_registro'].isna().any() or data['id_registro'].duplicated().any():
        raise ValueError('Operation identifiers are empty or duplicated.')
    for catalog, key in ((municipalities, 'id_municipio'), (departments, 'id_departamento'), (products, 'id_producto')):
        if catalog[key].duplicated().any():
            raise ValueError('The catalog contains duplicated codes: ' + key)
    data['validacion'] = 'valido'
    data['causa_modificacion'] = ''
    issues = detect_issues(data)
    findings_file = Path(__file__).resolve().parents[1] / 'resultados' / 'issue_findings.csv'
    if findings_file.is_file():
        findings = pd.read_csv(findings_file, encoding='utf-8-sig').set_index('id_registro')['issue_types']
        issue_labels = data['id_registro'].map(findings).fillna('')
        issues = {issue_type: issue_labels.str.contains(issue_type, regex=False) for issue_type in ISSUE_TYPES}
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
    columns = ['type', 'id_registro', 'field', 'problem', 'original_value', 'corrected_value', 'criterion', 'status']
    details = pd.DataFrame(audit, columns=columns).sort_values(['id_registro', 'type'])
    pending_ids = details.loc[details['status'].eq('pending'), 'id_registro']
    data.loc[data['id_registro'].isin(pending_ids), 'validacion'] = 'pendiente'
    return data, details


def read_query(cursor, query, parameters=None):
    cursor.execute(query, parameters)
    return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])


def main():
    connection = connect()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT current_database()')
                print('DATABASE:', cursor.fetchone()[0])
                data = read_query(cursor, 'SELECT * FROM operaciones ORDER BY id_registro FOR UPDATE')
                summary, affected = summarize_issues(data)
                print('\nBEFORE CORRECTION\n' + summary.to_string(index=False))
                if affected == 0:
                    print('\nNo issues of the five types were found. No changes were made.')
                    return
                municipalities = read_query(cursor, 'SELECT * FROM municipios')
                departments = read_query(cursor, 'SELECT * FROM departamentos')
                products = read_query(cursor, 'SELECT * FROM productos')
                cleaned_data, details = clean(data, municipalities, departments, products, 'day-month')
                print('\nCHANGES CALCULATED WITH PANDAS\n' + details.to_string(index=False))
                if details['status'].eq('pending').any():
                    raise RuntimeError('Pending cases remain. The transaction is reverted.')
                changes = cleaned_data.loc[cleaned_data['validacion'].eq('modificado')]
                original_data = data.set_index('id_registro')
                for row in changes.itertuples():
                    previous_reason = original_data.loc[row.id_registro].get('causa_modificacion', '')
                    previous_reason = '' if pd.isna(previous_reason) else str(previous_reason)
                    reason = previous_reason + (' | ' if previous_reason else '') + row.causa_modificacion
                    cursor.execute('UPDATE operaciones SET fecha=%s,cantidad=%s,id_departamento=%s,'
                                   'id_producto=%s,validacion=%s,causa_modificacion=%s WHERE id_registro=%s',
                                   (str(row.fecha), int(row.cantidad), int(row.id_departamento), int(row.id_producto),
                                    'modificado', reason, int(row.id_registro)))
                cursor.execute('UPDATE operaciones o SET id_region=d.codigo_region FROM departamentos d WHERE o.id_departamento=d.id_departamento AND o.id_region IS DISTINCT FROM d.codigo_region')
                after_data = read_query(cursor, 'SELECT * FROM operaciones ORDER BY id_registro')
                control, remaining = summarize_issues(after_data)
                if remaining or len(after_data) != len(data):
                    raise RuntimeError('Final verification failed; the transaction is reverted.')
                ids = [int(value) for value in changes['id_registro']]
        with connection.cursor() as cursor:
            saved = read_query(cursor, 'SELECT id_registro,fecha,cantidad,id_departamento,id_producto,validacion FROM operaciones WHERE id_registro=ANY(%s) ORDER BY id_registro', (ids,))
        print(f'\nCOMMIT CONFIRMED: {len(ids)} records corrected in PostgreSQL.')
        print('\nSAVED DATABASE VALUES\n' + saved.to_string(index=False))
        print('\nREMAINING ISSUES\n' + control.to_string(index=False))
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f'ERROR - Cleaning interrupted: {error}')
        raise SystemExit(1)
