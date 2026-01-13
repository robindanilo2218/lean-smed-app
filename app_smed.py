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
            # Leemos las primeras lineas como texto puro para 'olfatear' el separador
            try:
                # Intentamos leer con el motor de Python que es más flexible
                preview = pd.read_csv(file, nrows=20, header=None, sep=None, engine='python')
                file.seek(0) # Rebobinar archivo
            except:
                # Si falla, forzamos lectura manual básica
                return None, "El formato del CSV es ilegible. Intenta guardarlo como Excel (.xlsx)"

        else:
            # Excel es más fácil
            preview = pd.read_excel(file, nrows=20, header=None)

        # --- BUSCADOR INTELIGENTE DE ENCABEZADOS ---
        header_row_idx = 0
        keywords = ["actividad", "duración", "tiempo", "tipo", "categoría", "inicio", "fin", "descripción"]
        
        best_match_count = 0
        
        # Escaneamos las primeras 20 filas
        for i, row in preview.iterrows():
            row_text = row.astype(str).str.lower().tolist()
            # Contamos cuántas palabras clave aparecen en esta fila
            matches = sum(1 for word in keywords if any(word in str(x) for x in row_text))
            
            # Si encontramos una fila con más coincidencias que las anteriores, esa es la ganadora
            if matches > best_match_count and matches >= 2:
                best_match_count = matches
                header_row_idx = i
        
        # --- CARGA FINAL CON EL ENCABEZADO CORRECTO ---
        if is_csv:
            # Usamos engine='python' y sep=None para que detecte ; o , automáticamente
            df = pd.read_csv(file, header=header_row_idx, sep=None, engine='python')
        else:
            df = pd.read_excel(file, header=header_row_idx)
            
        return df, f"Carga exitosa (Encabezados detectados en fila {header_row_idx + 1})"

    except Exception as e:
        return None, f"Error detallado: {str(e)}"
