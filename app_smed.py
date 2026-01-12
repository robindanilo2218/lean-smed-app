import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="SMED Pro - Análisis", layout="wide")

# --- FUNCIONES AUXILIARES ---
def load_data_robust(file):
    """
    Carga Excel o CSV. Intenta detectar encabezados, pero si falla,
    carga desde la fila 0 para asegurar que siempre haya datos.
    """
    try:
        # 1. Determinar tipo de archivo por extensión
        filename = file.name.lower()
        is_csv = filename.endswith('.csv')
        
        # 2. Lectura preliminar para buscar encabezados (Smart Search)
        # Leemos un trozo pequeño para analizar
        if is_csv:
            preview = pd.read_csv(file, nrows=20, header=None)
            # Resetear el puntero del archivo para leerlo entero después
            file.seek(0) 
        else:
            preview = pd.read_excel(file, nrows=20, header=None)

        # 3. Buscar fila de encabezados
        header_row_idx = 0
        found = False
        
        # Buscamos palabras clave en las primeras filas
        keywords = ["actividad", "duración", "tiempo", "tipo", "categoría", "inicio"]
        
        for i, row in preview.iterrows():
            # Convertimos toda la fila a texto minúscula
            row_text = row.astype(str).str.lower().tolist()
            # Si encontramos al menos 2 palabras clave, asumimos que aquí empieza
            matches = sum(1 for word in keywords if any(word in str(x) for x in row_text))
            if matches >= 2:
                header_row_idx = i
                found = True
                break
        
        # 4. Carga Final de Datos
        if is_csv:
            df = pd.read_csv(file, header=header_row_idx)
        else:
            df = pd.read_excel(file, header=header_row_idx)
            
        return df, f"Carga exitosa (Encabezados en fila {header_row_idx + 1})"

    except Exception as e:
        return None, str(e)

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚙️ Configuración")
    st.info("Versión 3.1 - Fix CSV y Cálculos")
    st.markdown("Si la tabla sale vacía, revisa que los selectores de columna coincidan con tu archivo.")

# --- TÍTULO ---
st.title("⚡ Analizador SMED 3.1")

# --- 1. CARGA DE DATOS ---
st.subheader("1. Cargar Archivo")
uploaded_file = st.file_uploader("Sube tu Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    df_original, status = load_data_robust(uploaded_file)
    
    if df_original is None:
        st.error(f"Error crítico: {status}")
        st.stop()
    else:
        st.success(status)
        
        # --- 2. MAPEO DE COLUMNAS ---
        st.subheader("2. Confirmar Columnas")
        st.caption("Por favor, confirma qué columna es cuál:")
        
        cols = df_original.columns.tolist()
        
        # Función auxiliar para autoseleccionar
        def get_index(options, keywords):
            for i, opt in enumerate(options):
                if any(k in str(opt).lower() for k in keywords):
                    return i
            return 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            col_act = st.selectbox("Actividad", cols, index=get_index(cols, ["actividad", "tarea", "descripción"]))
        with c2:
            col_cat = st.selectbox("Categoría", cols, index=get_index(cols, ["categoría", "grupo"]))
        with c3:
            col_tipo = st.selectbox("Tipo (Int/Ext)", cols, index=get_index(cols, ["tipo", "clasificación"]))
        with c4:
            col_dur = st.selectbox("Duración", cols, index=get_index(cols, ["duración", "tiempo", "min", "seg"]))

        # Crear DataFrame de Trabajo
        df_work = df_original.copy()
        
        # Renombrar para uso interno
        df_work = df_work.rename(columns={
            col_act: "Actividad",
            col_cat: "Categoría",
            col_tipo: "Tipo Actual",
            col_dur: "Duración Raw"
        })

        # --- LIMPIEZA DE DATOS (CRÍTICO PARA CÁLCULOS) ---
        # 1. Convertir duración a números (Manejo de comas y textos)
        # Reemplazar comas por puntos si existen (ej: 12,5 -> 12.5)
        df_work["Duración Actual (s)"] = df_work["Duración Raw"].astype(str).str.replace(',', '.', regex=False)
        # Forzar conversión a numérico, errores se vuelven 0
        df_work["Duración Actual (s)"] = pd.to_numeric(df_work["Duración Actual (s)"], errors='coerce').fillna(0)

        # 2. Rellenar Tipos vacíos
        if "Tipo Futuro" not in df_work.columns:
            df_work["Tipo Futuro"] = df_work["Tipo Actual"]
        if "Duración Futura (s)" not in df_work.columns:
            df_work["Duración Futura (s)"] = df_work["Duración Actual (s)"]
            
        # --- EDITOR ---
        st.divider()
        st.markdown("### 3. Clasificación y Mejora")
        
        column_config = {
            "Actividad": st.column_config.TextColumn(width="large", disabled=True),
            "Tipo Actual": st.column_config.SelectboxColumn(
                options=["Interna", "Externa", "Muda"], required=True
            ),
            "Tipo Futuro": st.column_config.SelectboxColumn(
                options=["Interna", "Externa", "Muda", "Eliminada"], required=True
            ),
            "Duración Actual (s)": st.column_config.NumberColumn(format="%.2f"),
            "Duración Futura (s)": st.column_config.NumberColumn(format="%.2f"),
        }

        # Mostramos columnas clave
        cols_to_show = ["Categoría", "Actividad", "Tipo Actual", "Duración Actual (s)", "Tipo Futuro", "Duración Futura (s)"]
        # Filtramos solo las que existen (por si Categoría no se mapeó bien)
        cols_final = [c for c in cols_to_show if c in df_work.columns]

        df_edited = st.data_editor(
            df_work[cols_final],
            num_rows="dynamic",
            column_config=column_config,
            use_container_width=True,
            height=400
        )

        # --- CÁLCULOS ---
        def sum_time(df, col_tipo, col_time, keyword):
            return df[df[col_tipo].astype(str).str.lower().str.contains(keyword, na=False)][col_time].sum()

        t_int_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "interna")
        t_int_fut = sum_time(df_edited, "Tipo Futuro", "Duración Futura (s)", "interna")
        
        t_ext_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "externa")
        t_ext_fut = sum_time(df_edited, "Tipo Futuro", "Duración Futura (s)", "externa")

        t_muda_act = sum_time(df_edited, "Tipo Actual", "Duración Actual (s)", "muda")
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

        # Gráficos
        tab_a, tab_b = st.tabs(["Global", "Detalle por Tipo"])
        
        with tab_a:
            fig = go.Figure()
            colors = {'Interna': '#ef553b', 'Externa': '#00cc96', 'Muda': '#7f7f7f'}
            
            fig.add_trace(go.Bar(name='Interna', x=['Actual'], y=[t_int_act], marker_color=colors['Interna']))
            fig.add_trace(go.Bar(name='Externa', x=['Actual'], y=[t_ext_act], marker_color=colors['Externa']))
            fig.add_trace(go.Bar(name='Muda', x=['Actual'], y=[t_muda_act], marker_color=colors['Muda']))
            
            fig.add_trace(go.Bar(name='Interna', x=['Futuro'], y=[t_int_fut], marker_color=colors['Interna'], showlegend=False))
            fig.add_trace(go.Bar(name='Externa', x=['Futuro'], y=[t_ext_fut], marker_color=colors['Externa'], showlegend=False))
            fig.add_trace(go.Bar(name='Muda', x=['Futuro'], y=[t_muda_fut], marker_color=colors['Muda'], showlegend=False))
            
            fig.update_layout(barmode='stack', title="Tiempo Total de Cambio (Segundos)")
            st.plotly_chart(fig, use_container_width=True)
            
        with tab_b:
            if not df_edited.empty:
                fig_box = px.box(
                    df_edited, x="Tipo Actual", y="Duración Actual (s)", color="Tipo Actual",
                    color_discrete_map=colors, points="all", title="Dispersión de Tiempos"
                )
                st.plotly_chart(fig_box, use_container_width=True)
else:
    st.info("👆 Sube un archivo CSV o Excel para comenzar.")
