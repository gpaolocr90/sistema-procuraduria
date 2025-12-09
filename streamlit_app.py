import streamlit as st
import socket
import pandas as pd
from sqlalchemy import text

# ==========================================
# 🚑 PARCHE OBLIGATORIO IPV4 (No borrar)
# ==========================================
original_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo
# ==========================================

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Procuraduria", page_icon="⚖️", layout="wide")

# --- CONEXIÓN ---
try:
    conn = st.connection("supabase", type="sql", ttl=0)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- FUNCIONES ---

def obtener_ultimo_movimiento(nro, anio):
    """Busca solo el movimiento más reciente para la tabla principal"""
    sql = f"""
    SELECT fecha_mov, tipo_mov, detalle
    FROM movimiento_legajos
    WHERE CAST(legajo_mov AS TEXT) = '{nro}' 
      AND CAST(legajo_año_mov AS TEXT) = '{anio}'
    ORDER BY fecha_mov DESC
    LIMIT 1
    """
    try:
        df = conn.query(sql)
        if not df.empty:
            return df.iloc[0] # Retorna la primera fila (la más reciente)
        return None
    except:
        return None

def buscar_legajos(legajo, anio, expediente, abogado, estado):
    filtros = []
    
    # 1. QUERY CON TODAS LAS COLUMNAS QUE PEDISTE
    # Usamos minúsculas porque así quedó tu base de datos limpia
    sql_base = """
    SELECT 
        legajo_nro, 
        legajo_año, 
        exp_primera_instancia, 
        juzgado_primera_instancia,
        demandante, 
        inculpado,
        nombre_materia, 
        nombre_naturaleza,
        nombre_institucion,
        prioridad_proceso,
        tipo_proceso,
        estadolegajo_id, 
        estado_actual_resumen, 
        nombre_abogado, 
        ubicacion_archivo
    FROM legajos
    WHERE 1=1
    """
    
    # 2. APLICAR FILTROS
    if legajo: filtros.append(f"AND CAST(legajo_nro AS TEXT) = '{legajo.strip()}'")
    if anio: filtros.append(f"AND CAST(legajo_año AS TEXT) = '{anio.strip()}'")
    if expediente: filtros.append(f"AND exp_primera_instancia ILIKE '%{expediente.strip()}%'")
    if abogado: filtros.append(f"AND nombre_abogado ILIKE '%{abogado.strip()}%'")
    if estado: filtros.append(f"AND estadolegajo_id ILIKE '%{estado.strip()}%'")
    
    query_final = sql_base + " " + " ".join(filtros) + " ORDER BY legajo_año DESC, legajo_nro DESC LIMIT 50"
    
    try:
        df = conn.query(query_final)
        
        if not df.empty:
            # 3. AGREGAR DATOS DEL ÚLTIMO MOVIMIENTO (Loop Inteligente)
            # Creamos listas vacías para llenar los datos extra
            fechas, tipos, detalles = [], [], []
            
            for index, row in df.iterrows():
                # Buscamos el mov más reciente de cada legajo encontrado
                mov = obtener_ultimo_movimiento(row['legajo_nro'], row['legajo_año'])
                if mov is not None:
                    # Formatear fecha si existe
                    f_str = pd.to_datetime(mov['fecha_mov']).strftime('%d/%m/%Y') if mov['fecha_mov'] else ""
                    fechas.append(f_str)
                    tipos.append(mov['tipo_mov'])
                    detalles.append(mov['detalle'])
                else:
                    fechas.append("")
                    tipos.append("")
                    detalles.append("")
            
            # Insertamos las columnas nuevas al DataFrame
            df['fecha_ult_mov'] = fechas
            df['tipo_mov'] = tipos
            df['detalle_ult_mov'] = detalles

            # 4. RENOMBRAR COLUMNAS (MAPPING)
            # Mapeamos de tus columnas minúsculas (DB) a tus Nombres Mayúsculos (Vista)
            df = df.rename(columns={
                'legajo_nro': 'LEGAJO', 
                'legajo_año': 'AÑO',
                'exp_primera_instancia': 'EXPEDIENTE', 
                'juzgado_primera_instancia': 'INSTANCIA',
                'demandante': 'DENUNCIANTE', 
                'inculpado': 'DENUNCIADO/IMPUTADO',
                'nombre_materia': 'MATERIA', 
                'nombre_naturaleza': 'TIPO MATERIA',
                'nombre_institucion': 'ENTIDAD', 
                'prioridad_proceso': 'EMBLEMATICO',
                'tipo_proceso': 'TIPO PROCESO', 
                'estadolegajo_id': 'ESTADO',
                'estado_actual_resumen': 'OBSERVACIONES', 
                'nombre_abogado': 'ABOGADO',
                'ubicacion_archivo': 'UBICACION',
                # Columnas extra del movimiento
                'fecha_ult_mov': 'FECHA ULT. MOV',
                'tipo_mov': 'TIPO MOV',
                'detalle_ult_mov': 'DETALLE ULT. MOV'
            })

            # 5. ORDENAR COLUMNAS
            columnas_ordenadas = [
                'LEGAJO', 'AÑO', 'EXPEDIENTE', 'ABOGADO', 'ESTADO',
                'INSTANCIA', 'DENUNCIANTE', 'DENUNCIADO/IMPUTADO', 'MATERIA', 'ENTIDAD', 
                'OBSERVACIONES', 'FECHA ULT. MOV', 'TIPO MOV', 'DETALLE ULT. MOV',
                'TIPO MATERIA', 'EMBLEMATICO', 'TIPO PROCESO', 'UBICACION'
            ]
            
            # Filtramos solo las que existan para evitar errores si falta alguna
            cols_final = [c for c in columnas_ordenadas if c in df.columns]
            return df[cols_final]
            
        return df
        
    except Exception as e:
        st.error(f"Error buscando: {e}")
        return pd.DataFrame()

def obtener_historial_completo(nro, anio):
    sql = f"""
    SELECT fecha_mov, tipo_mov, detalle, usuario
    FROM movimiento_legajos
    WHERE CAST(legajo_mov AS TEXT) = '{nro}' 
      AND CAST(legajo_año_mov AS TEXT) = '{anio}'
    ORDER BY fecha_mov DESC
    """
    try:
        return conn.query(sql)
    except Exception as e:
        st.error(f"Error historial: {e}")
        return pd.DataFrame()

# --- INTERFAZ GRÁFICA ---
st.title("⚖️ Sistema Procuraduría (Nube)")
st.caption("Conectado a Supabase (Oficial)")

tab1, tab2 = st.tabs(["🔍 Buscador Maestro", "📂 Expediente Detallado"])

# --- PESTAÑA 1: BUSCADOR ---
with tab1:
    c1, c2, c3 = st.columns(3)
    f_leg = c1.text_input("Legajo")
    f_ani = c2.text_input("Año")
    f_abo = c3.text_input("Abogado")
    
    c4, c5 = st.columns(2)
    f_exp = c4.text_input("Expediente")
    f_est = c5.text_input("Estado")
    
    if st.button("🔎 Buscar", type="primary"):
        with st.spinner('Procesando consulta...'):
            df = buscar_legajos(f_leg, f_ani, f_exp, f_abo, f_est)
        
        if not df.empty:
            st.success(f"Registros encontrados: {len(df)}")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("No se encontraron resultados.")

# --- PESTAÑA 2: DETALLE ---
with tab2:
    c1, c2, c3 = st.columns([1, 1, 1])
    l_ver = c1.text_input("Ver Legajo N°", key="v_l")
    a_ver = c2.text_input("Del Año", key="v_a")
    
    with c3:
        st.write("")
        st.write("")
        btn = st.button("Ver Ficha", type="secondary")
    
    if btn and l_ver and a_ver:
        q = f"SELECT * FROM legajos WHERE CAST(legajo_nro AS TEXT)='{l_ver}' AND CAST(legajo_año AS TEXT)='{a_ver}' LIMIT 1"
        try:
            df_cab = conn.query(q)
            if not df_cab.empty:
                row = df_cab.iloc[0]
                st.divider()
                st.subheader(f"Expediente {l_ver}-{a_ver}")
                
                # Manejo seguro de columnas con .get() por si acaso
                st.info(f"Materia: {row.get('nombre_materia','')} | Estado: {row.get('estadolegajo_id','')}")
                st.write(f"**Abogado:** {row.get('nombre_abogado','')}")
                st.write(f"**Resumen:** {row.get('estado_actual_resumen','')}")
                
                st.markdown("### 📜 Historial Completo")
                df_mov = obtener_historial_completo(l_ver, a_ver)
                if not df_mov.empty:
                    if 'fecha_mov' in df_mov.columns:
                        df_mov['fecha_mov'] = pd.to_datetime(df_mov['fecha_mov']).dt.strftime('%d/%m/%Y')
                    
                    # Renombrar para vista bonita
                    df_mov = df_mov.rename(columns={
                        'fecha_mov': 'FECHA', 'tipo_mov': 'TIPO', 'detalle': 'DETALLE', 'usuario': 'USUARIO'
                    })
                    st.dataframe(df_mov, use_container_width=True, hide_index=True)
                else:
                    st.info("Sin movimientos.")
            else:
                st.error("No existe ese legajo.")
        except Exception as e:
            st.error(f"Error: {e}")
