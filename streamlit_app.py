import streamlit as st
import socket
import pandas as pd
from sqlalchemy import text

# ==========================================
# 🚑 PARCHE OBLIGATORIO PARA TU INTERNET
# ==========================================
# Este bloque obliga a Python a ignorar la dirección "2600:..." (IPv6)
# y usar solo la dirección numérica normal (IPv4) para que no falle.
original_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = original_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo
# ==========================================

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema Procuraduria", page_icon="⚖️", layout="wide")

# --- CONEXIÓN A SUPABASE ---
# ttl=0 hace que los datos siempre estén frescos
try:
    conn = st.connection("supabase", type="sql", ttl=0)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- FUNCIONES ---

def buscar_legajos(legajo, anio, expediente, abogado, estado):
    filtros = []
    
    # Consulta base (todo en minúsculas para evitar errores)
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
    
    # Filtros dinámicos
    if legajo: filtros.append(f"AND CAST(legajo_nro AS TEXT) = '{legajo.strip()}'")
    if anio: filtros.append(f"AND CAST(legajo_año AS TEXT) = '{anio.strip()}'")
    if expediente: filtros.append(f"AND exp_primera_instancia ILIKE '%{expediente.strip()}%'")
    if abogado: filtros.append(f"AND nombre_abogado ILIKE '%{abogado.strip()}%'")
    if estado: filtros.append(f"AND estadolegajo_id ILIKE '%{estado.strip()}%'")
    
    query_final = sql_base + " " + " ".join(filtros) + " ORDER BY legajo_año DESC LIMIT 50"
    
    try:
        return conn.query(query_final)
    except Exception as e:
        st.error(f"Error buscando: {e}")
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
        return conn.query(sql)
    except Exception as e:
        st.error(f"Error historial: {e}")
        return pd.DataFrame()

# --- INTERFAZ GRÁFICA ---
st.title("⚖️ Sistema Procuraduría (Nube)")
st.caption("Conectado a Supabase (IPv4 Forzado)")

tab1, tab2 = st.tabs(["🔍 Buscador", "📂 Expediente"])

with tab1:
    c1, c2, c3 = st.columns(3)
    f_leg = c1.text_input("Legajo")
    f_ani = c2.text_input("Año")
    f_abo = c3.text_input("Abogado")
    
    c4, c5 = st.columns(2)
    f_exp = c4.text_input("Expediente")
    f_est = c5.text_input("Estado")
    
    if st.button("Buscar", type="primary"):
        with st.spinner('Buscando...'):
            df = buscar_legajos(f_leg, f_ani, f_exp, f_abo, f_est)
        
        if not df.empty:
            st.success(f"Encontrados: {len(df)}")
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No se encontraron resultados.")

with tab2:
    c1, c2, c3 = st.columns([1, 1, 1])
    l_ver = c1.text_input("Ver Legajo N°", key="v_l")
    a_ver = c2.text_input("Del Año", key="v_a")
    
    with c3:
        st.write("")
        st.write("")
        btn = st.button("Cargar Datos", type="primary")
    
    if btn and l_ver and a_ver:
        q = f"SELECT * FROM legajos WHERE CAST(legajo_nro AS TEXT)='{l_ver}' AND CAST(legajo_año AS TEXT)='{a_ver}' LIMIT 1"
        try:
            df_cab = conn.query(q)
            if not df_cab.empty:
                row = df_cab.iloc[0]
                st.divider()
                st.subheader(f"Expediente {l_ver}-{a_ver}")
                st.info(f"Materia: {row.get('nombre_materia','')} | Estado: {row.get('estadolegajo_id','')}")
                st.write(f"**Abogado:** {row.get('nombre_abogado','')}")
                st.write(f"**Resumen:** {row.get('estado_actual_resumen','')}")
                
                st.markdown("### Movimientos")
                df_mov = obtener_movimientos(l_ver, a_ver)
                if not df_mov.empty:
                     # Arreglo de fecha visual
                    if 'fecha_mov' in df_mov.columns:
                        df_mov['fecha_mov'] = pd.to_datetime(df_mov['fecha_mov']).dt.strftime('%d/%m/%Y')
                    st.dataframe(df_mov, use_container_width=True)
                else:
                    st.info("Sin movimientos.")
            else:
                st.error("No existe ese legajo.")
        except Exception as e:
            st.error(f"Error: {e}")
