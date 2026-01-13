import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="SMED Pro", layout="wide")

# --- 2. BARRA LATERAL (CONTROLES) ---
with st.sidebar:
    st.title("⚙️ Configuración")
    st.markdown("### 1. Formato de Archivo")
    
    # Selector de Separador (Coma funcionó en tu foto, mantenlo)
    sep_opt = st.selectbox(
        "Separador",
        ["Coma (,)", "Punto y Coma (;)", "Tabulación", "Auto"],
        index=0
    )
    
    encoding_opt = st.selectbox("Codificación", ["utf-8", "latin-1", "cp1252"], index=0)
    
    st.divider()
    st.markdown("### 2. Ajuste de Encabezados")
    st.info("Si las columnas se llaman 'SELLO' o datos raros, cambia este número:")
    
    # NUEVO: Control manual para subir/bajar la fila de títulos
    header_adjust = st.number_input(
        "Fila del Título (Encabezado)", 
        min_value=0, 
        max_value=50, 
        value=0, 
        help="0 es la detección automática. Si sale mal, prueba poner 8, 9 o 10."
    )
    
    st.divider()
    st.caption("SMED Analytics v5.0 (Manual Override)")

# --- 3. FUNCIÓN DE CARGA ---
def load_data_v5(file, separator_mode, encoding, manual_header_row):
    try:
        filename = file.name.lower()
        is_csv = filename.endswith('.csv')
        
        sep = "," if separator_mode == "Coma (,)" else ";" if separator_mode == "Punto y Coma (;)" else "\t" if separator_mode == "Tabulación" else None
        
        # 1. Detectar encabezado automáticamente si el usuario lo dejó en 0
        header_idx = manual_header_row
        
        if manual_header_row == 0: # Modo Automático
            if is_csv:
                content = file.getvalue().decode(encoding)
                lines = content.splitlines()
                keywords = ["actividad", "duracion", "tiempo", "tipo", "grupo", "inicio"]
                
                # Buscamos la fila que tenga más coincidencias
                best_match = -1
                max_hits = 0
                for i, line in enumerate(lines[:50]):
                    hits = sum(1 for w in keywords if w in line.lower())
                    if hits >= 2 and hits > max_hits:
                        max_hits = hits
                        best_match = i
                
                if best_match != -1:
                    header_idx = best_match
            else:
                # Excel auto-detect
                preview = pd.read_excel(file, nrows=20, header=None)
                # (Lógica simplificada para excel, asume fila detectada anteriormente)
        
        # 2. Cargar DataFrame
        if is_csv:
            file.seek(0) # Reset
            # Leemos todo como texto primero para limpiar líneas malas arriba
            content = file.getvalue().decode(encoding)
            
            # Usamos engine='python' y saltamos filas hasta el header
            df = pd.read_csv(
                io.StringIO(content),
                header=header_idx,
                sep=sep,
                engine='python',
                on_bad_lines='skip'
            )
        else:
            df = pd.read_excel(file, header=header_idx)
            
        return df, header_idx

    except Exception as e:
        return None, str(e)

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚡ Analizador SMED (Control Total)")

st.subheader("1. Cargar Datos")
uploaded_file = st.file_uploader("Sube tu archivo", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    # Cargar
    df_original, detected_row = load_data_v5(uploaded_file, sep_opt, encoding_opt, header_adjust)
    
    if df_original is None:
        st.error(f"Error: {detected_row}") # detected_row contiene el msg de error aquí
        st.stop()
        
    # Mostrar qué fila se usó
    if header_adjust == 0:
        st.success(f"✅ Encabezados detectados automáticamente en la fila **{detected_row}**. (Si es incorrecto, cámbialo en la barra lateral).")
    else:
        st.success(f"✅ Usando fila **{header_adjust}** como encabezado manual.")

    # Validación de Columnas
    if len(df_original.columns) < 2:
        st.error("⚠️ El archivo tiene 1 sola columna. Cambia el 'Separador' en la izquierda.")
        st.stop()

    st.subheader("2. Validar Columnas")
    
    # --- PREVENCIÓN DE ERROR KEYERROR ---
    cols = df_original.columns.tolist()
    
    # Función de búsqueda inteligente
    def get_idx(opts, keys):
        for i, o in enumerate(opts):
            if any(k in str(o).lower() for k in keys): return i
        return 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        col_act = st.selectbox("Actividad", cols, index=get_idx(cols, ["actividad", "tarea"]))
    with c2:
        col_cat = st.selectbox("Categoría", cols, index=get_idx(cols, ["categoría", "grupo", "área"]))
    with c3:
        col_tipo = st.selectbox("Tipo Original", cols, index=get_idx(cols, ["tipo", "clasi"]))
    with c4:
        col_dur = st.selectbox("Duración", cols, index=get_idx(cols, ["duración", "tiempo", "seg"]))

    # --- VALIDACIÓN DE SEGURIDAD (NUEVO) ---
    # Si el usuario selecciona la misma columna para todo (ej: SELLO), detenemos antes de que falle
    selected_cols = [col_act, col_cat, col_tipo, col_dur]
    if len(set(selected_cols)) < 3: # Si hay muchas repetidas
        st.warning("⚠️ **¡Atención!** Has seleccionado la misma columna para varios campos.")
        st.markdown(f"Parece que tus columnas se llaman **'{col_act}'**.")
        st.error("👉 **SOLUCIÓN:** Ve a la barra lateral izquierda y cambia el número **'Fila del Título'**. Prueba subirlo o bajarlo (ej: pon 8 o 9) hasta que veas los nombres correctos ('Grupo', 'Actividad', etc).")
        st.stop()

    # Si pasa la validación, procesamos
    df_work = df_original.copy()
    rename_map = {col_act: "Actividad", col_cat: "Categoría", col_tipo: "Tipo Actual", col_dur: "Duración Raw"}
    df_work = df_work.rename(columns=rename_map)

    # Limpieza
    df_work["Duración Actual (s)"] = df_work["Duración Raw"].astype(str).str.replace(',', '.', regex=False)
    df_work["Duración Actual (s)"] = pd.to_numeric(df_work["Duración Actual (s)"], errors='coerce').fillna(0)

    if "Tipo Futuro" not in df_work.columns: df_work["Tipo Futuro"] = df_work["Tipo Actual"]
    if "Duración Futura (s)" not in df_work.columns: df_work["Duración Futura (s)"] = df_work["Duración Actual (s)"]

    # --- EDITOR ---
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

    # --- RESULTADOS ---
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
        eje_x = st.radio("Agrupar por:", ["Tipo Actual", "Categoría", "Actividad"], horizontal=True)
        if eje_x in df_edited.columns and not df_edited.empty:
            fig_box = px.box(df_edited, x=eje_x, y="Duración Actual (s)", color="Tipo Actual", color_discrete_map=colors, points="all")
            st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("👆 Sube tu archivo.")
