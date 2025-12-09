import streamlit as st
import pandas as pd
from sqlalchemy import text

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Sistema Procuraduria Cloud", page_icon="☁️", layout="wide")

# --- CONEXIÓN ---
# Busca automáticamente en .streamlit/secrets.toml
conn = st.connection("supabase", type="sql")

# --- FUNCIONES ---

def buscar_legajos(legajo, anio, expediente, abogado, estado):
    filtros = []
    
    # QUERY BASE (Todo en minúsculas, sin comillas)
    sql_base = """
    SELECT 
        legajo_nro as legajo, 
        legajo_año as anio, 
        exp_primera_instancia as expediente, 
        nombre_abogado as abogado, 
        estadolegajo_id as estado,
        nombre_materia as materia,
        demandante as demandante,
        estado_actual_resumen as resumen
    FROM legajos
    WHERE 1=1
    """
    
    # FILTROS DINÁMICOS
    if legajo: 
        # Convertimos a texto para buscar, por si acaso es un ID numérico
        filtros.append(f"AND CAST(legajo_nro AS TEXT) = '{legajo.strip()}'")
        
    if anio: 
        filtros.append(f"AND CAST(legajo_año AS TEXT) = '{anio.strip()}'")
        
    if expediente: 
        # ILIKE ignora mayúsculas/minúsculas (ej: busca 'juan' y encuentra 'JUAN')
        filtros.append(f"AND exp_primera_instancia ILIKE '%{expediente.strip()}%'")
        
    if abogado: 
        filtros.append(f"AND nombre_abogado ILIKE '%{abogado.strip()}%'")

    if estado:
        filtros.append(f"AND estadolegajo_id ILIKE '%{estado.strip()}%'")
    
    # Unimos todo
    query_final = sql_base + " " + " ".join(filtros) + " ORDER BY legajo_año DESC LIMIT 50"
    
    try:
        # ttl=0 para que los datos estén siempre frescos
        return conn.query(query_final, ttl=0)
    except Exception as e:
        st.error(f"Error en búsqueda: {e}")
        return pd.DataFrame()

def obtener_movimientos(nro, anio):
    sql = f"""
    SELECT fecha_mov, tipo_mov, detalle, usuario
    FROM movimiento_legajos
    WHERE CAST(legajo_mov AS TEXT) = '{nro}' 
      AND CAST(legajo_año_mov AS TEXT) = '{anio}'
    ORDER BY fecha_mov DESC
    """
    try:
        return conn.query(sql, ttl=0)
    except Exception as e:
        st.error(f"Error en historial: {e}")
        return pd.DataFrame()

# --- INTERFAZ GRÁFICA ---
st.title("☁️ Sistema Procuraduría (Cloud)")
st.caption("Conectado a Supabase 🟢")

tab1, tab2 = st.tabs(["🔍 Búsqueda General", "📂 Expediente Detallado"])

# --- PESTAÑA 1: BUSCADOR ---
with tab1:
    c1, c2, c3 = st.columns(3)
    f_leg = c1.text_input("Legajo")
    f_ani = c2.text_input("Año")
    f_abo = c3.text_input("Abogado")
    
    c4, c5 = st.columns(2)
    f_exp = c4.text_input("Expediente")
    f_est = c5.text_input("Estado")
    
    if st.button("Buscar Expedientes", type="primary"):
        if f_leg or f_ani or f_abo or f_exp or f_est:
            with st.spinner('Consultando nube...'):
                df = buscar_legajos(f_leg, f_ani, f_exp, f_abo, f_est)
            
            if not df.empty:
                st.success(f"Encontrados: {len(df)}")
                st.dataframe(df, use_container_width=True)
            else:
                st.warning("No se encontraron resultados con esos filtros.")
        else:
            st.info("Escribe al menos un filtro para buscar.")

# --- PESTAÑA 2: DETALLE ---
with tab2:
    col_a, col_b, col_btn = st.columns([1, 1, 1])
    l_ver = col_a.text_input("Ver Legajo N°", key="v_leg")
    a_ver = col_b.text_input("Del Año", key="v_ani")
    
    with col_btn:
        st.write("")
        st.write("")
        btn_ver = st.button("Cargar Historial", type="primary")
    
    if btn_ver and l_ver and a_ver:
        # 1. Cargar Cabecera
        q_cab = f"SELECT * FROM legajos WHERE CAST(legajo_nro AS TEXT)='{l_ver}' AND CAST(legajo_año AS TEXT)='{a_ver}' LIMIT 1"
        try:
            df_cab = conn.query(q_cab, ttl=0)
            
            if not df_cab.empty:
                row = df_cab.iloc[0]
                
                # Diseño de Ficha
                st.markdown("---")
                st.subheader(f"📁 Expediente {l_ver}-{a_ver}")
                
                c_info1, c_info2 = st.columns(2)
                c_info1.info(f"**Materia:** {row['nombre_materia']}")
                c_info2.warning(f"**Estado:** {row['estadolegajo_id']}")
                
                st.write(f"**Demandante:** {row['demandante']}")
                st.write(f"**Inculpado:** {row['inculpado']}")
                st.write(f"**Abogado Responsable:** {row['nombre_abogado']}")
                
                with st.expander("Ver Resumen / Observaciones", expanded=True):
                    st.write(row['estado_actual_resumen'])
                
                # 2. Cargar Movimientos
                st.markdown("### 📜 Historial de Movimientos")
                df_mov = obtener_movimientos(l_ver, a_ver)
                
                if not df_mov.empty:
                    # Ajuste visual de fecha si viene como objeto
                    # (Si Supabase lo manda como string, esto no es necesario, pero previene errores)
                    if 'fecha_mov' in df_mov.columns:
                        df_mov['fecha_mov'] = pd.to_datetime(df_mov['fecha_mov']).dt.strftime('%d/%m/%Y')
                        
                    st.dataframe(df_mov, use_container_width=True, hide_index=True)
                else:
                    st.info("Este legajo no registra movimientos.")
                    
            else:
                st.error(f"El Legajo {l_ver}-{a_ver} no existe en la base de datos.")
        except Exception as e:
            st.error(f"Error consultando base de datos: {e}")