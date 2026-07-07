import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import plotly.express as px
import os
from dotenv import load_dotenv

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (Debe ser lo primero en ejecutarse)
# ==============================================================================
st.set_page_config(page_title="Industrial Telemetry Pipeline", page_icon="🏭", layout="wide")

# ==============================================================================
# 2. CONTROL DE RUTAS ABSOLUTAS Y CARGA DE ENTORNO
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ENV = os.path.join(BASE_DIR, "pass.env")
load_dotenv(RUTA_ENV)

# ==============================================================================
# 3. CONEXIÓN OPTIMIZADA A BASE DE DATOS (Con freno de seguridad)
# ==============================================================================
@st.cache_resource(ttl=60)
def init_connection():
    # Buscamos la URL completa que usa tu configuración de Supabase
    db_url = os.getenv("DATABASE_URL")
  
    # Freno de mano preventivo por si pasa algo
    if not db_url:
        st.error("⚠️ **Error de Credenciales:** Python leyó el archivo `pass.env` pero NO encontró la variable `DATABASE_URL` adentro.")
        st.info(f"Ruta del archivo verificado: `{RUTA_ENV}`")
        st.stop() 

    # psycopg2 se conecta directo usando el string completo sin separar campos
    return psycopg2.connect(db_url)


    #port = int(os.getenv("DB_PORT", "6543"))
    #database = os.getenv("DB_NAME")
    #user = os.getenv("DB_USER")
    #password = os.getenv("DB_PASSWORD")
    #sslmode = os.getenv("DB_SSLMODE", "require")

    

# ==============================================================================
# 4. FUNCIONES DE EXTRACCIÓN DE DATOS (Queries optimizadas e insensibles a mayúsculas)
# ==============================================================================
@st.cache_data(ttl=5)
def get_latest_data():
    conn = init_connection()
    # Usamos UPPER() para que agrupe "Sullair_Compressor" y "SULLAIR_COMPRESSOR" como uno solo
    query = """
    SELECT DISTINCT ON (UPPER(TRIM(machine_name))) 
        UPPER(TRIM(machine_name)) as machine_name, timestamp, pressure_bar, temperature_c, run_hours, current_amps
    FROM historical_telemetry
    ORDER BY UPPER(TRIM(machine_name)), timestamp DESC;
    """
    return pd.read_sql(query, conn)

@st.cache_data(ttl=15)
def get_historical_data(machine):
    conn = init_connection()
    # Modificamos el WHERE para que la búsqueda en el historial no falle por tipografía
    query = """
    SELECT timestamp, pressure_bar, temperature_c, current_amps
    FROM historical_telemetry
    WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
    ORDER BY timestamp DESC
    LIMIT 300;
    """
    df = pd.read_sql(query, conn, params=(machine,))
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
    return df

# ==============================================================================
# 5. COMPONENTES VISUALES (Diseño de Manómetros)
# ==============================================================================
def draw_gauge(value, title, max_val, color, unit):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"<b>{title}</b>", 'font': {'size': 15, 'color': '#1E293B'}, 'align': 'center'},
        number = {'font': {'size': 24, 'color': '#0F172A'}, 'suffix': f" {unit}"},
        gauge = {
            'axis': {'range': [0, max_val], 'tickwidth': 1, 'tickcolor': "#475569", 'tickfont': {'size': 10}},
            'bar': {'color': color},
            'bgcolor': "#E2E8F0",
            'borderwidth': 0
        }
    ))
    fig.update_layout(
        height=150, 
        margin=dict(l=30, r=30, t=50, b=10), 
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)"
    )
    return fig

# ==============================================================================
# 6. INTERFAZ DE USUARIO (Streamlit Layout)
# ==============================================================================
st.title("🏭 Multi-Asset Telemetry Pipeline")
st.caption("Monitoreo de estado y análisis de tendencias para activos industriales")
st.markdown("---")

tab1, tab2 = st.tabs(["🟢 Monitoreo en Vivo", "📈 Historial de Tendencias"])

# --- TAB 1: MONITOREO EN VIVO ---
with tab1:
    df_latest = get_latest_data()
    
    if not df_latest.empty:
        for index, row in df_latest.iterrows():
            with st.container(border=True):
                
                # 🔌 LÓGICA DE PROCESO: Si consume más de 2 Amperes, el activo está operando
                if row['current_amps'] > 2.0:
                    status_badge = """
                    <span style='background-color: #DCFCE7; color: #15803D; padding: 8px 16px; 
                    border-radius: 8px; font-weight: bold; font-size: 18px; border: 2px solid #BBF7D0;'>
                        🟢 ENCENDIDO
                    </span>
                    """
                else:
                    status_badge = """
                    <span style='background-color: #FEE2E2; color: #B91C1C; padding: 8px 16px; 
                    border-radius: 8px; font-weight: bold; font-size: 18px; border: 2px solid #FCA5A5;'>
                        🔴 APAGADO
                    </span>
                    """
                
                # 🗂️ ENCABEZADO: Dividimos en columnas para colocar el nombre y el cartel alineados
                col_header_title, col_header_status = st.columns([3, 1])
                
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_name']}")
                
                with col_header_status:
                    # Renderizamos el cartel flotado a la derecha
                    st.markdown(f"<div style='text-align: right; margin-top: 12px;'>{status_badge}</div>", unsafe_allow_html=True)
                
                # 📊 CUADRÍCULA DE MEDIDORES (Tu lógica original intacta)
                col_press, col_temp, col_amps, col_hours = st.columns(4)
                
                with col_press:
                    st.plotly_chart(
                        draw_gauge(row['pressure_bar'], "Presión", 15, "#00CC96", "Bar"), 
                        use_container_width=True, 
                        key=f"live_p_{row['machine_name']}"
                    )
                with col_temp:
                    st.plotly_chart(
                        draw_gauge(row['temperature_c'], "Temperatura", 100, "#EF553B", "°C"), 
                        use_container_width=True, 
                        key=f"live_t_{row['machine_name']}"
                    )
                with col_amps:
                    st.markdown("<div style='min-height:25px;'></div>", unsafe_allow_html=True)
                    st.metric(label="⚡ Corriente Motor", value=f"{row['current_amps']} A")
                with col_hours:
                    st.markdown("<div style='min-height:25px;'></div>", unsafe_allow_html=True)
                    st.metric(label="⏱️ Horas de Marcha", value=f"{row['run_hours']} h")
                
                st.markdown(f"<p style='color:#64748B; font-size:12px; margin:0;'>Última actualización: {row['timestamp']}</p>", unsafe_allow_html=True)
    else:
        st.warning("No se encontraron activos transmitiendo en vivo.")

        
# --- TAB 2: HISTORIAL DE TENDENCIAS ---
with tab2:
    df_latest_names = get_latest_data()
    
    if not df_latest_names.empty:
        machine_list = df_latest_names['machine_name'].tolist()
        selected_machine = st.selectbox("Seleccione el activo a analizar:", machine_list, key="select_history_asset")
        
        df_hist = get_historical_data(selected_machine)
        
        if not df_hist.empty:
            st.markdown(f"#### Historial analítico para: **{selected_machine}** ({len(df_hist)} registros cargados)")
            
            # --- GRÁFICO 1: TEMPERATURA ---
            fig_temp = px.line(df_hist, x='timestamp', y='temperature_c', title="📊 Evolución Térmica del Activo", markers=True)
            fig_temp.update_traces(line_color='#EF553B', marker=dict(size=5, opacity=0.8))
            fig_temp.update_layout(
                hovermode="x unified",
                margin=dict(l=40, r=20, t=50, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#F8FAFC",
                xaxis=dict(showgrid=True, gridcolor='#E2E8F0', title="Línea de Tiempo"),
                yaxis=dict(showgrid=True, gridcolor='#E2E8F0', title="Temperatura (°C)")
            )
            st.plotly_chart(fig_temp, use_container_width=True, key=f"chart_h_temp_{selected_machine}")
            
            # --- GRÁFICO 2: PRESIÓN ---
            fig_pres = px.line(df_hist, x='timestamp', y='pressure_bar', title="📊 Comportamiento de Presión Dinámica", markers=True)
            fig_pres.update_traces(line_color='#00CC96', marker=dict(size=5, opacity=0.8))
            fig_pres.update_layout(
                hovermode="x unified",
                margin=dict(l=40, r=20, t=50, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#F8FAFC",
                xaxis=dict(showgrid=True, gridcolor='#E2E8F0', title="Línea de Tiempo"),
                yaxis=dict(showgrid=True, gridcolor='#E2E8F0', title="Presión (Bar)")
            )
            st.plotly_chart(fig_pres, use_container_width=True, key=f"chart_h_pres_{selected_machine}")
            
        else:
            st.info(f"El activo {selected_machine} no registra datos históricos almacenados.")