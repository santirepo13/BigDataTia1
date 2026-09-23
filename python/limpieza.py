"""Exploración y limpieza de operaciones con Pandas, sin listas de registros."""
import re
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd

TIPOS = {
    'A': ('fecha', 'Fecha fuera del formato AAAA-MM-DD o inexistente'),
    'B': ('cantidad', 'Cantidad en cero o ausente'),
    'C': ('cantidad', 'Cantidad negativa'),
    'D': ('id_departamento', 'Código de departamento ausente'),
    'E': ('id_producto', 'Código de producto ausente'),
}


def fecha_valida(valor):
    texto = str(valor)
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', texto):
        return False
    try:
        date.fromisoformat(texto)
        return True
    except ValueError:
        return False


def detectar(datos):
    """Revisa todas las filas; el número de problemas se calcula, no se fija."""
    cantidad = pd.to_numeric(datos['cantidad'], errors='coerce')
    departamento = pd.to_numeric(datos['id_departamento'], errors='coerce')
    producto = pd.to_numeric(datos['id_producto'], errors='coerce')
    return {
        'A': ~datos['fecha'].map(fecha_valida),
        'B': cantidad.isna() | cantidad.eq(0),
        'C': cantidad.lt(0),
        'D': departamento.isna() | departamento.eq(0),
        'E': producto.isna() | producto.eq(0),
    }


def resumen_problemas(datos):
    mascaras = detectar(datos)
    resumen = pd.DataFrame([
        {'tipo': tipo, 'problema': TIPOS[tipo][1], 'registros': int(mascara.sum())}
        for tipo, mascara in mascaras.items()
    ])
    afectados = pd.concat(mascaras.values(), axis=1).any(axis=1)
    return resumen, int(afectados.sum())


def corregir_fecha(valor, anios, orden_ambiguo=None):
    """Propone fechas por formato y calendario; una ambigüedad queda pendiente."""
    partes = str(valor).strip().split('-')
    if len(partes) != 3 or not all(p.isdigit() for p in partes):
        return None, 'Formato no reconocido; revisar la fuente.'
    posiciones = []
    extremos = [p for p in (0, 2) if len(partes[p]) == 4] or [0, 2]
    for posicion in extremos:
        texto = partes[posicion]
        if len(texto) == 4:
            posiciones.append((posicion, int(texto)))
        elif len(texto) in (2, 3):
            coincidencias = [a for a in anios if a % (10 ** len(texto)) == int(texto)]
            if len(coincidencias) == 1:
                posiciones.append((posicion, coincidencias[0]))
    if len(posiciones) != 1:
        return None, 'No se puede determinar el año con los datos válidos del conjunto.'
    posicion, anio = posiciones[0]
    nota_anio = '' if len(partes[posicion]) == 4 else f' Año {anio} según las fechas completas del conjunto.'
    candidatos = {}
    def agregar(orden, mes, dia):
        try:
            candidatos[orden] = date(anio, mes, dia).isoformat()
        except ValueError:
            pass
    if posicion == 0:
        # Año al inicio: se usa año-mes-día. Si el mes es >12, se prueba año-día-mes.
        segundo, tercero = int(partes[1]), int(partes[2])
        if segundo <= 12:
            agregar('año-mes-día', segundo, tercero)
        else:
            agregar('año-día-mes', tercero, segundo)
    else:
        primero, segundo = int(partes[0]), int(partes[1])
        agregar('dia-mes', segundo, primero)
        agregar('mes-dia', primero, segundo)
    unicos = set(candidatos.values())
    if len(unicos) == 1:
        return next(iter(unicos)), 'Normalización por formato y calendario.' + nota_anio
    if len(unicos) > 1:
        opciones = '; '.join(f'{k}: {v}' for k, v in candidatos.items())
        if orden_ambiguo in candidatos:
            return candidatos[orden_ambiguo], f'Fecha ambigua ({opciones}); decisión explícita: {orden_ambiguo}.' + nota_anio
        return None, f'Fecha ambigua ({opciones}); requiere decisión explícita.'
    return None, 'Fecha imposible en el calendario; revisar la fuente.'


def normalizar_nombre(valor):
    return ''.join(c for c in unicodedata.normalize('NFD', str(valor))
                   if unicodedata.category(c) != 'Mn').upper().strip()


def limpiar(operaciones, municipios, departamentos, productos, orden_ambiguo=None, mostrar=None):
    """Devuelve una copia corregida y una auditoría; no cambia PostgreSQL."""
    datos = operaciones.copy(deep=True).reset_index(drop=True)
    originales = datos.copy(deep=True)
    for campo in ['id_registro', 'id_municipio', 'cantidad', 'id_departamento', 'id_producto']:
        datos[campo] = pd.to_numeric(datos[campo], errors='coerce')
    if datos['id_registro'].isna().any() or datos['id_registro'].duplicated().any():
        raise ValueError('Hay identificadores de operaciones vacíos o duplicados.')
    for catalogo, clave in ((municipios, 'id_municipio'), (departamentos, 'id_departamento'), (productos, 'id_producto')):
        if catalogo[clave].duplicated().any():
            raise ValueError('El catálogo contiene códigos duplicados: ' + clave)
    datos['validacion'] = 'valido'
    datos['causa_modificacion'] = ''
    problemas = detectar(datos)
    auditoria = []
    anios = {int(str(v)[:4]) for v in datos.loc[~problemas['A'], 'fecha']}

    def registrar(indice, tipo, nuevo, criterio):
        campo = TIPOS[tipo][0]
        anterior = originales.at[indice, campo]
        estado = 'pendiente' if nuevo is None else 'corregido'
        auditoria.append({'tipo': tipo, 'id_registro': int(datos.at[indice, 'id_registro']),
                         'campo': campo, 'problema': TIPOS[tipo][1],
                         'valor_original': anterior, 'valor_corregido': nuevo,
                         'criterio': criterio, 'estado': estado})
        if nuevo is None:
            previo = datos.at[indice, 'causa_modificacion']
            datos.at[indice, 'causa_modificacion'] = previo + (' | ' if previo else '') + f'{tipo}: pendiente. {criterio}'
            return
        datos.at[indice, campo] = nuevo
        datos.at[indice, 'validacion'] = 'modificado'
        motivo = f'{tipo}: {campo} {anterior} -> {nuevo}. {criterio}'
        previo = datos.at[indice, 'causa_modificacion']
        datos.at[indice, 'causa_modificacion'] = previo + (' | ' if previo else '') + motivo

    def etapa(titulo, tipos):
        if mostrar:
            filas = [r for r in auditoria if r['tipo'] in tipos]
            columnas = ['id_registro', 'campo', 'valor_original', 'valor_corregido', 'criterio', 'estado']
            mostrar(titulo, pd.DataFrame(filas, columns=columnas))

    for i in datos.index[problemas['A']]:
        nuevo, criterio = corregir_fecha(datos.at[i, 'fecha'], anios, orden_ambiguo)
        registrar(i, 'A', nuevo, criterio)
    etapa('2. Fechas: detección, propuesta y decisiones pendientes', ['A'])

    for i in datos.index[problemas['C']]:
        registrar(i, 'C', abs(int(datos.at[i, 'cantidad'])), 'Retirar el signo negativo con abs().')
    etapa('3. Cantidades negativas', ['C'])

    # Se calcula una sola vez: excluye todos los ceros y ya incluye los negativos corregidos.
    positivos = datos.loc[datos['cantidad'].gt(0)]
    promedios = positivos.groupby('id_municipio')['cantidad'].agg(['sum', 'count', 'mean'])
    if mostrar:
        municipios_cero = datos.loc[problemas['B'], 'id_municipio'].unique()
        mostrar('4. Promedios antes de reemplazar los ceros',
                promedios.reindex(municipios_cero).reset_index())
    for i in datos.index[problemas['B']]:
        municipio = datos.at[i, 'id_municipio']
        if municipio not in promedios.index:
            registrar(i, 'B', None, 'El municipio no tiene cantidades positivas para calcular un promedio.')
            continue
        grupo = promedios.loc[municipio]
        media = Decimal(int(grupo['sum'])) / Decimal(int(grupo['count']))
        nueva = int(media.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        registrar(i, 'B', nueva, f'Promedio municipal {media:.6f} de {int(grupo["count"])} cantidades positivas; redondeo a unidad.')
    etapa('5. Cantidades en cero: antes y después', ['B'])

    mapa_departamentos = municipios.set_index('id_municipio')['id_departamento']
    for i in datos.index[problemas['D']]:
        municipio = datos.at[i, 'id_municipio']
        nuevo = int(mapa_departamentos[municipio]) if municipio in mapa_departamentos.index else None
        registrar(i, 'D', nuevo, 'Departamento obtenido del catálogo de municipios.' if nuevo else 'Municipio desconocido; revisar la fuente.')

    antioquia = departamentos.loc[departamentos['nombre'].map(normalizar_nombre).eq('ANTIOQUIA'), 'id_departamento']
    tamesis = municipios.loc[municipios['nombre'].map(normalizar_nombre).eq('TAMESIS') & municipios['id_departamento'].isin(antioquia), 'id_municipio']
    naranjita = productos.loc[productos['nombre'].map(normalizar_nombre).eq('NARANJITA'), 'id_producto']
    for i in datos.index[problemas['E']]:
        if datos.at[i, 'id_municipio'] in set(tamesis) and len(naranjita) == 1:
            registrar(i, 'E', int(naranjita.iloc[0]), 'Regla del caso: en Támesis, Antioquia, solo se vende NARANJITA.')
        else:
            registrar(i, 'E', None, 'La regla de Támesis no permite deducir este producto.')
    etapa('6. Departamentos y productos faltantes', ['D', 'E'])

    columnas = ['tipo', 'id_registro', 'campo', 'problema', 'valor_original', 'valor_corregido', 'criterio', 'estado']
    detalle = pd.DataFrame(auditoria, columns=columnas).sort_values(['id_registro', 'tipo'])
    pendientes = detalle.loc[detalle['estado'].eq('pendiente'), 'id_registro']
    datos.loc[datos['id_registro'].isin(pendientes), 'validacion'] = 'pendiente'
    return datos, detalle
