"""Muestra la exploración y limpieza desde el respaldo anterior al ETL."""
import argparse
from pathlib import Path
import pandas as pd
from limpieza import limpiar, resumen_problemas

BASE = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paso-a-paso', action='store_true', help='Pausa cada etapa para revisar y capturar la pantalla.')
    parser.add_argument('--fecha-ambigua', choices=['dia-mes', 'mes-dia'], help='Decisión explícita para fechas ambiguas con el año al final.')
    args = parser.parse_args()
    entrada = BASE / 'resultados'
    salida = entrada / 'punto6'
    salida.mkdir(exist_ok=True)
    def leer(nombre):
        return pd.read_csv(entrada / (nombre + '.csv'), encoding='utf-8-sig', keep_default_na=False)
    datos = leer('operaciones_antes')
    municipios, departamentos, productos = (leer(n) for n in ['municipios', 'departamentos', 'productos'])
    def mostrar(titulo, tabla):
        print('\n' + titulo)
        reglas = {
            '2': 'Regla: validar el formato y el calendario; proponer fechas y separar las ambiguas.',
            '3': 'Regla: cantidad < 0; reemplazar por abs(cantidad).',
            '4': 'Regla: filtrar cantidad > 0 y agrupar por id_municipio; calcular sum, count y mean.',
            '5': 'Regla: imputar cada cero con el promedio de su municipio, redondeado a unidad.',
            '6': 'Regla: consultar el municipio para recuperar el departamento; aplicar la regla de NARANJITA solo en Támesis.',
        }
        if titulo[0] in reglas:
            print(reglas[titulo[0]])
        visible = tabla.drop(columns=['criterio'], errors='ignore')
        print(visible.to_string(index=False) if len(tabla) else 'Sin registros en esta etapa.')
        if 'criterio' in tabla:
            for _, fila in tabla.iterrows():
                if 'ambigua' in fila['criterio'] or fila['estado'] == 'pendiente':
                    print(f'Registro {fila["id_registro"]}: {fila["criterio"]}')
        if args.paso_a_paso:
            input('\nTome la captura si la necesita. Pulse Enter para continuar...')
    print('Fuente: resultados/operaciones_antes.csv (respaldo anterior a la limpieza).')
    print('Se trabaja sobre una copia en memoria. Este programa no modifica PostgreSQL.')
    resumen, afectados = resumen_problemas(datos)
    print(f'Filas leídas: {len(datos)}. Registros con problemas: {afectados} ({afectados/len(datos)*100:.2f} %).')
    mostrar('1. Exploración de todas las operaciones', resumen)
    limpios, detalle = limpiar(datos, municipios, departamentos, productos, args.fecha_ambigua, mostrar)
    resumen.to_csv(salida / 'diagnostico.csv', index=False, encoding='utf-8-sig')
    detalle.to_csv(salida / 'detalle_limpieza.csv', index=False, encoding='utf-8-sig')
    pendientes = detalle.loc[detalle['estado'].eq('pendiente')]
    pendientes.to_csv(salida / 'pendientes.csv', index=False, encoding='utf-8-sig')
    nombre = 'operaciones_propuestas.csv' if len(pendientes) else 'operaciones_limpias.csv'
    limpios.to_csv(salida / nombre, index=False, encoding='utf-8-sig')
    anterior = 'operaciones_limpias.csv' if len(pendientes) else 'operaciones_propuestas.csv'
    (salida / anterior).unlink(missing_ok=True)
    controles = pd.DataFrame([
        ['Filas originales', len(datos)], ['Filas conservadas', len(limpios)],
        ['Registros modificados', int(limpios['validacion'].eq('modificado').sum())],
        ['Problemas pendientes', len(pendientes)]], columns=['control', 'total'])
    mostrar('7. Verificación de la conservación de registros', controles)
    print('Archivos guardados en:', salida)
    if len(pendientes):
        print('Revise pendientes.csv. Las fechas ambiguas no se corrigieron automáticamente.')
        print('Si elige día-mes-año, repita con --fecha-ambigua dia-mes. Es una decisión, no un dato confirmado.')


if __name__ == '__main__':
    main()
