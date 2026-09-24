import random
import time
from psycopg2.extras import execute_values
from conexion import connect


def main():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT id_departamento, id_municipio FROM municipios ORDER BY id_municipio')
            municipalities = cursor.fetchall()
            if not municipalities:
                raise RuntimeError('Run the ETL first.')

            print(f'{"Records":>12} {"Time ms":>14} {"Table KiB":>14} {"Database MiB":>12} {"Table/database %":>14}')
            for record_count in (10000, 100000, 1000000, 10000000):
                cursor.execute('TRUNCATE public.tamanio')
                connection.commit()
                random.seed(20260923)
                rows = []
                start_time = time.perf_counter()

                for record_id in range(1, record_count + 1):
                    product_id = random.randint(1, 4)
                    quantity = random.randint(1, 5000)
                    date_value = f'{random.randint(1, 28):02d}-{random.randint(1, 12):02d}-2023'
                    department_id, municipality_id = random.choice(municipalities)
                    rows.append((record_id, department_id, municipality_id, product_id, date_value, quantity, 'F'))
                    if len(rows) == 10000 or record_id == record_count:
                        execute_values(cursor, '''INSERT INTO public.tamanio
                            (id_registro, id_departamento, id_municipio,
                             id_producto, fecha, cantidad, estado)
                            VALUES %s''', rows, page_size=len(rows))
                        rows.clear()

                connection.commit()
                elapsed_time = (time.perf_counter() - start_time) * 1000
                cursor.execute('SELECT count(*) FROM public.tamanio')
                if cursor.fetchone()[0] != record_count:
                    raise RuntimeError(f'Count does not match the expected {record_count} records.')
                cursor.execute('''SELECT pg_total_relation_size('public.tamanio'),
                                      pg_database_size(current_database())''')
                table_size, database_size = cursor.fetchone()
                print(f'{record_count:>12} {elapsed_time:>14.3f} {table_size / 1024:>14.2f} '
                      f'{database_size / 1048576:>12.2f} {100 * table_size / database_size:>14.2f}', flush=True)
    finally:
        connection.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f'ERROR - Size calculation interrupted: {error}')
        raise SystemExit(1)
