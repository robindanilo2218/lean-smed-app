import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SMED Pro - Análisis", layout="wide")

# --- 2. FUNCIÓN DE CARGA ROBUSTA (FIX CSV) ---
def load_data_robust(file):
    """
    Carga Excel o CSV. 
    1. Detecta automáticamente si usa coma (,) o punto y coma (;).
    2. Busca dónde empieza la tabla real ignorando títulos.
    """
    try:
        filename = file.name.lower()
        is_csv = filename.endswith('.csv')
        
        # --- ESTRATEGIA PARA CSV (DETECTAR SEPARADOR) ---
        if is_csv:
            try:
                # 'sep=None' y 'engine=python' permiten detectar ; o , automáticamente
                preview = pd.read_csv(file, nrows=20, header=None, sep=None, engine='python')
                file.seek(0) # Rebobinar archivo al inicio
            except Exception as e:
                return None, f"Error leyendo CSV: {e}. Intenta guardar como Excel."
        else:
            # Excel es más estándar
            preview = pd.read_excel(file, nrows=20, header=None)

        # --- BUSCADOR INTELIGENTE DE ENCABEZADOS ---
        header_row_idx = 0
        keywords = ["actividad", "duración", "tiempo", "tipo", "categoría", "inicio", "fin", "descripción"]
        best_match_count = 0
        
        # Escaneamos las primeras 20 filas buscando la cabecera
        for i, row in preview.iterrows():
            row_text = row.astype(str).str.lower().tolist()
            matches = sum(1 for word in keywords if any(word in str(x) for x in row_text))
            
            if matches > best_match_count and matches >= 2:
                best_match_count = matches
                header_row_idx = i
        
        # --- CARGA FINAL CON EL ENCABEZADO CORRECTO ---
        if is_csv:
            df = pd.read_csv(file, header=header_row_idx, sep=None, engine='python')
        else:
            df = pd.read_excel(file, header=header_row_idx)
            
        return df, f"Carga exitosa (Encabezados detectados en fila {header_row_idx + 1})"

    except Exception as e:
        return None, f"Error crítico: {str(e)}"

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Configuración")
    st.info("SMED Analytics v3.3")
    st.markdown("""
    **Guía rápida:**
    1. Sube tu archivo (Excel o CSV).
    2. Verifica las columnas detectadas.
    3. Clasifica (Interna/Externa/Muda).
    4. Analiza los gráficos.
    """)

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚡ Analizador SMED (Segundos + Grupos)")

# Sección de Carga
st.subheader("1. Cargar Archivo")
uploaded_file = st.file_uploader("Sube tu archivo de cronometraje", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # --- PROCESAR ARCHIVO ---
    df_original, status = load_data_robust(uploaded_file)
    
    if df_original is None:
        st.error(status)
        st.stop()
    else:
        st.success(status)
        
        # --- SELECCIÓN DE COLUMNAS ---
        st.subheader("2. Mapeo de Columnas")
        st.caption("Confirma qué columna es cual:")
        
        cols = df_original.columns.tolist()
        
        def get_index(options, keywords):
            for i, opt in enumerate(options):
                if any(k in str(opt).lower() for k in keywords):
                    return i
            return 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            col_act = st.selectbox("Actividad", cols, index=get_index(cols, ["actividad", "tarea", "descripción"]))
        with c2:
            col_cat = st.selectbox("Categoría", cols, index=get_index(cols, ["categoría", "grupo", "área"]))
        with c3:
            col_tipo = st.selectbox("Tipo Original", cols, index=get_index(cols, ["tipo", "clasificación"]))
        with c4:
            col_dur = st.selectbox("Duración", cols, index=get_index(cols, ["duración", "tiempo", "min", "seg"]))

        # Crear DataFrame de Trabajo
        df_work = df_original.copy()
        df_work = df_work.rename(columns={
            col_act: "Actividad",
            col_cat: "Categoría",
            col_tipo: "Tipo Actual",
            col_dur: "Duración Raw"
        })

        # --- LIMPIEZA DE DATOS (CRÍTICO) ---
        # 1. Convertir comas a puntos (12,5 -> 12.5) y asegurar número
        df_work["Duración Actual (s)"] = df_work["Duración Raw"].astype(str).str.replace(',', '.', regex=False)
        df_work["Duración Actual (s)"] = pd.to_numeric(df_work["Duración Actual (s)"], errors='coerce').fillna(0)

        # 2. Inicializar columnas futuras
        if "Tipo Futuro" not in df_work.columns:
            df_work["Tipo Futuro"] = df_work["Tipo Actual"]
        if "Duración Futura (s)" not in df_work.columns:
            df_work["Duración Futura (s)"] = df_work["Duración Actual (s)"]
            
        # --- EDITOR DE DATOS ---
        st.divider()
        st.markdown("### 3. Clasificación y Propuesta")
        
        column_config = {
            "Actividad": st.column_config.TextColumn(width="large", disabled=True),
            "Categoría": st.column_config.TextColumn(disabled=True),
            "Tipo Actual": st.column_config.SelectboxColumn(
                options=["Interna", "Externa", "Muda"], required=True
            ),
            "Tipo Futuro": st.column_config.SelectboxColumn(
                options=["Interna", "Externa", "Muda", "Eliminada"], required=True
            ),
            "Duración Actual (s)": st.column_config.NumberColumn(format="%.2f"),
            "Duración Futura (s)": st.column_config.NumberColumn(format="%.2f"),
        }

        cols_to_show = ["Categoría", "Actividad", "Tipo Actual", "Duración Actual (s)", "Tipo Futuro", "Duración Futura (s)"]
        cols_final = [c for c in cols_to_show if c in df_work.columns]

        df_edited = st.data_editor(
            df_work[cols_final],
            num_rows="dynamic",
            column_config=column_config,
            use_container_width=True,
            height=400
        )

        # --- CÁLCULOS KPI ---
        def sum_time(df, col_tipo, col_time, keyword):
            return df[df[col_tipo].astype(str).str.lower().str.contains(keyword, na=False)][col_time].sum()

        t_int_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "interna")
        t_ext_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "externa")
        t_muda_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "muda")

        t_int_fut = sum_time(df_edited, "Tipo Futuro", "Duración Futura (s)", "interna")
        t_ext_fut = sum_time(df_edited, "Tipo Futuro", "Duración Futura (s)", "externa")
        t_muda_fut = sum_time(df_edited, "Tipo Futuro", "Duración Futura (s)", "muda")

        ahorro = t_int_act - t_int_fut
        pct = (ahorro / t_int_act * 100) if t_int_act > 0 else 0

        # --- RESULTADOS ---
        st.divider()
        st.subheader("Resultados del Análisis")
        
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Paro Actual", f"{t_int_act:.2f} s", delta_color="inverse")
        kpi2.metric("Paro Futuro (Meta)", f"{t_int_fut:.2f} s", delta=f"-{ahorro:.2f} s")
        kpi3.metric("Muda Eliminada", f"{t_muda_act - t_muda_fut:.2f} s")
        kpi4.metric("% Reducción", f"{pct:.1f}%")

        # --- GRÁFICOS ---
        tab_a, tab_b = st.tabs(["📊 Global (Cascada)", "📦 Análisis de Variabilidad (Cuartiles)"])
        colors = {'Interna': '#ef553b', 'Externa': '#00cc96', 'Muda': '#7f7f7f'}

        with tab_a:
            fig = go.Figure()
            # Actual
            fig.add_trace(go.Bar(name='Interna', x=['Actual'], y=[t_int_act], marker_color=colors['Interna']))
            fig.add_trace(go.Bar(name='Externa', x=['Actual'], y=[t_ext_act], marker_color=colors['Externa']))
            fig.add_trace(go.Bar(name='Muda', x=['Actual'], y=[t_muda_act], marker_color=colors['Muda']))
            # Futuro
            fig.add_trace(go.Bar(name='Interna', x=['Futuro'], y=[t_int_fut], marker_color=colors['Interna'], showlegend=False))
            fig.add_trace(go.Bar(name='Externa', x=['Futuro'], y=[t_ext_fut], marker_color=colors['Externa'], showlegend=False))
            fig.add_trace(go.Bar(name='Muda', x=['Futuro'], y=[t_muda_fut], marker_color=colors['Muda'], showlegend=False))
            
            fig.update_layout(barmode='stack', title="Tiempo Total de Cambio", yaxis_title="Segundos")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab_b:
            st.markdown("##### 🔍 Radiografía del Proceso")
            eje_x = st.radio("Agrupar dispersión por:", ["Tipo Actual", "Categoría", "Actividad"], horizontal=True)
            
            if not df_edited.empty:
                if eje_x == "Actividad" and len(df_edited) > 30:
                    st.warning(f"⚠️ Mostrando {len(df_edited)} actividades.")
                
                if eje_x in df_edited.columns:
                    fig_box = px.box(
                        df_edited, x=eje_x, y="Duración Actual (s)", color="Tipo Actual",
                        color_discrete_map=colors, points="all", hover_data=["Actividad"],
                        title=f"Dispersión de Tiempos por {eje_x}"
                    )
                    st.plotly_chart(fig_box, use_container_width=True)
                else:
                    st.warning(f"La columna '{eje_x}' no existe en el archivo cargado.")

else:
    st.info("👆 Sube un archivo CSV o Excel arriba para comenzar.")
