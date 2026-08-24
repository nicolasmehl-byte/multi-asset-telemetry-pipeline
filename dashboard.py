import os
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
from dotenv import load_dotenv

### UMBRALES DE ALERTA CRÍTICA (Se pueden ajustar según la planta)
umbral_temp = 95.0  # °C
umbral_pressure = 10.0  # Bar

# ORDEN VISUAL DE LA PLANTA (Primero compresores, al final Chiller)
MACHINE_DISPLAY_LABEL = {
    "AERCOM_22P": "Compresor Aercom",
    "SULLAIR_COMPRESSOR": "Compresor Sullair ",
    "CHILLER_TRANE": "Chiller Trane",
}
MACHINE_ALERT_KEY = {
    "AERCOM_22P": "AERCOM 22P",
    "SULLAIR_COMPRESSOR": "SULLAIR SE1507NEW",
    "CHILLER_TRANE": "CHILLER TRANE CGAX030",
}
ORDEN_PLANTA_KEYS = ["AERCOM_22P", "SULLAIR_COMPRESSOR", "CHILLER_TRANE"]
ORDEN_PLANTA = [MACHINE_DISPLAY_LABEL[key] for key in ORDEN_PLANTA_KEYS]

# COTAS DE ADVERTENCIA PREVENTIVA (ALERTAS PREVIAS A FALLA)
PREVENTIVE_ALERTS = {
    "AERCOM 22P": {
        "max_temp": 95.0,  # °C (Alerta de alta temperatura)
        "min_temp": 65.0,  # °C (Alerta de temperatura baja / condensación)
        "max_press": 10.0,  # bar (Alerta de alta presión)
    },
    "SULLAIR SE1507NEW": {
        "max_temp": 95.0,
        "min_temp": 65.0,
        "max_press": 9.5,
    },
    "CHILLER TRANE CGAX030": {
        "max_temp": 12.0,  # °C (Agua caliente / bajo rendimiento)
        "min_temp": 4.5,  # °C (Alerta anti-congelamiento)
        "max_press": 27.0,  # bar (Alta presión de condensación)
        "min_press": 6.5,  # bar (Baja presión / falta de gas)
    },
}

DEFAULT_PREVENTIVE_ALERTS = {
    "max_temp": 95.0,
    "min_temp": 65.0,
    "max_press": 10.0,
    "min_press": None,
}


def get_preventive_alerts(alert_key: str) -> dict:
    thresholds = PREVENTIVE_ALERTS.get(alert_key, DEFAULT_PREVENTIVE_ALERTS)
    # Garantizar todas las claves están presentes.
    return {
        "max_temp": thresholds.get("max_temp", DEFAULT_PREVENTIVE_ALERTS["max_temp"]),
        "min_temp": thresholds.get("min_temp", DEFAULT_PREVENTIVE_ALERTS["min_temp"]),
        "max_press": thresholds.get(
            "max_press", DEFAULT_PREVENTIVE_ALERTS["max_press"]
        ),
        "min_press": thresholds.get(
            "min_press", DEFAULT_PREVENTIVE_ALERTS["min_press"]
        ),
    }


# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (¡Restaurada!)
# ==============================================================================
st.set_page_config(
    page_title="Monitoreo Industrial Beniplast IIoT", page_icon="🏭", layout="wide"
)

# ==============================================================================
# MODO OSCURO FIJO
# ==============================================================================
tema_seleccionado = "🌙 Oscuro SCADA"
bg_color = "#0E1117"
card_bg = "#161B22"
card_border = "#30363D"
text_color = "#FFFFFF"
text_muted = "#94A3B8"
metric_color = "#58A6FF"
gauge_track = "#21262D"
plotly_theme = "plotly_dark"
grid_color = "#21262D"

# ==============================================================================
# 2. INYECCIÓN DE ESTILOS CSS
# ==============================================================================
st.markdown(
    f"""
    <style>
    /* Fondo principal de la app */
    .stApp {{
        background-color: {bg_color} !important;
    }}
    
    /* Fondo y borde de la barra lateral (Sidebar) */
    [data-testid="stSidebar"] {{
        background-color: {card_bg} !important;
        border-right: 1px solid {card_border} !important;
    }}
    
    /* Color de texto unificado para toda la interfaz (incluyendo el Sidebar) */
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp span, .stApp label {{
        color: {text_color} !important;
    }}
    
    /* Tarjetas de activos en el panel principal */
    [data-testid="stVerticalBlock"] > div[data-testid="stBlock"] {{
        background-color: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }}
    
    /* Métricas */
    [data-testid="stMetricValue"] {{
        font-size: 1.8rem !important;
        font-weight: 700;
        color: {metric_color} !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {text_muted} !important;
        font-weight: 600;
        font-size: 0.9rem !important;
    }}
    .industrial-alert-pulse {{
        color: #FFFFFF !important;
        background-color: rgba(248, 113, 113, 0.18) !important;
        border: 1px solid #F87171 !important;
        padding: 12px 14px;
        border-radius: 10px;
        margin-bottom: 10px;
        font-weight: 600;
    }}
    .industrial-alert-pulse strong {{
        color: #FFFFFF !important;
    }}
    </style>
""",
    unsafe_allow_html=True,
)
# ==============================================================================
# 3. CONTROL DE RUTAS Y ENTORNO
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ENV = os.path.join(BASE_DIR, "pass.env")
# Si pass.env no existe (por ejemplo, en Streamlit Cloud, donde nunca se sube
# por seguridad), load_dotenv simplemente no hace nada y no tira error.
load_dotenv(RUTA_ENV)
DATA_TIMEZONE = ZoneInfo(os.getenv("DATA_TIMEZONE", "America/Argentina/Buenos_Aires"))


def get_database_url():
    """
    Obtiene la cadena de conexión a la base de datos desde Streamlit Cloud o
    desde el entorno local.

    - En Streamlit Cloud: usa st.secrets["DATABASE_URL"] cuando se configuró.
    - En local: usa la variable de entorno cargada desde pass.env.
    """
    try:
        # Acceder a st.secrets puede fallar cuando no existe ningún secrets.toml.
        db_url = st.secrets.get("DATABASE_URL")
    except Exception:
        db_url = None

    if db_url:
        return db_url

    return os.getenv("DATABASE_URL")


@st.cache_resource(ttl=60)
def init_connection():
    db_url = get_database_url()
    if not db_url:
        st.error(
            "⚠️ **Error de Credenciales:** Variable `DATABASE_URL` no encontrada "
            "ni en pass.env ni en Secrets de Streamlit."
        )
        st.stop()
    return psycopg2.connect(db_url)


# ---------------------------------------------------------------------------
# Debug: panel seguro (no muestra credenciales) para verificar origen DB
# Se muestra solo si el usuario marca la casilla en el sidebar.
# ---------------------------------------------------------------------------
def _mask_host_port_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        host = p.hostname or ""
        port = p.port or ""
        if host:
            return f"{host}:{port}"
        return "(unknown)"
    except Exception:
        return "(invalid)"


with st.sidebar:
    with st.expander("🔧 Debug DB (solo admin)", expanded=False):
        show_db_debug = st.checkbox("Mostrar info de conexión (segura)", key="debug_db")
        if show_db_debug:
            db_url = None
            try:
                # Intentamos leer el secret sin lanzar si no existe
                db_url = (
                    st.secrets.get("DATABASE_URL") if hasattr(st, "secrets") else None
                )
            except Exception:
                db_url = None

            if not db_url:
                db_url = os.getenv("DATABASE_URL")

            if not db_url:
                st.warning("DATABASE_URL no configurada en st.secrets ni en pass.env")
            else:
                src = (
                    "st.secrets"
                    if (hasattr(st, "secrets") and st.secrets.get("DATABASE_URL"))
                    else "pass.env / env"
                )
                st.info(f"Fuente: {src}")
                st.write("Host:Port:", _mask_host_port_from_url(db_url))

                # Test de conexión (rápido y no muestra la URL completa)
                try:
                    conn = psycopg2.connect(db_url, connect_timeout=5)
                    conn.close()
                    st.success("Conexión a la base: OK")
                except Exception as e:
                    st.error(
                        f"Conexión fallida: {e.__class__.__name__}: {str(e)[:150]}"
                    )

                # Estado detallado por activo (timestamps y segundos desde última telemetría)
                try:
                    # Ejecutar una consulta mínima inline para evitar depender de
                    # funciones que podrían definirse más abajo en este archivo.
                    # Abrir una conexión nueva para debug (no usar la conexión
                    # cacheada por `init_connection()` ya que esa instancia
                    # podría ser compartida por la app y no debe cerrarse aquí).
                    conn_dbg = None
                    try:
                        conn_dbg = psycopg2.connect(db_url, connect_timeout=5)
                    except Exception as e_conn:
                        st.error(f"No se pudo abrir conexión debug directa: {e_conn}")

                    if conn_dbg is None:
                        st.warning(
                            "No se pudo abrir conexión para obtener estado de activos"
                        )
                    else:
                        query_dbg = """
                        SELECT DISTINCT ON (UPPER(TRIM(machine_name)))
                            UPPER(TRIM(machine_name)) as machine_name, timestamp, pressure_bar
                        FROM historical_telemetry
                        ORDER BY UPPER(TRIM(machine_name)), timestamp DESC;
                        """
                        df_dbg = pd.read_sql(query_dbg, conn_dbg)
                        try:
                            conn_dbg.close()
                        except Exception:
                            pass

                        if df_dbg is None or df_dbg.empty:
                            st.warning(
                                "No hay filas recientes en la tabla historical_telemetry"
                            )
                        else:
                            now_utc = pd.Timestamp.now(tz="UTC")
                            rows = []
                            for _, r in df_dbg.iterrows():
                                ts = (
                                    pd.to_datetime(r["timestamp"])
                                    if pd.notna(r["timestamp"])
                                    else None
                                )
                                if ts is not None and ts.tzinfo is None:
                                    ts = ts.tz_localize(DATA_TIMEZONE)
                                diff_sec = None
                                if ts is not None:
                                    diff_sec = (
                                        now_utc - ts.astimezone("UTC")
                                    ).total_seconds()
                                machine_label = MACHINE_DISPLAY_LABEL.get(
                                    r["machine_name"], r["machine_name"]
                                )
                                rows.append(
                                    {
                                        "machine": machine_label,
                                        "timestamp": str(ts),
                                        "tz": (
                                            str(ts.tzinfo) if ts is not None else None
                                        ),
                                        "pressure_bar": r.get("pressure_bar"),
                                        "seconds_since": diff_sec,
                                    }
                                )
                            st.table(pd.DataFrame(rows))
                except Exception as e:
                    st.error(f"Error al calcular estado por activo: {e}")


# ==============================================================================
# 5. FUNCIONES DE EXTRACCIÓN DE DATOS
# ==============================================================================
@st.cache_data(ttl=5)
def get_latest_data():
    conn = init_connection()
    query = """
    SELECT DISTINCT ON (UPPER(TRIM(machine_name))) 
        UPPER(TRIM(machine_name)) as machine_key, timestamp, pressure_bar, temperature_c, run_hours
    FROM historical_telemetry
    ORDER BY UPPER(TRIM(machine_name)), timestamp DESC;
    """
    df = pd.read_sql(query, conn)

    if not df.empty:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
        df["machine_key"] = pd.Categorical(
            df["machine_key"], categories=ORDEN_PLANTA_KEYS, ordered=True
        )
        df = df.sort_values("machine_key").reset_index(drop=True)
        df["machine_key"] = df["machine_key"].astype(str)
        df["machine_label"] = (
            df["machine_key"].map(MACHINE_DISPLAY_LABEL).fillna(df["machine_key"])
        )
        df["machine_alert_key"] = (
            df["machine_key"].map(MACHINE_ALERT_KEY).fillna(df["machine_key"])
        )

    return df


@st.cache_data(ttl=15)
def get_historical_data(machine):
    conn = init_connection()
    query = """
    SELECT timestamp, pressure_bar, temperature_c
    FROM historical_telemetry
    WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
    ORDER BY timestamp DESC
    LIMIT 300;
    """
    df = pd.read_sql(query, conn, params=(machine,))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
        df = df.sort_values("timestamp")
    return df


# ==============================================================================
# 6. COMPONENTES VISUALES (Manómetros Estilizados)
# ==============================================================================
def draw_gauge(value, title, max_val, color, unit, font_color, track_color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            # Reservamos el 25% superior del lienzo para que el arco no invada el título
            domain={"x": [0, 1], "y": [0, 0.75]},
            number={
                "font": {"size": 25, "color": font_color},
                "suffix": f" {unit}",
            },
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont": {"size": 25, "color": font_color},
                },
                "bar": {"color": color},
                "bgcolor": track_color,
                "borderwidth": 0,
            },
        )
    )

    # Anotación con coordenada fija al lienzo (paper) para alinear todos los títulos
    fig.add_annotation(
        text=f"<b>{title}</b>",
        x=0.5,
        y=1.0,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=20, color=font_color),
        xanchor="center",
        yanchor="bottom",
    )

    fig.update_layout(
        height=150,
        margin=dict(l=20, r=20, t=25, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


# ==============================================================================
# 7. FRAGMENTO DE MONITOREO EN VIVO
# ==============================================================================
@st.fragment(run_every=10)
def render_live_monitoring():
    df_latest = get_latest_data()
    # Tiempo (segundos) que consideramos para marcar pérdida de comunicación.
    # Valor por defecto aumentado a 200s; puede sobreescribirse desde el entorno
    # con la variable TIMEOUT_DESCONEXION.
    TIMEOUT_DESCONEXION = int(os.getenv("TIMEOUT_DESCONEXION", "200"))

    if not df_latest.empty:
        for index, row in df_latest.iterrows():
            with st.container():
                # 🕒 Tiempo transcurrido
                last_update = pd.to_datetime(row["timestamp"])
                if last_update.tzinfo is None:
                    last_update = last_update.tz_localize(DATA_TIMEZONE)
                now = pd.Timestamp.now(tz="UTC")
                segundos_sin_datos = (
                    now - last_update.astimezone("UTC")
                ).total_seconds()

                # 🧹 Sanitización defensiva
                temp = row["temperature_c"] if pd.notna(row["temperature_c"]) else None
                press = row["pressure_bar"] if pd.notna(row["pressure_bar"]) else None
                hours = row["run_hours"] if pd.notna(row["run_hours"]) else None

                # 🔌 Estado operativo
                if segundos_sin_datos > TIMEOUT_DESCONEXION:
                    is_online = False
                    status_badge = """
                    <span style='background-color: #3D2D00; color: #FFFFFF; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #D97706;'>
                        ⚠️ SIN CONEXIÓN
                    </span>
                    """
                elif press is not None and press > 1:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #0D3321; color: #FFFFFF; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #059669;'>
                        🟢 ENCENDIDO
                    </span>
                    """
                else:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #1F2937; color: #FFFFFF; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #6B7280;'>
                        ⚪ APAGADO
                    </span>
                    """

                # 🗂️ ENCABEZADO DE ACTIVO
                col_header_title, col_header_status = st.columns([3, 1])
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_label']}")
                with col_header_status:
                    st.markdown(
                        f"<div style='text-align: right; margin-top: 5px;'>{status_badge}</div>",
                        unsafe_allow_html=True,
                    )

                # 🚨 BANNERS DE ALERTAS
                if not is_online:
                    st.warning(
                        "⚠️ **Pérdida de Comunicación:** No se reciben telemetrías válidas del dispositivo."
                    )
                else:
                    alert_messages = []
                    thresholds = get_preventive_alerts(row["machine_alert_key"])
                    if temp is not None:
                        if temp > thresholds["max_temp"]:
                            alert_messages.append(
                                f"Alta Temperatura: {temp} °C (Umbral: >{thresholds['max_temp']} °C)"
                            )
                        elif temp < thresholds["min_temp"]:
                            alert_messages.append(
                                f"Temperatura baja: {temp} °C (Umbral: <{thresholds['min_temp']} °C)"
                            )
                    if press is not None:
                        if (
                            thresholds["min_press"] is not None
                            and press < thresholds["min_press"]
                        ):
                            alert_messages.append(
                                f"Presión baja: {press} Bar (Umbral: <{thresholds['min_press']} Bar)"
                            )
                        elif press > thresholds["max_press"]:
                            alert_messages.append(
                                f"Alta Presión: {press} Bar (Umbral: >{thresholds['max_press']} Bar)"
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

                # 📊 CUADRÍCULA DE MEDIDORES Y MÉTRICAS
                col_press, col_temp, col_hours = st.columns(3)

                with col_press:
                    st.plotly_chart(
                        draw_gauge(
                            press if press is not None else 0.0,
                            "Presión",
                            15,
                            "#00E676",
                            "Bar",
                            text_color,
                            gauge_track,
                        ),
                        use_container_width=True,
                        key=f"live_p_{row['machine_key']}",
                    )

                with col_temp:
                    st.plotly_chart(
                        draw_gauge(
                            temp if temp is not None else 0.0,
                            "Temperatura",
                            100,
                            "#FF5252",
                            "°C",
                            text_color,
                            gauge_track,
                        ),
                        use_container_width=True,
                        key=f"live_t_{row['machine_key']}",
                    )

                with col_hours:
                    st.markdown(
                        "<div style='min-height:15px;'></div>",
                        unsafe_allow_html=True,
                    )
                    st.metric(
                        label="⏱️ Horas de Marcha",
                        value=f"{int(hours):,} h" if hours is not None else "---",
                    )

                st.markdown(
                    f"<p style='color:{text_muted}; font-size:11px; margin:0; text-align:right;'>Última telemetría: {row['timestamp']}</p>",
                    unsafe_allow_html=True,
                )
    else:
        st.warning("No se encontraron activos transmitiendo en vivo.")


# ==============================================================================
# 8. INTERFAZ DE USUARIO PRINCIPAL
# ==============================================================================
st.title("🏭 Monitoreo de equipos auxiliares en tiempo real")
st.caption("Sistema SCADA IIoT")
st.markdown("---")

tab1, tab2 = st.tabs(["🟢 Monitoreo en Vivo", "📈 Historial de Tendencias"])

# --- TAB 1: MONITOREO EN VIVO ---
with tab1:
    render_live_monitoring()

# --- TAB 2: HISTORIAL DE TENDENCIAS ---
with tab2:
    df_latest_names = get_latest_data()

    if not df_latest_names.empty:
        machine_list = df_latest_names["machine_key"].tolist()
        selected_machine = st.selectbox(
            "Seleccione el activo a analizar:",
            machine_list,
            format_func=lambda x: MACHINE_DISPLAY_LABEL.get(x, x),
            key="select_history_asset",
        )

        df_hist = get_historical_data(selected_machine)

        if not df_hist.empty:
            st.markdown(
                f"#### Historial analítico: **{selected_machine}** (`{len(df_hist)} registros`)"
            )

            # --- GRÁFICO 1: TEMPERATURA ---
            fig_temp = px.line(
                df_hist,
                x="timestamp",
                y="temperature_c",
                title="📈 Evolución Térmica",
                markers=False,
            )
            fig_temp.update_traces(line_color="#FF5252", line_width=2)
            fig_temp.update_layout(
                template=plotly_theme,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor=card_bg,
                font=dict(color=text_color),
                xaxis=dict(showgrid=True, gridcolor=grid_color, title=""),
                yaxis=dict(
                    showgrid=True, gridcolor=grid_color, title="Temperatura (°C)"
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
                title="📉 Comportamiento de Presión",
                markers=False,
            )
            fig_pres.update_traces(line_color="#00E676", line_width=2)
            fig_pres.update_layout(
                template=plotly_theme,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor=card_bg,
                font=dict(color=text_color),
                xaxis=dict(showgrid=True, gridcolor=grid_color, title=""),
                yaxis=dict(showgrid=True, gridcolor=grid_color, title="Presión (Bar)"),
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
