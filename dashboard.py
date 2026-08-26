import json
import os
from datetime import datetime, timedelta
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
        "max_press": 7.5,  # bar (Alerta de alta presión)
        "min_press": 6.5,
    },
    "SULLAIR SE1507NEW": {
        "max_temp": 95.0,
        "min_temp": 65.0,
        "max_press": 7.5,
        "min_press": 6.5,
    },
    "CHILLER TRANE CGAX030": {
        "max_temp": 12.0,  # °C (Agua caliente / bajo rendimiento)
        "min_temp": 4.5,  # °C (Alerta anti-congelamiento)
        "max_press": 27.0,  # bar (Alta presión de condensación)
        "min_press": 6.5,  # bar (Baja presión / falta de gas)
    },
}

SUBSTATE_LABELS = {
    "STOPPED": "DETENIDO",
    "OFF / DETENIDO": "DETENIDO",
    "READY (LISTO)": "LISTO",
    "ENABLED": "HABILITADO",
    "AUTOENABLED": "AUTO HABILITADO",
    "STARTING (ARRANCANDO)": "ARRANCANDO",
    "UNLOADED (EN VACÍO)": "EN VACÍO",
    "LOADING (CARGANDO)": "CARGANDO",
    "FULL LOAD (PLENA CARGA)": "PLENA CARGA",
    "MODULATING (MODULANDO)": "MODULANDO",
    "STOPPING (PARANDO)": "DETENIENDO",
}


def translate_substate(value):
    return SUBSTATE_LABELS.get(str(value).strip().upper(), str(value))


def get_preventive_alerts(alert_key: str) -> dict:
    thresholds = PREVENTIVE_ALERTS[alert_key]
    return {
        "max_temp": thresholds["max_temp"],
        "min_temp": thresholds["min_temp"],
        "max_press": thresholds["max_press"],
        "min_press": thresholds["min_press"],
    }


# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (¡Restaurada!)
# ==============================================================================
st.set_page_config(
    page_title="Beniplast | Monitoreo Industrial", page_icon="B", layout="wide"
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
        box-sizing: border-box;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }}

    [data-testid="stColumn"] {{
        min-width: 0 !important;
        box-sizing: border-box;
    }}
    
    /* Métricas */
    [data-testid="stMetricValue"] {{
        font-size: 2rem !important;
        font-weight: 700;
        color: {metric_color} !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: {text_muted} !important;
        font-weight: 600;
        font-size: 1.05rem !important;
    }}
    [data-baseweb="tab"] {{
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }}
    .substate-label {{
        color: {text_muted};
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 10px;
    }}
    .substate-value {{
        color: {metric_color};
        font-size: 1rem;
        font-weight: 700;
        line-height: 1.2;
        overflow-wrap: anywhere;
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
    .industrial-alert-compact {{
        color: #FFFFFF !important;
        background-color: rgba(248, 113, 113, 0.12) !important;
        border-left: 3px solid #F87171 !important;
        padding: 5px 10px;
        margin: 3px 0;
        font-size: 13px;
    }}
    .maintenance-badge {{
        display: inline-block;
        color: #FFFFFF !important;
        background-color: #991B1B !important;
        border: 1px solid #F87171 !important;
        border-radius: 14px;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: 700;
        animation: blink 1.2s step-start infinite;
        cursor: help;
    }}
    .industrial-alert-failure {{
        color: #FFFFFF !important;
        background-color: #991B1B !important;
        border: 2px solid #F87171 !important;
        padding: 14px 16px;
        border-radius: 8px;
        margin: 5px 0 10px;
        font-size: 18px;
        font-weight: 700;
    }}
    .status-badge {{
        display: inline-block;
        padding: 8px 18px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 16px;
        color: #FFFFFF !important;
        text-align: center;
    }}
    .status-on {{
        background-color: #16A34A;
        border: 1px solid #4ADE80;
    }}
    .status-off, .status-offline {{
        background-color: #DC2626;
        border: 1px solid #F87171;
        animation: blink 1.2s step-start infinite;
    }}
    .equipment-offline {{ opacity: 0.35; }}
    .js-plotly-plot .plotly .main-svg {{
        overflow: visible !important;
    }}
    div[data-testid="stPlotlyChart"] {{
        width: 100% !important;
        min-width: 0 !important;
    }}
    @keyframes blink {{
        50% {{ opacity: 0.35; }}
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


def read_postgres_dataframe(query, conn, params=None):
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    return pd.DataFrame.from_records(rows, columns=columns)


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
                        df_dbg = read_postgres_dataframe(query_dbg, conn_dbg)
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
    WITH latest_reading AS (
        SELECT DISTINCT ON (UPPER(TRIM(machine_name)))
            UPPER(TRIM(machine_name)) AS machine_key,
            timestamp, pressure_bar, temperature_c, run_hours
        FROM historical_telemetry
        ORDER BY UPPER(TRIM(machine_name)), timestamp DESC
    )
    SELECT
        latest_reading.machine_key,
        latest_reading.timestamp,
        latest_reading.pressure_bar,
        latest_reading.temperature_c,
        latest_reading.run_hours,
        (
            SELECT pressure_sink_bar
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.pressure_sink_bar IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS pressure_sink_bar,
        (
            SELECT operating_state
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.operating_state IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS operating_state,
        (
            SELECT shutdown_code
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.shutdown_code IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS shutdown_code,
        (
            SELECT warnings
            FROM historical_telemetry h
            WHERE UPPER(TRIM(h.machine_name)) = latest_reading.machine_key
              AND h.warnings IS NOT NULL
            ORDER BY h.timestamp DESC
            LIMIT 1
        ) AS warnings
    FROM latest_reading;
    """
    df = read_postgres_dataframe(query, conn)

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


def get_historical_data(machine, start_date, end_date):
    conn = init_connection()
    query = """
        SELECT timestamp, pressure_bar, pressure_sink_bar, temperature_c,
            operating_state, warnings
    FROM historical_telemetry
    WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
      AND timestamp >= %s
      AND timestamp < %s
    ORDER BY timestamp ASC;
    """
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    df = read_postgres_dataframe(
        query, conn, params=(machine, start_datetime, end_datetime)
    )
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
            # Reservamos espacio suficiente arriba para separar el titulo del arco
            domain={"x": [0.06, 0.94], "y": [0, 0.68]},
            number={
                "font": {"size": 34, "color": font_color},
                "suffix": f" {unit}",
            },
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont": {"size": 19, "color": font_color},
                },
                "bar": {"color": color},
                "bgcolor": track_color,
                "borderwidth": 0,
            },
        )
    )

    # El titulo queda fuera del area del gauge para evitar superposiciones al ampliar.
    fig.add_annotation(
        text=f"<b>{title}</b>",
        x=0.5,
        y=0.96,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=34, color=font_color),
        xanchor="center",
        yanchor="bottom",
    )

    fig.update_layout(
        height=300,
        margin=dict(l=24, r=24, t=52, b=12),
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def draw_temperature_gauge(value, font_color, track_color):
    fig = draw_gauge(
        value, "Temperatura", 110, "#16A34A", "°C", font_color, track_color
    )
    fig.update_traces(
        gauge={
            "steps": [
                {"range": [0, 95], "color": "#166534"},
                {"range": [95, 103], "color": "#A16207"},
                {"range": [103, 110], "color": "#991B1B"},
            ],
            "bar": {"color": "#F8FAFC"},
        }
    )
    return fig


def draw_pressure_gauge(value, font_color, track_color):
    fig = draw_gauge(
        value, "Presión Línea", 15, "#00E676", "Bar", font_color, track_color
    )
    fig.update_traces(
        gauge={
            "steps": [
                {"range": [0, 6.5], "color": "#3F3F46"},
                {"range": [6.5, 7.5], "color": "#166534"},
                {"range": [7.5, 15], "color": "#991B1B"},
            ],
            "bar": {"color": "#F8FAFC"},
        }
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
            with st.container(border=True):
                # 🕒 Tiempo transcurrido
                last_update = pd.to_datetime(row["timestamp"])
                if last_update.tzinfo is None:
                    last_update = last_update.tz_localize(DATA_TIMEZONE)
                now = pd.Timestamp.now(tz="UTC")
                segundos_sin_datos = (
                    now - last_update.astimezone("UTC")
                ).total_seconds()

                # 🧹 Sanitización defensiva
                temp = (
                    float(row["temperature_c"])
                    if pd.notna(row["temperature_c"])
                    else None
                )
                press = (
                    float(row["pressure_bar"])
                    if pd.notna(row["pressure_bar"])
                    else None
                )
                pressure_sink = (
                    float(row["pressure_sink_bar"])
                    if pd.notna(row["pressure_sink_bar"])
                    else None
                )
                hours = row["run_hours"] if pd.notna(row["run_hours"]) else None
                operating_state = (
                    translate_substate(row["operating_state"])
                    if pd.notna(row["operating_state"])
                    else "N/D"
                )
                shutdown_code = (
                    int(row["shutdown_code"])
                    if pd.notna(row["shutdown_code"])
                    else None
                )
                warnings = []
                if pd.notna(row["warnings"]):
                    try:
                        warnings = json.loads(row["warnings"])
                    except (TypeError, json.JSONDecodeError):
                        warnings = [str(row["warnings"])]

                # 🔌 Estado operativo
                if segundos_sin_datos > TIMEOUT_DESCONEXION:
                    status = "SIN CONEXIÓN"
                    status_class = "status-offline"
                elif press is not None and press > 1:
                    status = "ENCENDIDO"
                    status_class = "status-on"
                else:
                    status = "APAGADO"
                    status_class = "status-off"
                is_online = status != "SIN CONEXIÓN"
                status_badge = (
                    f"<span class='status-badge {status_class}'>{status}</span>"
                )

                # 🗂️ ENCABEZADO DE ACTIVO
                col_header_title, col_header_status = st.columns([3, 1])
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_label']}")
                with col_header_status:
                    st.markdown(
                        f"<div style='text-align: right; margin-top: 5px;'>{status_badge}</div>",
                        unsafe_allow_html=True,
                    )

                # Falla de parada: se muestra inmediatamente debajo del estado.
                if shutdown_code not in (None, 0):
                    st.markdown(
                        f"<div class='industrial-alert-failure'>🚨 FALLA DE PARADA: código {shutdown_code}</div>",
                        unsafe_allow_html=True,
                    )

                # 🚨 ALERTAS Y ADVERTENCIAS
                temperature_alert = None
                pressure_alert = None
                maintenance_alerts = []
                if not is_online:
                    st.markdown(
                        "<div class='industrial-alert-compact'>⚠️ Pérdida de comunicación: no se reciben telemetrías válidas.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    alert_key = MACHINE_ALERT_KEY[str(row["machine_key"])]
                    thresholds = get_preventive_alerts(alert_key)
                    if temp is not None:
                        if temp > thresholds["max_temp"]:
                            temperature_alert = f"Alta Temperatura: {temp} °C (Umbral: >{thresholds['max_temp']} °C)"
                        elif temp < thresholds["min_temp"]:
                            temperature_alert = f"Temperatura baja: {temp} °C (Umbral: <{thresholds['min_temp']} °C)"
                    if press is not None:
                        if (
                            thresholds["min_press"] is not None
                            and press < thresholds["min_press"]
                        ):
                            pressure_alert = f"Presión baja: {press} Bar (Umbral: <{thresholds['min_press']} Bar)"
                        elif press > thresholds["max_press"]:
                            pressure_alert = f"Alta Presión: {press} Bar (Umbral: >{thresholds['max_press']} Bar)"
                    maintenance_alerts.extend(
                        warning
                        for warning in warnings
                        if "SIN ADVERTENCIAS" not in warning
                    )
                    if maintenance_alerts:
                        alert_tooltip = "&#10;".join(maintenance_alerts).replace(
                            '"', "&quot;"
                        )
                        st.markdown(
                            f"<span class='maintenance-badge' title=\"{alert_tooltip}\">🔧 ALARMA MANTENIMIENTO</span>",
                            unsafe_allow_html=True,
                        )

                # 📊 CUADRÍCULA DE MEDIDORES Y MÉTRICAS
                col_press, col_temp, col_hours = st.columns(3, gap="small")

                delta_pressure = (
                    pressure_sink - press
                    if pressure_sink is not None and press is not None
                    else None
                )

                with col_press:
                    if is_online:
                        st.plotly_chart(
                            draw_pressure_gauge(
                                press if press is not None else 0.0,
                                text_color,
                                gauge_track,
                            ),
                            width="stretch",
                            config={"responsive": True, "displayModeBar": False},
                            key=f"live_p_{row['machine_key']}",
                        )
                    else:
                        st.metric("Presión Línea", "N/D")
                    if pressure_alert:
                        st.error(pressure_alert, icon="⚠️")

                with col_temp:
                    if is_online:
                        st.plotly_chart(
                            draw_temperature_gauge(
                                temp if temp is not None else 0.0,
                                text_color,
                                gauge_track,
                            ),
                            width="stretch",
                            config={"responsive": True, "displayModeBar": False},
                            key=f"live_t_{row['machine_key']}",
                        )
                    else:
                        st.metric("Temperatura", "N/D")
                    if temperature_alert:
                        st.error(temperature_alert, icon="⚠️")

                with col_hours:
                    col_hours_value, col_delta = st.columns(2, gap="small")
                    with col_hours_value:
                        st.metric(
                            label="⏱️ Horas de Marcha",
                            value=(
                                f"{int(hours):,} h"
                                if is_online and hours is not None
                                else "N/D"
                            ),
                        )
                    with col_delta:
                        delta_label = "ΔP Filtro Separador"
                        if delta_pressure is not None and delta_pressure >= 0.8:
                            delta_label += " ⚠️ Reemplazar Filtro"
                        st.metric(
                            delta_label,
                            (
                                f"{delta_pressure:.1f} bar"
                                if is_online and delta_pressure is not None
                                else "N/D"
                            ),
                        )
                    st.markdown(
                        "<div class='substate-label'>Sub-Estado Modbus</div>"
                        f"<div class='substate-value'>{operating_state if is_online else 'N/D'}</div>",
                        unsafe_allow_html=True,
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
logo_path = os.path.join(BASE_DIR, "logo_grupo_beniplast.png")
header_logo, header_text = st.columns([1, 5], vertical_alignment="center")
with header_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=220)
with header_text:
    st.markdown(
        """
        <div style="border-left: 3px solid #2F81F7; padding-left: 18px;">
            <h1 style="margin: 3px 0 2px; font-size: 2rem; line-height: 0.5;">
                Sistema de Monitoreo Industrial
            </h1>
            <div style="color: #94A3B8; font-size: 1.20rem;">
                Supervisión operativa y análisis de variables críticas
            </div>
            </h1 style="margin: 5px 0 4px; font-size: 2rem; line-height: 1.2;">
            <div style="color: #94A3B8; font-size: 1.20rem;">
                Departamento de Mantenimiento 
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
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

        default_end_date = datetime.now().date()
        default_start_date = default_end_date - timedelta(days=6)
        with st.expander("Configurar período", expanded=False):
            start_date = st.date_input(
                "Fecha inicial",
                value=default_start_date,
                format="DD/MM/YYYY",
                key="history_start_date",
            )
            end_date = st.date_input(
                "Fecha final",
                value=default_end_date,
                format="DD/MM/YYYY",
                key="history_end_date",
            )

        if start_date > end_date:
            st.error("La fecha inicial no puede ser posterior a la fecha final.")
            st.stop()

        df_hist = get_historical_data(selected_machine, start_date, end_date)

        if not df_hist.empty:
            st.markdown(
                f"#### Historial analítico: **{selected_machine}** (`{len(df_hist)} registros`)"
            )
            st.caption(
                f"Período mostrado: {df_hist['timestamp'].min():%d/%m/%Y %H:%M} "
                f"a {df_hist['timestamp'].max():%d/%m/%Y %H:%M}"
            )

            # --- GRÁFICO 1: TEMPERATURA ---
            fig_temp = px.line(
                df_hist,
                x="timestamp",
                y="temperature_c",
                title="📈 Evolución Térmica",
                markers=True,
            )
            fig_temp.update_traces(line_color="#FF5252", line_width=2)
            fig_temp.update_layout(
                template=plotly_theme,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor=card_bg,
                font=dict(color=text_color),
                xaxis=dict(
                    showgrid=True,
                    gridcolor=grid_color,
                    title="",
                    tickformat="%d/%m/%Y",
                    hoverformat="%d/%m/%Y %H:%M",
                ),
                yaxis=dict(
                    showgrid=True, gridcolor=grid_color, title="Temperatura (°C)"
                ),
            )
            st.plotly_chart(
                fig_temp,
                width="stretch",
                key=f"chart_h_temp_{selected_machine}",
            )

            # --- GRÁFICO 2: PRESIÓN ---
            fig_pres = px.line(
                df_hist,
                x="timestamp",
                y="pressure_bar",
                title="📉 Comportamiento de Presión",
                markers=True,
            )
            fig_pres.update_traces(line_color="#00E676", line_width=2)
            fig_pres.update_layout(
                template=plotly_theme,
                hovermode="x unified",
                margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor=card_bg,
                font=dict(color=text_color),
                xaxis=dict(
                    showgrid=True,
                    gridcolor=grid_color,
                    title="",
                    tickformat="%d/%m/%Y",
                    hoverformat="%d/%m/%Y %H:%M",
                ),
                yaxis=dict(showgrid=True, gridcolor=grid_color, title="Presión (Bar)"),
            )
            st.plotly_chart(
                fig_pres,
                width="stretch",
                key=f"chart_h_pres_{selected_machine}",
            )

            vista_tabla = st.selectbox(
                "Vista de la tabla",
                ["Resumen diario", "Mostrar todos los datos"],
                key="history_table_view",
            )

            nombre_activo = MACHINE_DISPLAY_LABEL.get(
                selected_machine, selected_machine
            )
            tabla_detalle = pd.DataFrame(
                {
                    "Fecha completa": df_hist["timestamp"],
                    "Activo": nombre_activo,
                    "Presión": df_hist["pressure_bar"],
                    "Temperatura": df_hist["temperature_c"],
                }
            )

            if vista_tabla == "Resumen diario":
                datos_diarios = df_hist.copy()
                datos_diarios["fecha"] = datos_diarios["timestamp"].dt.date
                datos_diarios["pressure_bar"] = pd.to_numeric(
                    datos_diarios["pressure_bar"], errors="coerce"
                )
                datos_diarios["temperature_c"] = pd.to_numeric(
                    datos_diarios["temperature_c"], errors="coerce"
                )

                promedios = (
                    datos_diarios.groupby("fecha", as_index=False)
                    .agg(
                        Presión=("pressure_bar", "mean"),
                        Temperatura=("temperature_c", "mean"),
                    )
                    .sort_values("fecha")
                )
                promedio_por_fecha = promedios.set_index("fecha")
                datos_diarios["promedio_presion"] = datos_diarios["fecha"].map(
                    promedio_por_fecha["Presión"]
                )
                datos_diarios["promedio_temperatura"] = datos_diarios["fecha"].map(
                    promedio_por_fecha["Temperatura"]
                )

                def porcentaje_desviacion(valor, promedio):
                    if pd.isna(valor) or pd.isna(promedio):
                        return float("nan")
                    if promedio == 0:
                        return 0.0 if valor == 0 else float("inf")
                    return abs(valor - promedio) / abs(promedio) * 100

                datos_diarios["desviacion_presion"] = datos_diarios.apply(
                    lambda fila: porcentaje_desviacion(
                        fila["pressure_bar"], fila["promedio_presion"]
                    ),
                    axis=1,
                )
                datos_diarios["desviacion_temperatura"] = datos_diarios.apply(
                    lambda fila: porcentaje_desviacion(
                        fila["temperature_c"], fila["promedio_temperatura"]
                    ),
                    axis=1,
                )

                filas_resumen = []
                for _, promedio in promedios.iterrows():
                    fecha = promedio["fecha"]
                    filas_resumen.append(
                        {
                            "Fecha completa": fecha.strftime("%d/%m/%Y"),
                            "Activo": nombre_activo,
                            "Presión": promedio["Presión"],
                            "Temperatura": promedio["Temperatura"],
                            "Detalle": "Promedio diario",
                            "Es desviación": False,
                        }
                    )

                    lecturas_con_desviacion = datos_diarios[
                        (datos_diarios["fecha"] == fecha)
                        & (
                            (datos_diarios["desviacion_presion"] >= 20)
                            | (datos_diarios["desviacion_temperatura"] >= 20)
                        )
                    ]
                    for _, lectura in lecturas_con_desviacion.iterrows():
                        desviaciones = []
                        if lectura["desviacion_presion"] >= 20:
                            desviaciones.append(
                                f"presión: {lectura['desviacion_presion']:.0f}%"
                            )
                        if lectura["desviacion_temperatura"] >= 20:
                            desviaciones.append(
                                f"temperatura: {lectura['desviacion_temperatura']:.0f}%"
                            )
                        filas_resumen.append(
                            {
                                "Fecha completa": lectura["timestamp"].strftime(
                                    "%d/%m/%Y %H:%M:%S"
                                ),
                                "Activo": nombre_activo,
                                "Presión": lectura["pressure_bar"],
                                "Temperatura": lectura["temperature_c"],
                                "Detalle": "Desviación del " + " y ".join(desviaciones),
                                "Es desviación": True,
                            }
                        )

                tabla_historial = pd.DataFrame(filas_resumen)
            else:
                tabla_historial = tabla_detalle.assign(
                    Detalle="Lectura registrada", **{"Es desviación": False}
                )

            es_desviacion = tabla_historial.pop("Es desviación")
            tabla_mostrada = tabla_historial.style.apply(
                lambda fila: [
                    (
                        "background-color: #7f1d1d; color: #ffffff"
                        if es_desviacion.loc[fila.name]
                        else ""
                    )
                    for _ in fila
                ],
                axis=1,
            )
            st.dataframe(
                tabla_mostrada,
                width="stretch",
                hide_index=True,
                column_config={
                    "Presión": st.column_config.NumberColumn(
                        "Presión", format="%.1f bar"
                    ),
                    "Temperatura": st.column_config.NumberColumn(
                        "Temperatura", format="%.1f °C"
                    ),
                    "Detalle": st.column_config.TextColumn("Detalle"),
                },
            )

        else:
            st.info(
                f"El activo {selected_machine} no registra datos históricos almacenados."
            )
