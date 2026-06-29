import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
import plotly.express as px
import os
from dotenv import load_dotenv

# Configuración inicial de la página (Minimalista e Industrial)
st.set_page_config(page_title="IIoT Telemetry Panel", page_icon="⚙️", layout="wide")

# Cargar variables de entorno (tu pass.env)
load_dotenv("pass.env")

# --- CONEXIÓN A BASE DE DATOS ---
@st.cache_resource(ttl=60) # Cachea la conexión por 60 seg para no saturar Supabase
def init_connection():
    return psycopg2.connect(
        host="aws-1-sa-east-1.pooler.supabase.com",
        port=6543,
        database="postgres",
        user="postgres.bmuchkgxvcggummezhhh",
        password=os.getenv("DB_PASSWORD"),
        sslmode="require"
    )

@st.cache_data(ttl=10) # Refresca los datos cada 10 segundos
def get_latest_data():
    conn = init_connection()
    # Traemos el último registro de cada máquina
    query = """
    SELECT DISTINCT ON (machine_name) 
        machine_name, timestamp, pressure_bar, temperature_c, run_hours, current_amps
    FROM historical_telemetry
    ORDER BY machine_name, timestamp DESC;
    """
    df = pd.read_sql(query, conn)
    return df

@st.cache_data(ttl=60)
def get_historical_data(machine):
    conn = init_connection()
    # Traemos los últimos 500 registros de la máquina seleccionada
    query = f"""
    SELECT timestamp, pressure_bar, temperature_c, current_amps
    FROM historical_telemetry
    WHERE machine_name = '{machine}'
    ORDER BY timestamp DESC
    LIMIT 500;
    """
    df = pd.read_sql(query, conn)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.sort_values('timestamp')

# --- COMPONENTES VISUALES ---
def draw_gauge(value, title, max_val, color):
    """Genera un Gauge industrial minimalista con Plotly"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        title = {'text': title, 'font': {'size': 18, 'color': 'white'}},
        number = {'font': {'size': 36, 'color': 'white'}},
        gauge = {
            'axis': {'range': [None, max_val], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20), paper_bgcolor="rgba(0,0,0,0)")
    return fig

# --- INTERFAZ PRINCIPAL ---
st.title("🏭 Plant Asset Monitoring | Real-Time Telemetry")
st.markdown("---")

# Pestañas de navegación
tab1, tab2 = st.tabs(["🟢 Live Monitoring", "📈 Histórico de Tendencias"])

with tab1:
    st.subheader("Estado Actual de Equipos")
    df_latest = get_latest_data()
    
    if not df_latest.empty:
        # Creamos una columna para cada máquina
        cols = st.columns(len(df_latest))
        
        for index, row in df_latest.iterrows():
            with cols[index]:
                st.markdown(f"### {row['machine_name']}")
                st.caption(f"Última actualización: {row['timestamp']}")
                
                # Fila interna para los Gauges (Presión y Temp)
                gauge_col1, gauge_col2 = st.columns(2)
                with gauge_col1:
                    st.plotly_chart(draw_gauge(row['pressure_bar'], "Presión (Bar)", 15, "#00CC96"), use_container_width=True)
                with gauge_col2:
                    st.plotly_chart(draw_gauge(row['temperature_c'], "Temp (°C)", 100, "#EF553B"), use_container_width=True)
                
                # Fila interna para métricas de texto plano (minimalista)
                st.metric(label="Corriente Actual (A)", value=f"{row['current_amps']} A")
                st.metric(label="Horas de Marcha", value=f"{row['run_hours']} h")
                st.markdown("---")
    else:
        st.warning("No hay datos recientes disponibles en Supabase.")

with tab2:
    st.subheader("Análisis Histórico")
    df_latest_names = get_latest_data()
    
    if not df_latest_names.empty:
        machine_list = df_latest_names['machine_name'].tolist()
        selected_machine = st.selectbox("Seleccione un equipo para analizar:", machine_list)
        
        df_hist = get_historical_data(selected_machine)
        
        if not df_hist.empty:
            # Gráfico de Temperatura
            fig_temp = px.line(df_hist, x='timestamp', y='temperature_c', title=f"Evolución Térmica - {selected_machine}")
            fig_temp.update_traces(line_color='#EF553B')
            st.plotly_chart(fig_temp, use_container_width=True)
            
            # Gráfico de Presión
            fig_pres = px.line(df_hist, x='timestamp', y='pressure_bar', title=f"Evolución de Presión - {selected_machine}")
            fig_pres.update_traces(line_color='#00CC96')
            st.plotly_chart(fig_pres, use_container_width=True)
        else:
            st.info("No hay suficientes datos históricos para este equipo.")