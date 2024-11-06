import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import locale

# Configurar regionalización en español
locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')

def procesar_ventas(kardex_df):
    """Procesa las ventas por cada bodega y fecha."""
    ventas = kardex_df[kardex_df['MOVIMIENTO'].str.contains('salida.*Venta', case=False, na=False)]
    ventas['FECHA'] = pd.to_datetime(ventas['FECHA'], format='%d/%m/%Y', errors='coerce')

    fecha_limite = ventas['FECHA'].max() - pd.DateOffset(months=4)
    ventas_recientes = ventas[(ventas['FECHA'] < ventas['FECHA'].max()) & 
                              (ventas['FECHA'] >= fecha_limite)]
    ventas_recientes['Mes'] = ventas_recientes['FECHA'].dt.to_period('M')

    ventas_agrupadas = ventas_recientes.groupby(
        ['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA', 'Mes']
    )['CANTIAD'].sum().abs().reset_index()

    return ventas_agrupadas

def clasificacion_abc_por_sede(dataframe):
    ventas_por_sede = dataframe.groupby(['BODEGA', 'CATEGORIA', 'CODIGO', 'PRODUCTO']).agg(
        Total_Ventas=('CANTIAD', 'sum')
    ).reset_index()

    ventas_por_sede['Porcentaje_Ventas'] = ventas_por_sede.groupby(['BODEGA', 'CATEGORIA'])['Total_Ventas'].transform(lambda x: x / x.sum())
    ventas_por_sede = ventas_por_sede.sort_values(['BODEGA', 'CATEGORIA', 'Porcentaje_Ventas'], ascending=[True, True, False])
    ventas_por_sede['Porcentaje_Acumulado'] = ventas_por_sede.groupby(['BODEGA', 'CATEGORIA'])['Porcentaje_Ventas'].cumsum()

    ventas_por_sede = ventas_por_sede.sort_values(['BODEGA', 'CATEGORIA', 'Porcentaje_Acumulado'], ascending=[True, True, True])

    ventas_por_sede['Clasificacion_ABC'] = np.where(
        ventas_por_sede['Porcentaje_Acumulado'] <= 0.8, 'A',
        np.where(ventas_por_sede['Porcentaje_Acumulado'] <= 0.95, 'B', 'C')
    )

    return ventas_por_sede

def calcular_inventario(ventas_agrupadas):
    inventario = ventas_agrupadas.groupby(['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA']).agg(
        Promedio_Mensual=('CANTIAD', 'mean'),
        Desviacion_Estandar=('CANTIAD', 'std'),
        Venta_Maxima=('CANTIAD', 'max')
    ).reset_index()

    inventario['Inventario_Minimo'] = (inventario['Promedio_Mensual'] + inventario['Desviacion_Estandar'].fillna(0)).round()
    inventario['Inventario_Maximo'] = (inventario['Promedio_Mensual'] * 2 * 1.1).round()
    inventario['Inventario_Maximo'] = inventario[['Inventario_Minimo', 'Inventario_Maximo']].max(axis=1)

    return inventario

def generar_excel(dataframe):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dataframe.to_excel(writer, sheet_name='Inventario_ABC', index=False, startrow=0, startcol=0)
    return output.getvalue()

def main():
    st.title("Análisis de Inventario con Clasificación ABC por Sede")
    st.write("Sube tu archivo `Kardex.csv` para calcular inventario mínimo, máximo y clasificación ABC por bodega.")

    archivo = st.file_uploader("Sube el archivo Kardex.csv", type=["csv"])

    if archivo is not None:
        try:
            kardex_df = pd.read_csv(archivo, encoding='latin1', sep=';')
            st.success("Archivo cargado correctamente.")

            ventas_agrupadas = procesar_ventas(kardex_df)
            inventario = calcular_inventario(ventas_agrupadas)
            clasificacion_abc = clasificacion_abc_por_sede(ventas_agrupadas)
            inventario_abc = pd.merge(inventario, clasificacion_abc, on=['CODIGO', 'PRODUCTO', 'BODEGA', 'CATEGORIA'])

            datos_excel = generar_excel(inventario_abc)

            st.download_button(
                label="Descargar Inventario ABC",
                data=datos_excel,
                file_name="inventario_abc.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Hubo un error al procesar el archivo: {e}")

if __name__ == "__main__":
    main()
