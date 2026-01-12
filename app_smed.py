import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="SMED Pro", layout="wide")

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("📚 Teoría SMED")
    st.info("Sube tu Excel para analizar los datos automáticamente.")
    st.markdown("""
    **Formato requerido del Excel:**
    Asegúrate de que tu hoja tenga columnas parecidas a:
    * Descripción
    * Duración (min)
    * Tipo (Interna/Externa)
    """)

# --- TÍTULO ---
st.title("⚡ Analizador SMED - Versión Pro")

# --- CARGA DE DATOS ---
st.subheader("1. Cargar Datos")
uploaded_file = st.file_uploader("Sube tu archivo Excel o CSV aquí", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # Detectar tipo de archivo
    try:
        if uploaded_file.name.endswith('.csv'):
            df_original = pd.read_csv(uploaded_file)
        else:
            df_original = pd.read_excel(uploaded_file)
        
        st.success("¡Archivo cargado correctamente!")
    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        st.stop()
else:
    st.warning("👆 Sube un archivo para empezar (o usa los datos de ejemplo abajo).")
    # Datos de ejemplo por defecto
    data = {
        "Descripción": ["Buscar llave", "Parar máquina", "Cambio molde", "Ajustes"],
        "Duración Actual (min)": [5.0, 2.0, 15.0, 10.0],
        "Tipo Actual": ["Interna", "Interna", "Interna", "Interna"],
        "Tipo Futuro": ["Externa", "Interna", "Interna", "Eliminada"],
        "Duración Futura (min)": [5.0, 2.0, 10.0, 0.0]
    }
    df_original = pd.DataFrame(data)

# --- MAPEO DE COLUMNAS (INTELIGENCIA) ---
# Intentamos adivinar qué columna es cuál si tienen nombres distintos en tu Excel
cols = df_original.columns.tolist()
c1, c2, c3 = st.columns(3)
with c1:
    col_desc = st.selectbox("Columna Descripción", cols, index=0)
with c2:
    # Intenta encontrar una columna que tenga "tiempo" o "duración" en el nombre
    idx_time = next((i for i, c in enumerate(cols) if "tiempo" in c.lower() or "duración" in c.lower() or "min" in c.lower()), 1)
    col_time = st.selectbox("Columna Tiempo (Min)", cols, index=idx_time if idx_time < len(cols) else 0)
with c3:
    idx_type = next((i for i, c in enumerate(cols) if "tipo" in c.lower()), 2)
    col_type = st.selectbox("Columna Tipo (Interna/Ext)", cols, index=idx_type if idx_type < len(cols) else 0)

# Preparamos el DataFrame de trabajo
df_work = df_original.copy()
# Renombramos para estandarizar
df_work = df_work.rename(columns={col_desc: "Descripción", col_time: "Duración Actual (min)", col_type: "Tipo Actual"})

# Asegurar que existan columnas futuras si no vienen en el Excel
if "Tipo Futuro" not in df_work.columns:
    df_work["Tipo Futuro"] = df_work["Tipo Actual"]
if "Duración Futura (min)" not in df_work.columns:
    df_work["Duración Futura (min)"] = df_work["Duración Actual (min)"]

# --- EDITOR DE ANÁLISIS ---
st.divider()
st.subheader("2. Clasificación y Mejora")

# Configuración del editor
column_config = {
    "Tipo Actual": st.column_config.SelectboxColumn(options=["Interna", "Externa"], required=True),
    "Tipo Futuro": st.column_config.SelectboxColumn(options=["Interna", "Externa", "Eliminada"], required=True),
    "Duración Actual (min)": st.column_config.NumberColumn(format="%.2f"),
    "Duración Futura (min)": st.column_config.NumberColumn(format="%.2f"),
}

df_edited = st.data_editor(
    df_work[["Descripción", "Duración Actual (min)", "Tipo Actual", "Tipo Futuro", "Duración Futura (min)"]],
    num_rows="dynamic",
    column_config=column_config,
    use_container_width=True,
    height=400
)

# --- CÁLCULOS Y GRÁFICOS ---
paro_actual = df_edited[df_edited["Tipo Actual"].str.lower().str.contains("interna")]["Duración Actual (min)"].sum()
paro_futuro = df_edited[df_edited["Tipo Futuro"].str.lower().str.contains("interna")]["Duración Futura (min)"].sum()
ahorro = paro_actual - paro_futuro
mejora_pct = (ahorro / paro_actual * 100) if paro_actual > 0 else 0

st.divider()
st.subheader("3. Resultados")
m1, m2, m3 = st.columns(3)
m1.metric("Tiempo Paro ACTUAL", f"{paro_actual:.2f} min")
m2.metric("Tiempo Paro FUTURO", f"{paro_futuro:.2f} min", delta=f"-{ahorro:.2f}")
m3.metric("% Reducción", f"{mejora_pct:.1f}%")

fig = go.Figure()
fig.add_trace(go.Bar(name='Paro Actual', x=['Tiempos'], y=[paro_actual], marker_color='#ef553b'))
fig.add_trace(go.Bar(name='Paro Futuro', x=['Tiempos'], y=[paro_futuro], marker_color='#00cc96'))
st.plotly_chart(fig, use_container_width=True)

