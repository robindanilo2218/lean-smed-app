import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- 1. CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SMED Pro - Análisis", layout="wide")

# --- 2. BARRA LATERAL Y CONFIGURACIÓN ---
with st.sidebar:
    st.title("⚙️ Configuración")
    st.markdown("### Opciones de Carga")
    
    # NUEVO: Selector manual para arreglar el error de columnas pegadas
    sep_opt = st.selectbox(
        "Separador de CSV",
        ["Auto-Detectar", "Coma (,)", "Punto y Coma (;)", "Tabulación"],
        help="Si tus columnas salen pegadas (ej: 'Grupo,Actividad...'), cambia esto."
    )
    
    st.divider()
    st.info("SMED Analytics v4.0")
    st.markdown("""
    **Guía rápida:**
    1. Sube tu archivo.
    2. Si sale error, cambia el 'Separador' arriba.
    3. Confirma las columnas.
    4. Analiza.
    """)

# --- 3. FUNCIÓN DE CARGA ROBUSTA ---
def load_data_v4(file, separator_mode):
    """
    Carga datos permitiendo al usuario forzar el separador si falla el automático.
    """
    try:
        filename = file.name.lower()
        is_csv = filename.endswith('.csv')
        
        # Determinar separador según selección del usuario
        sep = None
        engine = None
        
        if is_csv:
            if separator_mode == "Coma (,)": sep = ","
            elif separator_mode == "Punto y Coma (;)": sep = ";"
            elif separator_mode == "Tabulación": sep = "\t"
            else: # Auto
                sep = None
                engine = 'python'

        # --- ESTRATEGIA DE LECTURA ---
        # 1. Detectar encabezados (fila donde empieza la tabla)
        # Leemos un poco del archivo para buscar palabras clave
        if is_csv:
            # Si es auto, usamos engine python, si es manual usamos c (más rápido)
            try:
                preview = pd.read_csv(file, nrows=20, header=None, sep=sep, engine=engine)
            except:
                # Si falla auto, intentamos coma por defecto
                file.seek(0)
                preview = pd.read_csv(file, nrows=20, header=None, sep=",")
            file.seek(0)
        else:
            preview = pd.read_excel(file, nrows=20, header=None)

        # Buscador de encabezados
        header_idx = 0
        keywords = ["actividad", "duración", "tiempo", "tipo", "categoría", "inicio", "grupo"]
        max_matches = 0
        
        for i, row in preview.iterrows():
            row_txt = row.astype(str).str.lower().tolist()
            matches = sum(1 for w in keywords if any(w in str(x) for x in row_txt))
            if matches > max_matches and matches >= 2:
                max_matches = matches
                header_idx = i
        
        # 2. Carga Final
        if is_csv:
            df = pd.read_csv(file, header=header_idx, sep=sep, engine=engine)
        else:
            df = pd.read_excel(file, header=header_idx)
            
        return df, f"Carga OK (Encabezados en fila {header_idx + 1})"

    except Exception as e:
        return None, f"Error: {str(e)}"

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚡ Analizador SMED Pro")

# Carga
st.subheader("1. Cargar Datos")
uploaded_file = st.file_uploader("Sube tu Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # Cargar con la opción del sidebar
    df_original, status = load_data_v4(uploaded_file, sep_opt)
    
    if df_original is None:
        st.error(status)
        st.stop()
    
    # --- VALIDACIÓN CRÍTICA ---
    # Si detectamos que solo hay 1 columna, avisamos al usuario
    if len(df_original.columns) < 2:
        st.error("⚠️ ¡ALERTA! El archivo se leyó como una sola columna.")
        st.warning(f"Parece que las columnas están pegadas: '{df_original.columns[0]}'")
        st.markdown("👉 **SOLUCIÓN:** Ve a la barra lateral izquierda y cambia el **'Separador de CSV'** a **Punto y Coma (;)** o **Coma (,)** hasta que veas las columnas separadas.")
        st.stop() # Detenemos aquí para evitar el KeyError
        
    else:
        st.success(status)
        
        # --- 2. MAPEO DE COLUMNAS ---
        st.subheader("2. Validar Columnas")
        cols = df_original.columns.tolist()
        
        def get_idx(opts, keys):
            for i, o in enumerate(opts):
                if any(k in str(o).lower() for k in keys): return i
            return 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            col_act = st.selectbox("Actividad", cols, index=get_idx(cols, ["actividad", "tarea", "descrip"]))
        with c2:
            col_cat = st.selectbox("Categoría", cols, index=get_idx(cols, ["categoría", "grupo", "área"]))
        with c3:
            col_tipo = st.selectbox("Tipo Original", cols, index=get_idx(cols, ["tipo", "clasi"]))
        with c4:
            col_dur = st.selectbox("Duración", cols, index=get_idx(cols, ["duración", "tiempo", "seg", "min"]))

        # Crear copia de trabajo y renombrar
        df_work = df_original.copy()
        
        # Diccionario de renombre seguro
        rename_map = {
            col_act: "Actividad",
            col_cat: "Categoría",
            col_tipo: "Tipo Actual",
            col_dur: "Duración Raw"
        }
        
        # Verificar que no estemos asignando la misma columna a dos cosas (evita KeyError)
        if len(set(rename_map.keys())) < 4:
            st.warning("⚠️ Cuidado: Has seleccionado la misma columna para varios campos. Verifica los selectores arriba.")

        df_work = df_work.rename(columns=rename_map)

        # --- LIMPIEZA ---
        # Convertir duración (12,5 -> 12.5)
        df_work["Duración Actual (s)"] = df_work["Duración Raw"].astype(str).str.replace(',', '.', regex=False)
        df_work["Duración Actual (s)"] = pd.to_numeric(df_work["Duración Actual (s)"], errors='coerce').fillna(0)

        # Inicializar futuros
        if "Tipo Futuro" not in df_work.columns: df_work["Tipo Futuro"] = df_work["Tipo Actual"]
        if "Duración Futura (s)" not in df_work.columns: df_work["Duración Futura (s)"] = df_work["Duración Actual (s)"]

        # --- 3. EDITOR ---
        st.divider()
        st.subheader("3. Clasificación")
        
        col_conf = {
            "Actividad": st.column_config.TextColumn(width="large", disabled=True),
            "Categoría": st.column_config.TextColumn(disabled=True),
            "Tipo Actual": st.column_config.SelectboxColumn(options=["Interna", "Externa", "Muda"], required=True),
            "Tipo Futuro": st.column_config.SelectboxColumn(options=["Interna", "Externa", "Muda", "Eliminada"], required=True),
            "Duración Actual (s)": st.column_config.NumberColumn(format="%.2f"),
            "Duración Futura (s)": st.column_config.NumberColumn(format="%.2f"),
        }
        
        final_cols = [c for c in ["Categoría", "Actividad", "Tipo Actual", "Duración Actual (s)", "Tipo Futuro", "Duración Futura (s)"] if c in df_work.columns]
        
        df_edited = st.data_editor(df_work[final_cols], num_rows="dynamic", column_config=col_conf, use_container_width=True, height=400)

        # --- 4. RESULTADOS ---
        def sum_t(df, c_type, c_val, key):
            return df[df[c_type].astype(str).str.lower().str.contains(key, na=False)][c_val].sum()

        t_int_act = sum_t(df_edited, "Tipo Actual", "Duración Actual (s)", "interna")
        t_int_fut = sum_t(df_edited, "Tipo Futuro", "Duración Futura (s)", "interna")
        ahorro = t_int_act - t_int_fut
        pct = (ahorro / t_int_act * 100) if t_int_act > 0 else 0
        
        st.divider()
        st.subheader("Resultados")
        k1, k2, k3 = st.columns(3)
        k1.metric("Paro Actual", f"{t_int_act:.1f} s", delta_color="inverse")
        k2.metric("Paro Futuro", f"{t_int_fut:.1f} s", delta=f"-{ahorro:.1f} s")
        k3.metric("% Reducción", f"{pct:.1f}%")

        # Gráficos
        tab1, tab2 = st.tabs(["📊 Global", "📦 Variabilidad"])
        colors = {'Interna': '#ef553b', 'Externa': '#00cc96', 'Muda': '#7f7f7f'}

        with tab1:
            fig = go.Figure()
            # Actual
            for t in ["Interna", "Externa", "Muda"]:
                val = sum_t(df_edited, "Tipo Actual", "Duración Actual (s)", t.lower())
                fig.add_trace(go.Bar(name=t, x=['Actual'], y=[val], marker_color=colors[t]))
            # Futuro
            for t in ["Interna", "Externa", "Muda"]:
                val = sum_t(df_edited, "Tipo Futuro", "Duración Futura (s)", t.lower())
                fig.add_trace(go.Bar(name=t, x=['Futuro'], y=[val], marker_color=colors[t], showlegend=False))
            
            fig.update_layout(barmode='stack', title="Tiempo Total (s)")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.markdown("##### Dispersión de Tiempos")
            eje_x = st.radio("Agrupar por:", ["Tipo Actual", "Categoría", "Actividad"], horizontal=True)
            if eje_x in df_edited.columns and not df_edited.empty:
                if eje_x == "Actividad" and len(df_edited) > 30: st.warning("Muchas actividades detectadas. Usa zoom.")
                fig_box = px.box(df_edited, x=eje_x, y="Duración Actual (s)", color="Tipo Actual", color_discrete_map=colors, points="all")
                st.plotly_chart(fig_box, use_container_width=True)

else:
    st.info("👆 Sube tu archivo para comenzar.")
