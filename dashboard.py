import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from dotenv import load_dotenv

### UMBRALES DE ALERTA CRÍTICA (Se pueden ajustar según la planta)
umbral_temp = 85.0  # °C
umbral_pressure = 10.0  # Bar
umbral_current_OFF = (
    2.0  # Amperios (Si baja de este valor, se considera que el motor está apagado)
)

# ORDEN VISUAL DE LA PLANTA (Primero compresores, al final Chiller)
ORDEN_PLANTA = ["AERCOM_22P", "SULLAIR_COMPRESSOR", "CHILLER_TRANE"]

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (Debe ser lo primero en ejecutarse)
# ==============================================================================
st.set_page_config(page_title="Monitoreo industrial ", page_icon="🏭", layout="wide")

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
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error(
            "⚠️ **Error de Credenciales:** Python leyó el archivo `pass.env` pero NO encontró la variable `DATABASE_URL` adentro."
        )
        st.info(f"Ruta del archivo verificado: `{RUTA_ENV}`")
        st.stop()
    return psycopg2.connect(db_url)


# ==============================================================================
# 4. FUNCIONES DE EXTRACCIÓN DE DATOS (Queries optimizadas e insensibles a mayúsculas)
# ==============================================================================
@st.cache_data(ttl=5)
def get_latest_data():
    conn = init_connection()
    query = """
    SELECT DISTINCT ON (UPPER(TRIM(machine_name))) 
        UPPER(TRIM(machine_name)) as machine_name, timestamp, pressure_bar, temperature_c, run_hours, current_amps
    FROM historical_telemetry
    ORDER BY UPPER(TRIM(machine_name)), timestamp DESC;
    """
    df = pd.read_sql(query, conn)

    if not df.empty:
        # Forzamos el orden exacto deseado para la visualización
        df["machine_name"] = pd.Categorical(
            df["machine_name"], categories=ORDEN_PLANTA, ordered=True
        )
        df = df.sort_values("machine_name").reset_index(drop=True)
        df["machine_name"] = df["machine_name"].astype(str)

    return df


@st.cache_data(ttl=15)
def get_historical_data(machine):
    conn = init_connection()
    query = """
    SELECT timestamp, pressure_bar, temperature_c, current_amps
    FROM historical_telemetry
    WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
    ORDER BY timestamp DESC
    LIMIT 300;
    """
    df = pd.read_sql(query, conn, params=(machine,))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
    return df


# ==============================================================================
# 5. COMPONENTES VISUALES (Diseño de Manómetros)
# ==============================================================================
def draw_gauge(value, title, max_val, color, unit):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": f"<b>{title}</b>",
                "font": {"size": 15, "color": "#1E293B"},
                "align": "center",
            },
            number={"font": {"size": 24, "color": "#0F172A"}, "suffix": f" {unit}"},
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": "#475569",
                    "tickfont": {"size": 10},
                },
                "bar": {"color": color},
                "bgcolor": "#E2E8F0",
                "borderwidth": 0,
            },
        )
    )
    fig.update_layout(
        height=150,
        margin=dict(l=30, r=30, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ==============================================================================
# 6. FRAGMENTO DE MONITOREO EN VIVO (Auto-refresco eficiente cada 10 segundos)
# ==============================================================================
@st.fragment(run_every=10)
def render_live_monitoring():
    df_latest = get_latest_data()

    TIMEOUT_DESCONEXION = 30

    if not df_latest.empty:
        for index, row in df_latest.iterrows():
            with st.container(border=True):

                # 🕒 1. CÁLCULO DE TIEMPO TRANSCURRIDO
                last_update = pd.to_datetime(row["timestamp"])
                now = (
                    pd.Timestamp.now(tz=last_update.tz)
                    if last_update.tzinfo is not None
                    else pd.Timestamp.now()
                )
                segundos_sin_datos = (now - last_update).total_seconds()

                # 🧹 Sanitización defensiva contra valores None / NULL
                amps = row["current_amps"] if pd.notna(row["current_amps"]) else None
                temp = row["temperature_c"] if pd.notna(row["temperature_c"]) else None
                press = row["pressure_bar"] if pd.notna(row["pressure_bar"]) else None
                hours = row["run_hours"] if pd.notna(row["run_hours"]) else None

                # 🔌 2. LÓGICA DE ESTADO OPERATIVO (3 ESTADOS)
                # Si transcurrieron +30s O si los datos vienen vacíos (None) por desconexión
                if segundos_sin_datos > TIMEOUT_DESCONEXION or amps is None:
                    is_online = False
                    status_badge = """
                    <span style='background-color: #FEF3C7; color: #D97706; padding: 8px 16px; 
                    border-radius: 8px; font-weight: bold; font-size: 18px; border: 2px solid #FCD34D;'>
                        ⚠️ SIN RECEPCIÓN
                    </span>
                    """
                elif amps > 2.0:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #DCFCE7; color: #15803D; padding: 8px 16px; 
                    border-radius: 8px; font-weight: bold; font-size: 18px; border: 2px solid #BBF7D0;'>
                        🟢 ENCENDIDO
                    </span>
                    """
                else:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #FEE2E2; color: #B91C1C; padding: 8px 16px; 
                    border-radius: 8px; font-weight: bold; font-size: 18px; border: 2px solid #FCA5A5;'>
                        🔴 APAGADO
                    </span>
                    """

                # 🗂️ ENCABEZADO: Nombre de máquina y Estado operativo
                col_header_title, col_header_status = st.columns([3, 1])
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_name']}")
                with col_header_status:
                    st.markdown(
                        f"<div style='text-align: right; margin-top: 12px;'>{status_badge}</div>",
                        unsafe_allow_html=True,
                    )

                # 🚨 3. BANNERS DE ADVERTENCIA Y ALERTAS
                if not is_online:
                    st.warning(
                        "⚠️ **Pérdida de Comunicación:** No se reciben telemetrías válidas de este activo."
                    )
                else:
                    alert_messages = []
                    if temp is not None and temp > umbral_temp:
                        alert_messages.append(
                            f"Alta Temperatura Detectada: {temp} °C (Umbral: >{umbral_temp}°C)"
                        )
                    if press is not None and press > umbral_pressure:
                        alert_messages.append(
                            f"Alta Presión Detectada: {press} Bar (Umbral: >{umbral_pressure} Bar)"
                        )
                    if amps is not None and amps < umbral_current_OFF:
                        alert_messages.append(
                            f"Baja Corriente Detectada: {amps} A (Umbral: <{umbral_current_OFF} A)"
                        )

                    if alert_messages:
                        for alert in alert_messages:
                            st.markdown(
                                f"""
                            <div class="industrial-alert-pulse">
                                ⚠️ <strong>¡ALERTA DE PLANTA!</strong> {alert}
                            </div>
                            """,
                                unsafe_allow_html=True,
                            )

                        st.markdown(
                            """
                        <style>
                        @keyframes industrial-pulse {
                            0% { background-color: #FEE2E2; border-color: #EF4444; color: #991B1B; }
                            50% { background-color: #FCA5A5; border-color: #DC2626; color: #7F1D1D; }
                            100% { background-color: #FEE2E2; border-color: #EF4444; color: #991B1B; }
                        }
                        .industrial-alert-pulse {
                            animation: industrial-pulse 1.2s infinite;
                            padding: 12px 16px;
                            border: 2px solid #EF4444;
                            border-radius: 8px;
                            margin-bottom: 10px;
                            font-weight: bold;
                            font-size: 15px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                        }
                        </style>
                        """,
                            unsafe_allow_html=True,
                        )

                # 📊 4. CUADRÍCULA DE MEDIDORES (Valores por defecto si no hay datos)
                col_press, col_temp, col_amps, col_hours = st.columns(4)

                with col_press:
                    st.plotly_chart(
                        draw_gauge(
                            press if press is not None else 0.0,
                            "Presión",
                            15,
                            "#00CC96",
                            "Bar",
                        ),
                        use_container_width=True,
                        key=f"live_p_{row['machine_name']}",
                    )
                with col_temp:
                    st.plotly_chart(
                        draw_gauge(
                            temp if temp is not None else 0.0,
                            "Temperatura",
                            100,
                            "#EF553B",
                            "°C",
                        ),
                        use_container_width=True,
                        key=f"live_t_{row['machine_name']}",
                    )
                with col_amps:
                    st.markdown(
                        "<div style='min-height:25px;'></div>", unsafe_allow_html=True
                    )
                    st.metric(
                        label="⚡ Corriente Motor",
                        value=f"{amps} A" if amps is not None else "---",
                    )
                with col_hours:
                    st.markdown(
                        "<div style='min-height:25px;'></div>", unsafe_allow_html=True
                    )
                    st.metric(
                        label="⏱️ Horas de Marcha",
                        value=f"{hours} h" if hours is not None else "---",
                    )

                st.markdown(
                    f"<p style='color:#64748B; font-size:12px; margin:0;'>Última actualización registrada: {row['timestamp']}</p>",
                    unsafe_allow_html=True,
                )
    else:
        st.warning("No se encontraron activos transmitiendo en vivo.")


# ==============================================================================
# 7. INTERFAZ DE USUARIO PRINCIPAL (Streamlit Layout)
# ==============================================================================
st.title("🏭 Multi-Asset Telemetry Pipeline")
st.caption("Monitoreo de estado y análisis de tendencias para activos industriales")
st.markdown("---")

tab1, tab2 = st.tabs(["🟢 Monitoreo en Vivo", "📈 Historial de Tendencias"])

# --- TAB 1: MONITOREO EN VIVO ---
with tab1:
    render_live_monitoring()

# --- TAB 2: HISTORIAL DE TENDENCIAS ---
with tab2:
    df_latest_names = get_latest_data()

    if not df_latest_names.empty:
        machine_list = df_latest_names["machine_name"].tolist()
        selected_machine = st.selectbox(
            "Seleccione el activo a analizar:", machine_list, key="select_history_asset"
        )

        df_hist = get_historical_data(selected_machine)

        if not df_hist.empty:
            st.markdown(
                f"#### Historial analítico para: **{selected_machine}** ({len(df_hist)} registros cargados)"
            )

            # --- GRÁFICO 1: TEMPERATURA ---
            fig_temp = px.line(
                df_hist,
                x="timestamp",
                y="temperature_c",
                title="📊 Evolución Térmica del Activo",
                markers=True,
            )
            fig_temp.update_traces(
                line_color="#EF553B", marker=dict(size=5, opacity=0.8)
            )
            fig_temp.update_layout(
                hovermode="x unified",
                margin=dict(l=40, r=20, t=50, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#F8FAFC",
                xaxis=dict(showgrid=True, gridcolor="#E2E8F0", title="Línea de Tiempo"),
                yaxis=dict(
                    showgrid=True, gridcolor="#E2E8F0", title="Temperatura (°C)"
                ),
            )
            st.plotly_chart(
                fig_temp,
                use_container_width=True,
                key=f"chart_h_temp_{selected_machine}",
            )

            # --- GRÁFICO 2: PRESIÓN ---
            fig_pres = px.line(
                df_hist,
                x="timestamp",
                y="pressure_bar",
                title="📊 Comportamiento de Presión Dinámica",
                markers=True,
            )
            fig_pres.update_traces(
                line_color="#00CC96", marker=dict(size=5, opacity=0.8)
            )
            fig_pres.update_layout(
                hovermode="x unified",
                margin=dict(l=40, r=20, t=50, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#F8FAFC",
                xaxis=dict(showgrid=True, gridcolor="#E2E8F0", title="Línea de Tiempo"),
                yaxis=dict(showgrid=True, gridcolor="#E2E8F0", title="Presión (Bar)"),
            )
            st.plotly_chart(
                fig_pres,
                use_container_width=True,
                key=f"chart_h_pres_{selected_machine}",
            )

        else:
            st.info(
                f"El activo {selected_machine} no registra datos históricos almacenados."
            )
