# dashboard_v2.py
"""
Sistema de Monitoreo Industrial - Grupo Beniplast (v2)

Qué cambia respecto a dashboard.py:
- Código reorganizado en funciones (load_css, render_sidebar, check_alerts,
  render_kpis, render_charts) en vez de un bloque largo secuencial. Más fácil
  de leer y de tocar sin romper otras partes.
- Nuevo panel de KPIs globales de planta arriba de todo (equipos operativos,
  alarmas activas, estado general del sistema, eficiencia de planta 24hs).
- Lógica de alertas centralizada en una sola función (check_alerts), en vez
  de tenerla repetida/mezclada dentro del loop de renderizado.
- Gráfico de historial combinado: Temperatura y Presión en el mismo panel
  con doble eje Y, en vez de dos gráficos separados (más fácil de comparar
  patrones entre las dos variables).
- Sidebar con: badge de estado general del sistema, toggle para silenciar
  TODAS las alarmas sonoras de una vez, y panel de debug de conexión.
- Descarga de datos de historial a CSV.
"""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import psycopg2
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from plotly.subplots import make_subplots

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA Y CONSTANTES DE PLANTA
# ==============================================================================
st.set_page_config(
    page_title="Beniplast | Monitoreo Industrial", page_icon="🏭", layout="wide"
)

MACHINE_DISPLAY_LABEL = {
    "AERCOM_22P": "Compresor Aercom",
    "SULLAIR_COMPRESSOR": "Compresor Sullair",
    "CHILLER_TRANE": "Chiller Trane",
}
MACHINE_ALERT_KEY = {
    "AERCOM_22P": "AERCOM 22P",
    "SULLAIR_COMPRESSOR": "SULLAIR SE1507NEW",
    "CHILLER_TRANE": "CHILLER TRANE CGAX030",
}
ORDEN_PLANTA_KEYS = ["AERCOM_22P", "SULLAIR_COMPRESSOR", "CHILLER_TRANE"]

DEFAULT_PREVENTIVE_ALERTS = {
    "AERCOM 22P": {
        "max_temp": 95.0,
        "min_temp": 65.0,
        "max_press": 7.5,
        "min_press": 6.5,
    },
    "SULLAIR SE1507NEW": {
        "max_temp": 95.0,
        "min_temp": 65.0,
        "max_press": 7.5,
        "min_press": 6.5,
    },
    "CHILLER TRANE CGAX030": {
        "max_temp": 12.0,
        "min_temp": 4.5,
        "max_press": 27.0,
        "min_press": 6.5,
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


# ==============================================================================
# 2. ENTORNO Y CONEXIÓN A LA BASE DE DATOS
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "pass.env"))
DATA_TIMEZONE = ZoneInfo(os.getenv("DATA_TIMEZONE", "America/Argentina/Buenos_Aires"))


def get_database_url():
    """DATABASE_URL desde Streamlit Secrets (nube) o desde pass.env (local)."""
    try:
        db_url = st.secrets.get("DATABASE_URL")
    except Exception:
        db_url = None
    return db_url or os.getenv("DATABASE_URL")


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


def read_postgres_dataframe(query, params=None):
    conn = init_connection()
    with conn.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
    return pd.DataFrame.from_records(rows, columns=columns)


# ==============================================================================
# 3. ESTILOS (load_css)
# ==============================================================================
def load_css():
    """Inyecta el tema oscuro industrial y los estilos de las tarjetas KPI/alarma."""
    st.markdown(
        """
        <style>
        .stApp { background-color: #0E1117 !important; }
        [data-testid="stSidebar"] {
            background-color: #161B22 !important;
            border-right: 1px solid #30363D !important;
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp span, .stApp label {
            color: #FFFFFF !important;
        }
        [data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 700; color: #58A6FF !important; }
        [data-testid="stMetricLabel"] { color: #94A3B8 !important; font-weight: 600; font-size: 0.9rem !important; }
        [data-baseweb="tab"] { font-size: 1.1rem !important; font-weight: 700 !important; }

        /* --- Tarjetas KPI de planta (panel superior) --- */
        .kpi-card {
            background-color: #1f293d;
            border: 1px solid #30363D;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }
        .kpi-card .kpi-label { color: #94A3B8; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
        .kpi-card .kpi-value { font-size: 1.8rem; font-weight: 800; margin-top: 4px; }
        .kpi-card .kpi-delta { font-size: 0.8rem; margin-top: 4px; }
        .kpi-delta-good { color: #4ADE80; }
        .kpi-delta-bad { color: #F87171; }
        .kpi-delta-neutral { color: #94A3B8; }

        /* --- Badge de estado general del sistema --- */
        .system-status-badge {
            display: inline-block; padding: 8px 18px; border-radius: 20px;
            font-weight: 800; font-size: 1rem; letter-spacing: 0.5px;
        }
        .status-normal { background-color: #14532D; color: #4ADE80; border: 1px solid #4ADE80; }
        .status-advertencia { background-color: #78350F; color: #FBBF24; border: 1px solid #FBBF24; animation: blink 1.4s step-start infinite; }
        .status-peligro { background-color: #7F1D1D; color: #FCA5A5; border: 1px solid #F87171; animation: blink 0.8s step-start infinite; }

        .status-badge { display: inline-block; padding: 6px 14px; border-radius: 16px; font-weight: 700; font-size: 14px; color: #FFFFFF !important; text-align: center; }
        .status-on { background-color: #16A34A; border: 1px solid #4ADE80; }
        .status-off, .status-offline { background-color: #DC2626; border: 1px solid #F87171; animation: blink 1.2s step-start infinite; }

        .industrial-alert-pulse { color: #FFFFFF !important; background-color: rgba(248,113,113,0.18) !important; border: 1px solid #F87171 !important; padding: 10px 12px; border-radius: 8px; margin-bottom: 8px; font-weight: 600; }
        .industrial-alert-compact { color: #FFFFFF !important; background-color: rgba(248,113,113,0.12) !important; border-left: 3px solid #F87171 !important; padding: 5px 10px; margin: 3px 0; font-size: 13px; }
        .maintenance-badge { display: inline-block; color: #FFFFFF !important; background-color: #991B1B !important; border: 1px solid #F87171 !important; border-radius: 12px; padding: 4px 8px; font-size: 11px; font-weight: 700; animation: blink 1.2s step-start infinite; }
        .industrial-alert-failure { color: #FFFFFF !important; background-color: #991B1B !important; border: 2px solid #F87171 !important; padding: 12px 14px; border-radius: 8px; margin: 5px 0 10px; font-size: 16px; font-weight: 700; }
        .substate-label { color: #94A3B8; font-size: 0.75rem; font-weight: 600; margin-top: 10px; }
        .substate-value { color: #58A6FF; font-size: 0.95rem; font-weight: 700; line-height: 1.2; overflow-wrap: anywhere; }
        @keyframes blink { 50% { opacity: 0.35; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label, value, delta_text=None, delta_kind="neutral"):
    """Renderiza una tarjeta KPI simple con valor grande y un delta opcional."""
    delta_html = (
        f"<div class='kpi-delta kpi-delta-{delta_kind}'>{delta_text}</div>"
        if delta_text
        else ""
    )
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 4. ALARMA SONORA (WEB AUDIO API)
# ==============================================================================
if "acknowledged_alarms" not in st.session_state:
    st.session_state["acknowledged_alarms"] = set()


@st.fragment(run_every=10)
def play_alarm_sound():
    """Genera un tono de alarma directo en el navegador con la Web Audio API."""
    js_code = """
    <script>
    if (!window.alarmInterval) {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        window.alarmInterval = setInterval(() => {
            if (audioCtx.state === 'suspended') { audioCtx.resume(); }
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        }, 700);
    }
    </script>
    """
    components.html(js_code, height=0, width=0)


def stop_alarm_sound():
    js_code = """
    <script>
    if (window.alarmInterval) {
        clearInterval(window.alarmInterval);
        window.alarmInterval = null;
    }
    </script>
    """
    components.html(js_code, height=0, width=0)


# ==============================================================================
# 5. LECTURA DE DATOS DESDE SUPABASE / POSTGRES
# ==============================================================================
@st.cache_data(ttl=5)
def get_latest_data():
    query = """
    WITH latest_reading AS (
        SELECT DISTINCT ON (UPPER(TRIM(machine_name)))
            UPPER(TRIM(machine_name)) AS machine_key,
            timestamp, pressure_bar, temperature_c, run_hours
        FROM historical_telemetry
        ORDER BY UPPER(TRIM(machine_name)), timestamp DESC
    )
    SELECT
        lr.machine_key, lr.timestamp, lr.pressure_bar, lr.temperature_c, lr.run_hours,
        (SELECT pressure_sink_bar FROM historical_telemetry h
         WHERE UPPER(TRIM(h.machine_name)) = lr.machine_key AND h.pressure_sink_bar IS NOT NULL
         ORDER BY h.timestamp DESC LIMIT 1) AS pressure_sink_bar,
        (SELECT operating_state FROM historical_telemetry h
         WHERE UPPER(TRIM(h.machine_name)) = lr.machine_key AND h.operating_state IS NOT NULL
         ORDER BY h.timestamp DESC LIMIT 1) AS operating_state,
        (SELECT shutdown_code FROM historical_telemetry h
         WHERE UPPER(TRIM(h.machine_name)) = lr.machine_key AND h.shutdown_code IS NOT NULL
         ORDER BY h.timestamp DESC LIMIT 1) AS shutdown_code,
        (SELECT warnings FROM historical_telemetry h
         WHERE UPPER(TRIM(h.machine_name)) = lr.machine_key AND h.warnings IS NOT NULL
         ORDER BY h.timestamp DESC LIMIT 1) AS warnings
    FROM latest_reading lr;
    """
    df = read_postgres_dataframe(query)
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
    query = """
        SELECT timestamp, pressure_bar, pressure_sink_bar, temperature_c, operating_state, warnings
        FROM historical_telemetry
        WHERE UPPER(TRIM(machine_name)) = UPPER(TRIM(%s))
          AND timestamp >= %s AND timestamp < %s
        ORDER BY timestamp ASC;
    """
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    df = read_postgres_dataframe(query, params=(machine, start_dt, end_dt))
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
        df = df.sort_values("timestamp")
    return df


@st.cache_data(ttl=60)
def get_plant_uptime_24h():
    query = """
        SELECT
            COUNT(*) FILTER (WHERE pressure_bar > 1) * 100.0 / NULLIF(COUNT(*), 0) AS uptime_pct
        FROM historical_telemetry
        WHERE timestamp >= NOW() - INTERVAL '24 hours';
    """
    df = read_postgres_dataframe(query)
    if df.empty or pd.isna(df.loc[0, "uptime_pct"]):
        return None
    return float(df.loc[0, "uptime_pct"])


# ==============================================================================
# 6. LÓGICA DE ALERTAS CENTRALIZADA
# ==============================================================================
def check_alerts(row, thresholds_by_key):
    timeout_desconexion = int(os.getenv("TIMEOUT_DESCONEXION", "200"))

    last_update = pd.to_datetime(row["timestamp"])
    if last_update.tzinfo is None:
        last_update = last_update.tz_localize(DATA_TIMEZONE)
    now = pd.Timestamp.now(tz="UTC")
    segundos_sin_datos = (now - last_update.astimezone("UTC")).total_seconds()

    temp = float(row["temperature_c"]) if pd.notna(row["temperature_c"]) else None
    press = float(row["pressure_bar"]) if pd.notna(row["pressure_bar"]) else None
    shutdown_code = (
        int(row["shutdown_code"]) if pd.notna(row["shutdown_code"]) else None
    )

    warnings = []
    if pd.notna(row["warnings"]):
        try:
            warnings = json.loads(row["warnings"])
        except (TypeError, json.JSONDecodeError):
            warnings = [str(row["warnings"])]
    maintenance_alerts = [w for w in warnings if "SIN ADVERTENCIAS" not in w]

    online = segundos_sin_datos <= timeout_desconexion

    temp_alert = None
    press_alert = None
    if online:
        alert_key = MACHINE_ALERT_KEY.get(str(row["machine_key"]))
        thresholds = thresholds_by_key.get(alert_key, {})

        if temp is not None:
            if thresholds.get("max_temp") is not None and temp > thresholds["max_temp"]:
                temp_alert = (
                    f"Alta Temp: {temp} °C (Umbral: >{thresholds['max_temp']} °C)"
                )
            elif (
                thresholds.get("min_temp") is not None and temp < thresholds["min_temp"]
            ):
                temp_alert = (
                    f"Baja Temp: {temp} °C (Umbral: <{thresholds['min_temp']} °C)"
                )

        if press is not None:
            if (
                thresholds.get("min_press") is not None
                and press < thresholds["min_press"]
            ):
                press_alert = f"Baja Presión: {press} Bar (Umbral: <{thresholds['min_press']} Bar)"
            elif (
                thresholds.get("max_press") is not None
                and press > thresholds["max_press"]
            ):
                press_alert = f"Alta Presión: {press} Bar (Umbral: >{thresholds['max_press']} Bar)"

    shutdown = shutdown_code not in (None, 0)

    if not online:
        level = "ADVERTENCIA"
    elif shutdown or temp_alert or press_alert:
        level = "PELIGRO"
    elif maintenance_alerts:
        level = "ADVERTENCIA"
    else:
        level = "NORMAL"

    return {
        "online": online,
        "level": level,
        "temp": temp,
        "press": press,
        "temp_alert": temp_alert,
        "press_alert": press_alert,
        "maintenance_alerts": maintenance_alerts,
        "shutdown": shutdown,
        "shutdown_code": shutdown_code,
    }


def compute_global_status(alerts_by_machine):
    levels = [a["level"] for a in alerts_by_machine.values()]
    if "PELIGRO" in levels:
        return "PELIGRO"
    if "ADVERTENCIA" in levels:
        return "ADVERTENCIA"
    return "NORMAL"


# ==============================================================================
# 7. SIDEBAR (render_sidebar)
# ==============================================================================
def render_sidebar(df_latest, alerts_by_machine):
    with st.sidebar:
        st.markdown("### 🏭 Estado del Sistema")
        estado_global = (
            compute_global_status(alerts_by_machine) if alerts_by_machine else "NORMAL"
        )
        badge_class = {
            "NORMAL": "status-normal",
            "ADVERTENCIA": "status-advertencia",
            "PELIGRO": "status-peligro",
        }[estado_global]
        st.markdown(
            f"<span class='system-status-badge {badge_class}'>{estado_global}</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"Actualizado: {datetime.now(DATA_TIMEZONE):%d/%m/%Y %H:%M:%S}")
        st.markdown("---")

        st.markdown("### 🔊 Alarmas Sonoras")
        sonido_activo = st.toggle("Sonido de alarma activado", value=True)
        if not sonido_activo:
            st.caption("Las alarmas visuales se muestran; solo se silencia el audio.")
        st.markdown("---")

        st.markdown("### ⚙️ Umbrales de Alerta")
        thresholds_by_key = {}
        with st.expander("Ajustar umbrales", expanded=False):
            for alert_key, defaults in DEFAULT_PREVENTIVE_ALERTS.items():
                st.markdown(f"**{alert_key}**")
                max_temp = st.slider(
                    "Temp. máx (°C)",
                    0.0,
                    150.0,
                    defaults["max_temp"],
                    key=f"maxtemp_{alert_key}",
                )
                max_press = st.slider(
                    "Presión máx (bar)",
                    0.0,
                    40.0,
                    defaults["max_press"],
                    key=f"maxpress_{alert_key}",
                )
                thresholds_by_key[alert_key] = {
                    "max_temp": max_temp,
                    "min_temp": defaults["min_temp"],
                    "max_press": max_press,
                    "min_press": defaults["min_press"],
                }
        for alert_key, defaults in DEFAULT_PREVENTIVE_ALERTS.items():
            thresholds_by_key.setdefault(alert_key, defaults)

        st.markdown("---")
        with st.expander("🔧 Debug DB", expanded=False):
            _render_debug_panel()

    return {"sonido_activo": sonido_activo, "thresholds_by_key": thresholds_by_key}


def _mask_host_port_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse

        p = urlparse(url)
        return f"{p.hostname}:{p.port}" if p.hostname else "(unknown)"
    except Exception:
        return "(invalid)"


def _render_debug_panel():
    show_db_debug = st.checkbox("Mostrar info de conexión", key="debug_db")
    if not show_db_debug:
        return
    db_url = get_database_url()
    if not db_url:
        st.warning("DATABASE_URL no configurada")
        return
    st.info(
        "Fuente: st.secrets"
        if st.secrets.get("DATABASE_URL")
        else "Fuente: pass.env / env"
    )
    st.write("Host:Port:", _mask_host_port_from_url(db_url))
    try:
        conn = psycopg2.connect(db_url, connect_timeout=5)
        conn.close()
        st.success("Conexión BD: OK")
    except Exception as e:
        st.error(f"Conexión fallida: {e.__class__.__name__}: {str(e)[:150]}")


# ==============================================================================
# 8. GAUGES / MANÓMETROS (PLOTLY)
# ==============================================================================
def draw_gauge(value, title, max_val, color, unit, font_color, track_color):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0.06, 0.94], "y": [0, 0.68]},
            number={"font": {"size": 30, "color": font_color}, "suffix": f" {unit}"},
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont": {"size": 14, "color": font_color},
                },
                "bar": {"color": color},
                "bgcolor": track_color,
                "borderwidth": 0,
            },
        )
    )
    fig.add_annotation(
        text=f"<b>{title}</b>",
        x=0.5,
        y=0.96,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=20, color=font_color),
        xanchor="center",
        yanchor="bottom",
    )
    fig.update_layout(
        height=240,
        margin=dict(l=20, r=20, t=40, b=10),
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def draw_temperature_gauge(value):
    fig = draw_gauge(value, "Temperatura", 110, "#16A34A", "°C", "#FFFFFF", "#21262D")
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


def draw_pressure_gauge(value):
    fig = draw_gauge(value, "Presión Línea", 15, "#00E676", "Bar", "#FFFFFF", "#21262D")
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
# 9. KPIs GLOBALES DE PLANTA
# ==============================================================================
def render_kpis(df_latest, alerts_by_machine):
    equipos_online = sum(1 for a in alerts_by_machine.values() if a["online"])
    total_equipos = len(alerts_by_machine)
    alarmas_activas = sum(
        1 for a in alerts_by_machine.values() if a["level"] == "PELIGRO"
    )
    estado_global = compute_global_status(alerts_by_machine)
    uptime_pct = get_plant_uptime_24h()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card(
            "Estado General",
            estado_global,
            delta_kind="good" if estado_global == "NORMAL" else "bad",
        )
    with col2:
        kpi_card(
            "Equipos Operativos",
            f"{equipos_online}/{total_equipos}",
            delta_kind="good" if equipos_online == total_equipos else "bad",
        )
    with col3:
        kpi_card(
            "Alarmas Activas",
            str(alarmas_activas),
            delta_kind="good" if alarmas_activas == 0 else "bad",
        )
    with col4:
        uptime_label = f"{uptime_pct:.1f}%" if uptime_pct is not None else "N/D"
        kpi_card("Eficiencia Planta (24h)", uptime_label, delta_kind="neutral")


# ==============================================================================
# 10. GRÁFICO COMBINADO DE HISTORIAL
# ==============================================================================
def render_charts(df_hist, machine_label):
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=df_hist["timestamp"],
            y=df_hist["temperature_c"],
            name="Temperatura (°C)",
            line=dict(color="#FF5252", width=2),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=df_hist["timestamp"],
            y=df_hist["pressure_bar"],
            name="Presión (Bar)",
            line=dict(color="#00E676", width=2),
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title=f"📈 Temperatura vs Presión — {machine_label}",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#161B22",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(
        title_text="Temperatura (°C)", secondary_y=False, gridcolor="#21262D"
    )
    fig.update_yaxes(title_text="Presión (Bar)", secondary_y=True, showgrid=False)
    fig.update_xaxes(
        tickformat="%d/%m/%Y", hoverformat="%d/%m/%Y %H:%M", gridcolor="#21262D"
    )
    st.plotly_chart(fig, use_container_width=True, key=f"chart_combo_{machine_label}")

    # Desglose de advertencias registradas
    warnings_flat = []
    for w in df_hist["warnings"].dropna():
        try:
            items = json.loads(w)
        except (TypeError, json.JSONDecodeError):
            items = [str(w)]
        warnings_flat.extend(i for i in items if "SIN ADVERTENCIAS" not in i)

    if warnings_flat:
        counts = pd.Series(warnings_flat).value_counts().reset_index()
        counts.columns = ["Advertencia", "Ocurrencias"]
        fig_bar = go.Figure(
            go.Bar(
                x=counts["Advertencia"], y=counts["Ocurrencias"], marker_color="#F87171"
            )
        )
        fig_bar.update_layout(
            title="🔧 Desglose de advertencias en el período",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#161B22",
            margin=dict(l=20, r=20, t=50, b=20),
        )
        st.plotly_chart(
            fig_bar, use_container_width=True, key=f"chart_warnings_{machine_label}"
        )
    else:
        st.caption("Sin advertencias registradas en el período seleccionado.")


# ==============================================================================
# 11. MONITOREO EN VIVO POR EQUIPO
# ==============================================================================
def render_live_monitoring(thresholds_by_key, sonido_activo):
    df_latest = get_latest_data()
    if df_latest.empty:
        st.warning("No se encontraron activos transmitiendo en vivo.")
        return

    alerts_by_machine = {
        row["machine_key"]: check_alerts(row, thresholds_by_key)
        for _, row in df_latest.iterrows()
    }

    render_kpis(df_latest, alerts_by_machine)
    st.markdown("---")

    for _, row in df_latest.iterrows():
        alert = alerts_by_machine[row["machine_key"]]
        with st.container(border=True):
            col_title, col_status = st.columns([3, 1])
            with col_title:
                st.markdown(f"### ⚙️ {row['machine_label']}")
            with col_status:
                status_text = (
                    "SIN CONEXIÓN"
                    if not alert["online"]
                    else (
                        "PARADO"
                        if alert["shutdown"]
                        else "ENCENDIDO" if (alert["press"] or 0) > 1 else "APAGADO"
                    )
                )
                status_class = (
                    "status-offline"
                    if not alert["online"]
                    else ("status-off" if status_text != "ENCENDIDO" else "status-on")
                )
                st.markdown(
                    f"<div style='text-align:right;'><span class='status-badge {status_class}'>{status_text}</span></div>",
                    unsafe_allow_html=True,
                )

            if not alert["online"]:
                st.markdown(
                    "<div class='industrial-alert-compact'>⚠️ Pérdida de comunicación: no se reciben telemetrías válidas.</div>",
                    unsafe_allow_html=True,
                )
                continue

            if alert["maintenance_alerts"]:
                tooltip = "&#10;".join(alert["maintenance_alerts"]).replace(
                    '"', "&quot;"
                )
                st.markdown(
                    f"<span class='maintenance-badge' title=\"{tooltip}\">🔧 ALARMA MANTENIMIENTO</span>",
                    unsafe_allow_html=True,
                )

            # --- Alarma sonora con reconocimiento (ACK) ---
            compresor_id = str(row["machine_key"])
            alarma_critica = alert["level"] == "PELIGRO"
            if (
                not alarma_critica
                and compresor_id in st.session_state["acknowledged_alarms"]
            ):
                st.session_state["acknowledged_alarms"].remove(compresor_id)

            if alarma_critica and sonido_activo:
                is_ack = compresor_id in st.session_state["acknowledged_alarms"]
                if alert["shutdown"]:
                    st.markdown(
                        f"<div class='industrial-alert-failure'>🚨 FALLA DE PARADA: código {alert['shutdown_code']}</div>",
                        unsafe_allow_html=True,
                    )
                if not is_ack:
                    play_alarm_sound()
                    ack_input = st.text_input(
                        f"🔕 Presiona ENTER para silenciar alarma de {row['machine_label']}:",
                        key=f"ack_input_{compresor_id}",
                        placeholder="Haz clic aquí y presiona Enter...",
                    )
                    if ack_input != "":
                        st.session_state["acknowledged_alarms"].add(compresor_id)
                        st.rerun()
                else:
                    stop_alarm_sound()
                    st.info(
                        "🔕 Alarma sonora silenciada por el operador para este activo."
                    )
            elif alarma_critica and alert["shutdown"]:
                st.markdown(
                    f"<div class='industrial-alert-failure'>🚨 FALLA DE PARADA: código {alert['shutdown_code']}</div>",
                    unsafe_allow_html=True,
                )

            # --- Renderizado de Métricas y Gauges (Completado) ---
            col_press, col_temp, col_hours = st.columns(3, gap="small")
            pressure_sink = (
                float(row["pressure_sink_bar"])
                if pd.notna(row["pressure_sink_bar"])
                else None
            )
            delta_pressure = (
                pressure_sink - alert["press"]
                if pressure_sink is not None and alert["press"] is not None
                else None
            )

            with col_press:
                st.plotly_chart(
                    draw_pressure_gauge(alert["press"] or 0.0),
                    use_container_width=True,
                    config={"responsive": True, "displayModeBar": False},
                    key=f"live_p_{row['machine_key']}",
                )
                if alert["press_alert"]:
                    st.error(alert["press_alert"], icon="⚠️")

            with col_temp:
                st.plotly_chart(
                    draw_temperature_gauge(alert["temp"] or 0.0),
                    use_container_width=True,
                    config={"responsive": True, "displayModeBar": False},
                    key=f"live_t_{row['machine_key']}",
                )
                if alert["temp_alert"]:
                    st.error(alert["temp_alert"], icon="⚠️")

            with col_hours:
                st.metric(
                    "Horas de Marcha",
                    (
                        f"{row['run_hours']:.1f} hs"
                        if pd.notna(row["run_hours"])
                        else "N/D"
                    ),
                )
                if delta_pressure is not None:
                    st.metric(
                        "Δ Presión (Depósito)",
                        f"{pressure_sink:.2f} bar",
                        delta=f"{delta_pressure:+.2f} bar",
                    )

                substate = translate_substate(row.get("operating_state", "N/D"))
                st.markdown(
                    "<div class='substate-label'>ESTADO OPERATIVO</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='substate-value'>{substate}</div>",
                    unsafe_allow_html=True,
                )

                last_ts = pd.to_datetime(row["timestamp"]).strftime("%d/%m/%Y %H:%M:%S")
                st.caption(f"Última lectura: {last_ts}")


# ==============================================================================
# 12. APORTES Y ENTRYPOINT (main)
# ==============================================================================
def main():
    load_css()

    df_latest = get_latest_data()
    alerts_by_machine = {}
    if not df_latest.empty:
        alerts_by_machine = {
            row["machine_key"]: check_alerts(row, DEFAULT_PREVENTIVE_ALERTS)
            for _, row in df_latest.iterrows()
        }

    sidebar_config = render_sidebar(df_latest, alerts_by_machine)

    st.title("🏭 Planta Beniplast — Monitoreo Industrial SCADA")
    st.caption("Sistema de Telemetría e Indicadores en Tiempo Real")

    tab_live, tab_history = st.tabs(
        ["📡 Monitoreo en Vivo", "📊 Historial y Analítica"]
    )

    with tab_live:
        render_live_monitoring(
            sidebar_config["thresholds_by_key"], sidebar_config["sonido_activo"]
        )

    with tab_history:
        st.markdown("### 📊 Análisis Histórico de Equipos")
        col_sel, col_start, col_end = st.columns([2, 1, 1])

        with col_sel:
            selected_machine = st.selectbox(
                "Seleccionar Equipo",
                options=ORDEN_PLANTA_KEYS,
                format_func=lambda x: MACHINE_DISPLAY_LABEL.get(x, x),
                key="hist_machine_select",
            )
        with col_start:
            start_date = st.date_input(
                "Fecha Inicio",
                value=datetime.now(DATA_TIMEZONE).date() - timedelta(days=1),
            )
        with col_end:
            end_date = st.date_input(
                "Fecha Fin", value=datetime.now(DATA_TIMEZONE).date()
            )

        if start_date > end_date:
            st.error("La fecha de inicio no puede ser posterior a la fecha de fin.")
        else:
            df_hist = get_historical_data(selected_machine, start_date, end_date)
            if not df_hist.empty:
                machine_label = MACHINE_DISPLAY_LABEL.get(
                    selected_machine, selected_machine
                )
                render_charts(df_hist, machine_label)

                csv = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Descargar datos históricos (CSV)",
                    data=csv,
                    file_name=f"historial_{selected_machine}_{start_date}_{end_date}.csv",
                    mime="text/csv",
                )
            else:
                st.info(
                    "No se encontraron registros en el rango de fechas seleccionado."
                )


if __name__ == "__main__":
    main()
