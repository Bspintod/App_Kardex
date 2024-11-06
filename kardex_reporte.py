import pandas as pd
import streamlit as st
from datetime import datetime

def main():
    st.title("Reporte de Antigüedad de Movimientos e Inventario")
    
    # Cargar archivos CSV
    antiguedad_file = st.file_uploader("Sube el archivo de movimientos (kardex)", type=["csv"])
    inventory_file = st.file_uploader("Sube el archivo de inventario", type=["csv"])
    
    if antiguedad_file and inventory_file:
        # Procesar archivo de movimientos (kardex)
        kardex_df = pd.read_csv(antiguedad_file, encoding='latin1', delimiter=';', on_bad_lines='skip')
        kardex_df['FECHA'] = pd.to_datetime(kardex_df['FECHA'], errors='coerce', dayfirst=True)
        kardex_df = kardex_df.dropna(subset=['FECHA'])
        kardex_df.columns = kardex_df.columns.str.strip("'")
        kardex_df['MOVIMIENTO'] = kardex_df['MOVIMIENTO'].str.lower()
        
        # Filtrar datos para cada tipo de movimiento
        purchase_df = kardex_df[kardex_df['MOVIMIENTO'].str.contains('compra')]
        transfer_df = kardex_df[kardex_df['MOVIMIENTO'].str.contains('traspaso')]
        sale_df = kardex_df[kardex_df['MOVIMIENTO'].str.contains('venta')]

        # Calcular la última fecha de cada movimiento por combinación de CODIGO y BODEGA
        last_purchase = purchase_df.groupby(['CODIGO', 'BODEGA'])['FECHA'].max().reset_index().rename(columns={'FECHA': 'ULTIMA_COMPRA'})
        last_transfer = transfer_df.groupby(['CODIGO', 'BODEGA'])['FECHA'].max().reset_index().rename(columns={'FECHA': 'ULTIMO_TRASPASO'})
        last_sale = sale_df.groupby(['CODIGO', 'BODEGA'])['FECHA'].max().reset_index().rename(columns={'FECHA': 'ULTIMA_VENTA'})
        
        # Merge de las fechas de último movimiento
        antiguedad_df = pd.merge(last_purchase, last_transfer, on=['CODIGO', 'BODEGA'], how='outer')
        antiguedad_df = pd.merge(antiguedad_df, last_sale, on=['CODIGO', 'BODEGA'], how='outer')

        # Calcular antigüedad de cada tipo de movimiento
        antiguedad_df['ANTIGUEDAD_ULTIMA_COMPRA'] = (datetime.today() - antiguedad_df['ULTIMA_COMPRA']).dt.days
        antiguedad_df['ANTIGUEDAD_ULTIMO_TRASPASO'] = (datetime.today() - antiguedad_df['ULTIMO_TRASPASO']).dt.days
        antiguedad_df['ANTIGUEDAD_ULTIMA_VENTA'] = (datetime.today() - antiguedad_df['ULTIMA_VENTA']).dt.days

        # Procesar archivo de inventario
        inventory_df = pd.read_csv(inventory_file, encoding='latin1', delimiter=';', on_bad_lines='skip')
        
        # Buscar y renombrar la columna que contiene "PRODUCTO"
        producto_columna = [col for col in inventory_df.columns if "PRODUCTO" in col.upper()]
        if producto_columna:
            inventory_df = inventory_df.rename(columns={producto_columna[0]: 'PRODUCTO'})
        
        inventory_df['CODIGO'] = inventory_df['CODIGO'].str.replace("'", "")

        # Limpiar la columna 'CODIGO' en antiguedad_df para que coincida
        antiguedad_df['CODIGO'] = antiguedad_df['CODIGO'].str.replace("'", "")

        # Selección de columnas relevantes y ajuste del formato del inventario
        inventory_selected = inventory_df[['CODIGO', 'PRODUCTO', 'CATEGORIA', 'INV GAITAN', 'INV OPORTO', 'INV SAMARIA', 'INV MIROLINDO']]
        inventory_long = inventory_selected.melt(id_vars=['CODIGO', 'PRODUCTO', 'CATEGORIA'], 
                                                 value_vars=['INV GAITAN', 'INV OPORTO', 'INV SAMARIA', 'INV MIROLINDO'], 
                                                 var_name='BODEGA', value_name='INVENTARIO')
        inventory_long['BODEGA'] = inventory_long['BODEGA'].str.replace("INV ", "")
        
        # Merge del inventario con los datos de antigüedad
        final_report_df = pd.merge(antiguedad_df, inventory_long, on=['CODIGO', 'PRODUCTO', 'CATEGORIA', 'BODEGA'], how='left')

        # Ordenar las columnas según la solicitud
        final_report_df = final_report_df[['CODIGO', 'PRODUCTO', 'CATEGORIA', 'BODEGA', 'ULTIMA_COMPRA', 
                                           'ULTIMO_TRASPASO', 'ULTIMA_VENTA', 'ANTIGUEDAD_ULTIMA_COMPRA', 
                                           'ANTIGUEDAD_ULTIMO_TRASPASO', 'ANTIGUEDAD_ULTIMA_VENTA', 'INVENTARIO']]
        
        # Mostrar el reporte final
        st.write("Reporte de Antigüedad de Movimientos e Inventario")
        st.dataframe(final_report_df)
        
        # Permitir la descarga del reporte en formato CSV
        csv = final_report_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar reporte como CSV",
            data=csv,
            file_name='reporte_antiguedad_inventario.csv',
            mime='text/csv',
        )

if __name__ == "__main__":
    main()
