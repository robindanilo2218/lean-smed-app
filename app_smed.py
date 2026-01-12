import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="SMED Pro - Análisis en Segundos", layout="wide")

# --- FUNCIONES AUXILIARES ---
def load_data_smart(file):
    """
    Busca automáticamente la fila de encabezados ignorando metadatos superiores.
    """
    try:
        # Leemos las primeras 20 filas sin encabezado para escanear
        preview = pd.read_excel(file, header=None, nrows=20)
        
        header_row_idx = 0
        found = False
        
        # Buscamos una fila que contenga palabras clave como "Actividad" o "Duración"
        for i, row in preview.iterrows():
            row_text = row.astype(str).str.lower().tolist()
            # Si la fila tiene al menos 2 palabras clave, asumimos que es el encabezado
            matches = sum(1 for word in ["actividad", "duración", "tipo", "inicio", "fin"] 
                          if any(word in str(x) for x in row_text))
            if matches >= 2:
                header_row_idx = i
                found = True
                break
        
        # Cargamos el archivo real usando esa fila como encabezado
        df = pd.read_excel(file, header=header_row_idx)
        return df, found
    except Exception as e:
        return None, str(e)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Configuración SMED")
    st.info("Modo de Precisión: Segundos")
    st.markdown("""
    **Columnas esperadas:**
    El sistema buscará automáticamente:
    * Categoría
    * Actividad
    * Tipo (Interna / Externa / Muda)
    * Duración (segundos)
    * Inicio / Fin
    """)

# --- TÍTULO ---
st.title("⚡ Analizador SMED 3.0 (Segundos + Cuartiles)")

# --- CARGA DE DATOS ---
st.subheader("1. Cargar Archivo de Cronometraje")
uploaded_file = st.file_uploader("Sube tu Excel (con o sin encabezados extra)", type=["xlsx", "xls"])

if uploaded_file is not None:
    df_original, status = load_data_smart(uploaded_file)
    
    if df_original is None:
        st.error(f"Error al leer archivo: {status}")
        st.stop()
    else:
        st.success("¡Tabla detectada y cargada correctamente!")
else:
    # Datos de ejemplo para demostración si no hay archivo
    st.warning("Vista previa con datos de ejemplo (Sube tu archivo para cambiar).")
    data = {
        "Categoría": ["Mecánica", "Operación", "Mecánica", "Limpieza", "Espera"],
        "Actividad": ["Desmontar tornillo A", "Retirar pieza", "Montar tornillo B", "Limpiar rebaba", "Esperar grúa"],
        "Tipo": ["Interna", "Interna", "Interna", "Externa", "Muda"],
        "Duración": [12.5, 4.2, 15.1, 8.5, 20.0],
        "Inicio": ["10:00:00", "10:00:12", "10:00:16", "10:00:31", "10:00:40"],
        "Fin": ["10:00:12", "10:00:16", "10:00:31", "10:00:40", "10:01:00"]
    }
    df_original = pd.DataFrame(data)

# --- MAPEO DE COLUMNAS ---
# Intentamos normalizar los nombres de columnas automáticamente
cols = df_original.columns.tolist()

# Función para encontrar la columna más parecida
def find_col(keywords, default_index=0):
    for i, col in enumerate(cols):
        if any(k in str(col).lower() for k in keywords):
            return col
    return cols[default_index] if cols else None

# Selección manual si la automática falla
c1, c2, c3, c4 = st.columns(4)
with c1:
    col_act = st.selectbox("Col. Actividad", cols, index=cols.index(find_col(["actividad", "tarea", "descripción"])))
with c2:
    col_tipo = st.selectbox("Col. Tipo", cols, index=cols.index(find_col(["tipo", "clasificación"], 1)))
with c3:
    col_dur = st.selectbox("Col. Duración (Seg)", cols, index=cols.index(find_col(["duración", "tiempo", "seg"], 2)))
with c4:
    col_cat = st.selectbox("Col. Categoría", cols, index=cols.index(find_col(["categoría", "grupo"], 0)))

# Preparamos DataFrame de Trabajo
df_work = df_original.copy()
df_work = df_work.rename(columns={
    col_act: "Actividad",
    col_tipo: "Tipo Actual",
    col_dur: "Duración Actual (s)",
    col_cat: "Categoría"
})

# Aseguramos que la duración sea numérica
df_work["Duración Actual (s)"] = pd.to_numeric(df_work["Duración Actual (s)"], errors='coerce').fillna(0)

# Inicializar columnas futuras si no existen
if "Tipo Futuro" not in df_work.columns:
    df_work["Tipo Futuro"] = df_work["Tipo Actual"]
if "Duración Futura (s)" not in df_work.columns:
    df_work["Duración Futura (s)"] = df_work["Duración Actual (s)"]

# --- EDITOR DE ANÁLISIS ---
st.divider()
st.subheader("2. Clasificación y Análisis de Desperdicio")

# Configuración de columnas del editor
column_config = {
    "Actividad": st.column_config.TextColumn(disabled=True),
    "Categoría": st.column_config.TextColumn(disabled=True),
    "Tipo Actual": st.column_config.SelectboxColumn(
        options=["Interna", "Externa", "Muda"], 
        required=True,
        help="Interna (Paro), Externa (Marcha), Muda (Desperdicio)"
    ),
    "Tipo Futuro": st.column_config.SelectboxColumn(
        options=["Interna", "Externa", "Muda", "Eliminada"], 
        required=True
    ),
    "Duración Actual (s)": st.column_config.NumberColumn(format="%.1f s"),
    "Duración Futura (s)": st.column_config.NumberColumn(format="%.1f s"),
}

# Editor
df_edited = st.data_editor(
    df_work[["Categoría", "Actividad", "Tipo Actual", "Duración Actual (s)", "Tipo Futuro", "Duración Futura (s)"]],
    num_rows="dynamic",
    column_config=column_config,
    use_container_width=True,
    height=400
)

# --- CÁLCULOS ---
def calcular_tiempos(df, col_tipo, col_dur):
    total = df[col_dur].sum()
    interna = df[df[col_tipo].astype(str).str.lower().str.contains("interna", na=False)][col_dur].sum()
    externa = df[df[col_tipo].astype(str).str.lower().str.contains("externa", na=False)][col_dur].sum()
    muda = df[df[col_tipo].astype(str).str.lower().str.contains("muda", na=False)][col_dur].sum()
    return total, interna, externa, muda

t_total_act, t_int_act, t_ext_act, t_muda_act = calcular_tiempos(df_edited, "Tipo Actual", "Duración Actual (s)")
t_total_fut, t_int_fut, t_ext_fut, t_muda_fut = calcular_tiempos(df_edited, "Tipo Futuro", "Duración Futura (s)")

ahorro = t_int_act - t_int_fut
mejora_pct = (ahorro / t_int_act * 100) if t_int_act > 0 else 0

# --- RESULTADOS Y GRÁFICOS ---
st.divider()
st.subheader("3. Dashboard de Resultados")

# Métricas
m1, m2, m3, m4 = st.columns(4)
m1.metric("Tiempo Paro ACTUAL", f"{t_int_act:.1f} s", delta_color="inverse")
m2.metric("Tiempo Paro FUTURO", f"{t_int_fut:.1f} s", delta=f"-{ahorro:.1f} s", delta_color="normal")
m3.metric("Desperdicio (Muda) Eliminado", f"{t_muda_act - t_muda_fut:.1f} s", help="Tiempo de Muda eliminado")
m4.metric("% Reducción de Paro", f"{mejora_pct:.1f}%")

# Gráficos
tab1, tab2 = st.tabs(["📊 Comparativa Global", "📦 Análisis de Cuartiles (Box Plot)"])

with tab1:
    fig = go.Figure()
    # Definición de colores: Interna (Rojo), Externa (Verde), Muda (Gris)
    colors = {'Interna': '#ef553b', 'Externa': '#00cc96', 'Muda': '#7f7f7f'}
    
    # Barra Actual
    fig.add_trace(go.Bar(name='Interna', x=['Actual'], y=[t_int_act], marker_color=colors['Interna']))
    fig.add_trace(go.Bar(name='Externa', x=['Actual'], y=[t_ext_act], marker_color=colors['Externa']))
    fig.add_trace(go.Bar(name='Muda', x=['Actual'], y=[t_muda_act], marker_color=colors['Muda']))
    
    # Barra Futura
    fig.add_trace(go.Bar(name='Interna', x=['Futuro'], y=[t_int_fut], marker_color=colors['Interna'], showlegend=False))
    fig.add_trace(go.Bar(name='Externa', x=['Futuro'], y=[t_ext_fut], marker_color=colors['Externa'], showlegend=False))
    fig.add_trace(go.Bar(name='Muda', x=['Futuro'], y=[t_muda_fut], marker_color=colors['Muda'], showlegend=False))
    
    fig.update_layout(barmode='stack', title="Impacto del SMED (Segundos)", yaxis_title="Segundos")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("##### Distribución de Tiempos por Tipo (Cuartiles)")
    st.caption("Este gráfico muestra la variabilidad de tus tareas. La 'caja' contiene el 50% de las tareas (Cuartil 1 al 3).")
    
    # Box Plot usando Plotly Express para facilidad
    # Usamos los datos actuales para el análisis estadístico
    fig_box = px.box(
        df_edited, 
        x="Tipo Actual", 
        y="Duración Actual (s)", 
        color="Tipo Actual",
        points="all", # Muestra todos los puntos
        color_discrete_map={'Interna': '#ef553b', 'Externa': '#00cc96', 'Muda': '#7f7f7f'},
        title="Dispersión de Duraciones por Tipo"
    )
    st.plotly_chart(fig_box, use_container_width=True)
