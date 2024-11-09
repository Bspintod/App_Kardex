import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import locale
from datetime import datetime

# Configurar regionalización en español
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

COLUMNAS_REQUERIDAS_KARDEX = [
    'FECHA', 'REFERENCIA', 'CODIGO', 'PRODUCTO', 'CANTIAD', 
    'PRECIO', 'IMPUESTO', 'SUBTOTAL', 'CATEGORIA', 'BODEGA', 'MOVIMIENTO'
]

COLUMNAS_ROTACION = [
    'CODIGO', 'COSTO', 'PRECIO', 'INV GAITAN', 'INV OPORTO', 'INV SAMARIA', 
    'INV VENCIDOS/ROTURA', 'INV MIROLINDO'
]

ESTRATEGIA_ROTACION = {
    (0, 20): "Nuevo en Inventario",
    (21, 60): "Venta Lenta Inicial",
    (61, 90): "Alerta Moderada",
    (91, 180): "Riesgo de Estancamiento",
    (181, 330): "Inventario Crítico",
    (331, 365): "Inventario Obsoleto",
    (366, float('inf')): "Pérdida Potencial"
}

def validar_columnas(dataframe, columnas_requeridas):
    """Verifica que las columnas requeridas estén en el DataFrame."""
    columnas_faltantes = [col for col in columnas_requeridas if col not in dataframe.columns]
    if columnas_faltantes:
        raise ValueError(f"Faltan las siguientes columnas: {', '.join(columnas_faltantes)}")

def convertir_fecha(column):
    """Convierte las columnas de fecha en formato datetime."""
    return pd.to_datetime(column, format='%d/%m/%Y', errors='coerce')

def limpiar_codigos(df, columna='CODIGO'):
    """Limpia el contenido de la columna CODIGO eliminando espacios y comillas simples."""
    df[columna] = df[columna].astype(str).str.replace("'", "").str.strip().str.upper()
    return df

def calcular_antiguedad(kardex_df):
    """Calcula la antigüedad de la última compra, traspaso y venta."""
    kardex_df['FECHA'] = convertir_fecha(kardex_df['FECHA'])

    # Filtrar movimientos
    compras = kardex_df[kardex_df['MOVIMIENTO'].str.contains('entrada.*Compra', case=False, na=False)]
    traspasos = kardex_df[kardex_df['MOVIMIENTO'].str.contains('entrada.*Traspaso', case=False, na=False)]
    ventas = kardex_df[kardex_df['CANTIAD'] < 0]

    # Agrupar y obtener la última fecha por tipo de movimiento
    ultima_compra = compras.groupby(['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA'])['FECHA'].max()
    ultimo_traspaso = traspasos.groupby(['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA'])['FECHA'].max()
    ultima_venta = ventas.groupby(['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA'])['FECHA'].max()

    # Alinear índices
    productos = ultima_compra.index.union(ultimo_traspaso.index).union(ultima_venta.index)
    ultima_compra = ultima_compra.reindex(productos)
    ultimo_traspaso = ultimo_traspaso.reindex(productos)
    ultima_venta = ultima_venta.reindex(productos)

    ahora = pd.Timestamp(datetime.now())

    # Calcular antigüedad en días
    antiguedad_compra = (ahora - ultima_compra).dt.days.fillna(np.inf)
    antiguedad_traspaso = (ahora - ultimo_traspaso).dt.days.fillna(np.inf)
    antiguedad_venta = (ahora - ultima_venta).dt.days.fillna(np.inf)

    antiguedad_df = pd.DataFrame({
        'CODIGO': [x[0] for x in productos],
        'PRODUCTO': [x[1] for x in productos],
        'BODEGA': [x[2] for x in productos],
        'CATEGORIA': [x[3] for x in productos],
        'Fecha Última Compra': ultima_compra.values,
        'Antigüedad Última Compra (días)': antiguedad_compra.values,
        'Fecha (Entrada) Traspaso': ultimo_traspaso.values,
        'Antigüedad Último Traspaso (días)': antiguedad_traspaso.values,
        'Fecha Última Venta': ultima_venta.values,
        'Antigüedad Última Venta (días)': antiguedad_venta.values
    })

    return antiguedad_df

def integrar_inventario_por_bodega(antiguedad_df, rotacion_df):
    """Integra el inventario por bodega usando CODIGO."""
    # Limpiar y asegurar coincidencia de códigos
    antiguedad_df = limpiar_codigos(antiguedad_df)
    rotacion_df = limpiar_codigos(rotacion_df)

    # Unir los DataFrames usando la columna CODIGO
    inventario_completo = antiguedad_df.merge(
        rotacion_df[['CODIGO', 'COSTO', 'PRECIO', 'INV GAITAN', 'INV OPORTO', 'INV SAMARIA', 'INV MIROLINDO']], 
        on='CODIGO', how='left'
    )

    # Renombrar las columnas de inventario por bodega
    inventario_completo = inventario_completo.rename(columns={
        'INV GAITAN': 'Inventario Gaitan',
        'INV OPORTO': 'Inventario Oporto',
        'INV SAMARIA': 'Inventario Samaria',
        'INV MIROLINDO': 'Inventario Mirolindo'
    })

    # Calcular nuevas columnas
    inventario_completo['TotalInv'] = inventario_completo[['Inventario Gaitan', 'Inventario Oporto', 'Inventario Samaria', 'Inventario Mirolindo']].sum(axis=1)
    inventario_completo['$ Gaitan'] = inventario_completo['Inventario Gaitan'] * inventario_completo['COSTO']
    inventario_completo['$ Oporto'] = inventario_completo['Inventario Oporto'] * inventario_completo['COSTO']
    inventario_completo['$ Samaria'] = inventario_completo['Inventario Samaria'] * inventario_completo['COSTO']
    inventario_completo['$ Mirolindo'] = inventario_completo['Inventario Mirolindo'] * inventario_completo['COSTO']
    inventario_completo['ValorInventario'] = inventario_completo[['$ Gaitan', '$ Oporto', '$ Samaria', '$ Mirolindo']].sum(axis=1)

    # Calcular Rango de Días y Estrategia
    def determinar_rango_estrategia(dias):
        for rango, estrategia in ESTRATEGIA_ROTACION.items():
            if rango[0] <= dias <= rango[1]:
                return estrategia
        return 'Sin Estrategia'

    inventario_completo['Rango de Días'] = inventario_completo['Antigüedad Última Venta (días)'].apply(determinar_rango_estrategia)
    inventario_completo['Estrategia'] = inventario_completo['Rango de Días']

    return inventario_completo

def generar_excel(dataframe):
    """Genera un archivo Excel con los datos."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer, sheet_name='Datos Procesados', index=False)
    output.seek(0)
    return output

def main():
    st.title("Análisis de Inventario con Antigüedad e Inventario por Bodega")

    # Subida de archivos
    archivo_kardex = st.file_uploader("Sube el archivo Kardex.csv", type=["csv"])
    archivo_rotacion = st.file_uploader("Sube el archivo Rotacion.csv", type=["csv"])

    if archivo_kardex and archivo_rotacion:
        try:
            # Cargar los archivos CSV
            kardex_df = pd.read_csv(archivo_kardex, encoding='latin1', sep=';')
            rotacion_df = pd.read_csv(archivo_rotacion, encoding='latin1', sep=';')

            # Validar columnas
            validar_columnas(kardex_df, COLUMNAS_REQUERIDAS_KARDEX)
            validar_columnas(rotacion_df, COLUMNAS_ROTACION)

            # Calcular antigüedad
            antiguedad_df = calcular_antiguedad(kardex_df)

            # Integrar inventario por bodega
            inventario_completo = integrar_inventario_por_bodega(antiguedad_df, rotacion_df)

            st.write("Inventario Completo por Bodega con Antigüedad:")
            st.dataframe(inventario_completo)

            # Generar archivo Excel
            datos_excel = generar_excel(inventario_completo)

            st.download_button(
                label="Descargar Datos en Excel",
                data=datos_excel,
                file_name="inventario_por_bodega.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except ValueError as ve:
            st.error(f"Error: {ve}")
        except Exception as e:
            st.error(f"Hubo un error al procesar los archivos: {e}")

if __name__ == "__main__":
    main()
