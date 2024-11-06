import streamlit as st
import subprocess

def main():
    st.title("Menú Principal")
    

    # Crear opciones en la barra lateral
    opcion = st.sidebar.selectbox(
        "Selecciona una opción:",
        ["Seleccione...", "Kardex abc", "Productos senior"]
    )

    if opcion == "Kardex abc":
        st.write("Kardex abc...")
        subprocess.run(["streamlit", "run", "kardex_abc.py"])
    elif opcion == "Productos senior":
        st.write("Productos senior...")
        subprocess.run(["streamlit", "run", "kardex_reporte.py"])

if __name__ == "__main__":
    main()