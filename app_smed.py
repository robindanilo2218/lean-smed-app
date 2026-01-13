import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="SMED Pro - Análisis", layout="wide")

# --- 2. BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Configuración")
    st.markdown("### Opciones de Carga")
    
    sep_opt = st.selectbox(
        "Separador de CSV",
        ["Auto-Detectar", "Coma (,)", "Punto y Coma (;)", "Tabulación"],
        help="Si falla, prueba cambiar esto."
    )
    
    encoding_opt = st.selectbox(
        "Codificación", 
        ["utf-8", "latin-1", "cp1252"], 
        index=0,
        help="Cambia a 'latin-1' si ves símbolos raros en el texto."
    )
    
    st.divider()
    st.info("SMED Analytics v4.2 (Text Scanner)")

# --- 3. FUNCIÓN DE CARGA AVANZADA (TEXT SCANNER) ---
def load_data_v4_2(file, separator_mode, encoding):
    """
    Escanea el archivo como texto plano primero para encontrar el encabezado,
    saltando metadatos superiores (Fecha, Turno, etc.) que rompen el CSV.
    """
    try:
        filename = file.name.lower()
        is_csv = filename.endswith('.csv')
        
        # Determinar separador
        sep = None
        if separator_mode == "Coma (,)": sep = ","
        elif separator_mode == "Punto y Coma (;)": sep = ";"
        elif separator_mode == "Tabulación": sep = "\t"
        
        header_row_idx = 0
        
        if is_csv:
            # --- ESTRATEGIA TEXTO PLANO (LA SOLUCIÓN) ---
            # Leemos el archivo como strings para no depender de la estructura de columnas
            content = file.getvalue().decode(encoding)
            lines = content.splitlines()
            
            keywords = ["actividad", "duracion", "tiempo", "tipo", "categoria", "grupo", "inicio"]
            found = False
            
            # Buscamos en las primeras 50 líneas dónde empieza la tabla
            for i, line in enumerate(lines[:50]):
                line_lower = line.lower()
                # Si la línea tiene al menos 2 palabras clave y separadores
                matches = sum(1 for w in keywords if w in line_lower)
                if matches >= 2:
                    header_row_idx = i
                    found = True
                    break
            
            if not found:
                return None, "No se encontró la fila de encabezados (Grupo, Actividad...) en las primeras 50 líneas."

            # Ahora cargamos con Pandas saltando las líneas de "basura"
            # Usamos io.StringIO para convertir el string en un "archivo virtual"
            file.seek(0) # Reset no necesario porque usamos 'lines', pero por seguridad
            df = pd.read_csv(
                io.StringIO(content), 
                header=header_row_idx, 
                sep=sep, 
                engine='python',
                on_bad_lines='skip' # Si hay una línea rota más abajo, la salta
            )

        else:
            # Excel (xls/xlsx)
            # Primero leemos sin header para buscar
            preview = pd.read_excel(file, nrows=20, header=None)
            keywords = ["actividad", "duracion", "tiempo", "tipo", "categoria", "grupo"]
            
            for i, row in preview.iterrows():
                row_txt = row.astype(str).str.lower().tolist()
                matches = sum(1 for w in keywords if any(w in str(x) for x in row_txt))
                if matches >= 2:
                    header_row_idx = i
                    break
                    
            df = pd.read_excel(file, header=header_row_idx)
            
        return df, f"Carga OK (Tabla detectada en línea {header_row_idx + 1})"

    except UnicodeDecodeError:
        return None, "Error de codificación. Prueba cambiar 'utf-8' a 'latin-1' en la barra lateral."
    except Exception as e:
        return None, f"Error General: {str(e)}"

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚡ Analizador SMED Pro")

# Carga
st.subheader("1. Cargar Datos")
uploaded_file = st.file_uploader("Sube tu Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # Cargar usando la nueva función v4.2
    df_original, status = load_data_v4_2(uploaded_file, sep_opt, encoding_opt)
    
    if df_original is None:
        st.error(status)
        st.stop()
    
    # Validación básica
    if len(df_original.columns) < 2:
        st.error("⚠️ El archivo se leyó como una sola columna.")
        st.warning(f"Columnas detectadas: '{df_original.columns[0]}'")
        st.markdown("👉 **SOLUCIÓN:** Cambia el 'Separador de CSV' en la izquierda.")
        st.stop()
        
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

        # Crear copia de trabajo
        df_work = df_original.copy()
        
        rename_map = {
            col_act: "Actividad",
            col_cat: "Categoría",
            col_tipo: "Tipo Actual",
            col_dur: "Duración Raw"
        }
        
        df_work = df_work.rename(columns=rename_map)

        # --- LIMPIEZA ---
        # Convertir duración (12,5 -> 12.5) y asegurar numérico
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
            for t in ["Interna", "Externa", "Muda"]:
                val = sum_t(df_edited, "Tipo Actual", "Duración Actual (s)", t.lower())
                fig.add_trace(go.Bar(name=t, x=['Actual'], y=[val], marker_color=colors[t]))
            for t in ["Interna", "Externa", "Muda"]:
                val = sum_t(df_edited, "Tipo Futuro", "Duración Futura (s)", t.lower())
                fig.add_trace(go.Bar(name=t, x=['Futuro'], y=[val], marker_color=colors[t], showlegend=False))
            
            fig.update_layout(barmode='stack', title="Tiempo Total (s)")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.markdown("##### Dispersión de Tiempos")
            eje_x = st.radio("Agrupar por:", ["Tipo Actual", "Categoría", "Actividad"], horizontal=True)
            if eje_x in df_edited.columns and not df_edited.empty:
                if eje_x == "Actividad" and len(df_edited) > 30: st.warning("Muchas actividades. Usa zoom.")
                fig_box = px.box(df_edited, x=eje_x, y="Duración Actual (s)", color="Tipo Actual", color_discrete_map=colors, points="all")
                st.plotly_chart(fig_box, use_container_width=True)

else:
    st.info("👆 Sube tu archivo para comenzar.")
