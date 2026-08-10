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
umbral_current_OFF = (
    2.0  # Amperios (Si baja de este valor, se considera que el motor está apagado)
)

# ORDEN VISUAL DE LA PLANTA (Primero compresores, al final Chiller)
ORDEN_PLANTA = ["AERCOM_22P", "SULLAIR_COMPRESSOR", "CHILLER_TRANE"]

# ==============================================================================
# 1. CONFIGURACIÓN DE PÁGINA (¡Restaurada!)
# ==============================================================================
st.set_page_config(
    page_title="Monitoreo Industrial IIoT", page_icon="🏭", layout="wide"
)

# ==============================================================================
# SELECCIÓN DE TEMA DINÁMICO EN EL SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("🎨 Personalización")
    tema_seleccionado = st.radio(
        "Modo de Visualización:",
        ["🌙 Oscuro SCADA", "☀️ Claro Industrial", "🎨 Personalizado"],
        index=0,
    )

    if tema_seleccionado == "🌙 Oscuro SCADA":
        bg_color = "#0E1117"
        card_bg = "#161B22"
        card_border = "#30363D"
        text_color = "#E0E6ED"
        text_muted = "#8B949E"
        metric_color = "#58A6FF"
        gauge_track = "#21262D"
        plotly_theme = "plotly_dark"
        grid_color = "#21262D"

    elif tema_seleccionado == "☀️ Claro Industrial":
        bg_color = "#F8FAFC"
        card_bg = "#FFFFFF"
        card_border = "#CBD5E1"
        text_color = "#0F172A"  # Oscuro para legibilidad total
        text_muted = "#475569"
        metric_color = "#1D4ED8"
        gauge_track = "#E2E8F0"
        plotly_theme = "plotly_white"
        grid_color = "#E2E8F0"

    else:  # 🎨 Personalizado
        bg_color = st.color_picker(
            "Color de fondo principal:", "#1E293B", key="picker_bg"
        )
        card_bg = st.color_picker("Color de tarjetas:", "#0F172A", key="picker_card")
        card_border = "#475569"
        text_color = "#F8FAFC"
        text_muted = "#94A3B8"
        metric_color = "#38BDF8"
        gauge_track = "#334155"
        plotly_theme = "plotly_dark"
        grid_color = "#334155"

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
                    conn_dbg = None
                    try:
                        conn_dbg = init_connection()
                    except Exception as e_conn:
                        st.error(
                            f"No se pudo inicializar conexión para debug: {e_conn}"
                        )
                        conn_dbg = None

                    if conn_dbg is None:
                        st.warning(
                            "No se pudo abrir conexión para obtener estado de activos"
                        )
                    else:
                        query_dbg = """
                        SELECT DISTINCT ON (UPPER(TRIM(machine_name)))
                            UPPER(TRIM(machine_name)) as machine_name, timestamp, current_amps
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
                                rows.append(
                                    {
                                        "machine": r["machine_name"],
                                        "timestamp": str(ts),
                                        "tz": (
                                            str(ts.tzinfo) if ts is not None else None
                                        ),
                                        "current_amps": r.get("current_amps"),
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
        UPPER(TRIM(machine_name)) as machine_name, timestamp, pressure_bar, temperature_c, run_hours, current_amps
    FROM historical_telemetry
    ORDER BY UPPER(TRIM(machine_name)), timestamp DESC;
    """
    df = pd.read_sql(query, conn)

    if not df.empty:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(DATA_TIMEZONE)
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
            domain={"x": [0, 1], "y": [0, 1]},
            title={
                "text": f"<b>{title}</b>",
                "font": {"size": 14, "color": font_color},
                "align": "center",
            },
            number={
                "font": {"size": 22, "color": font_color},
                "suffix": f" {unit}",
            },
            gauge={
                "axis": {
                    "range": [0, max_val],
                    "tickwidth": 1,
                    "tickcolor": font_color,
                    "tickfont": {"size": 10, "color": font_color},
                },
                "bar": {"color": color},
                "bgcolor": track_color,
                "borderwidth": 0,
            },
        )
    )
    fig.update_layout(
        height=145,
        margin=dict(l=20, r=20, t=40, b=10),
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
    TIMEOUT_DESCONEXION = 30

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
                amps = row["current_amps"] if pd.notna(row["current_amps"]) else None
                temp = row["temperature_c"] if pd.notna(row["temperature_c"]) else None
                press = row["pressure_bar"] if pd.notna(row["pressure_bar"]) else None
                hours = row["run_hours"] if pd.notna(row["run_hours"]) else None

                # 🔌 Estado operativo
                if segundos_sin_datos > TIMEOUT_DESCONEXION or amps is None:
                    is_online = False
                    status_badge = """
                    <span style='background-color: #3D2D00; color: #FBBF24; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #D97706;'>
                        ⚠️ SIN RECEPCIÓN
                    </span>
                    """
                elif amps > umbral_current_OFF:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #0D3321; color: #34D399; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #059669;'>
                        🟢 ENCENDIDO
                    </span>
                    """
                else:
                    is_online = True
                    status_badge = """
                    <span style='background-color: #3C1618; color: #F87171; padding: 6px 14px; 
                    border-radius: 20px; font-weight: 600; font-size: 14px; border: 1px solid #DC2626;'>
                        🔴 APAGADO
                    </span>
                    """

                # 🗂️ ENCABEZADO DE ACTIVO
                col_header_title, col_header_status = st.columns([3, 1])
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_name']}")
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
                    if temp is not None and temp > umbral_temp:
                        alert_messages.append(
                            f"Alta Temperatura: {temp} °C (Umbral: >{umbral_temp}°C)"
                        )
                    if press is not None and press > umbral_pressure:
                        alert_messages.append(
                            f"Alta Presión: {press} Bar (Umbral: >{umbral_pressure} Bar)"
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
                col_press, col_temp, col_amps, col_hours = st.columns(4)

                with col_press:
                    st.plotly_chart(
                        draw_gauge(
                            press if press is not None else 0.0,
                            "Presión",
                            15,
                            (
                                "#00E676"
                                if tema_seleccionado == "🌙 Oscuro SCADA"
                                else "#059669"
                            ),
                            "Bar",
                            text_color,
                            gauge_track,
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
                            (
                                "#FF5252"
                                if tema_seleccionado == "🌙 Oscuro SCADA"
                                else "#DC2626"
                            ),
                            "°C",
                            text_color,
                            gauge_track,
                        ),
                        use_container_width=True,
                        key=f"live_t_{row['machine_name']}",
                    )

                with col_amps:
                    st.markdown(
                        "<div style='min-height:15px;'></div>",
                        unsafe_allow_html=True,
                    )
                    st.metric(
                        label="⚡ Corriente Motor",
                        value=f"{amps} A" if amps is not None else "---",
                    )

                with col_hours:
                    st.markdown(
                        "<div style='min-height:15px;'></div>",
                        unsafe_allow_html=True,
                    )
                    st.metric(
                        label="⏱️ Horas de Marcha",
                        value=f"{hours:,.1f} h" if hours is not None else "---",
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
st.title("🏭 Multi-Asset Telemetry Pipeline")
st.caption("Sistema SCADA IIoT — Monitoreo de activos industriales en tiempo real")
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
            "Seleccione el activo a analizar:",
            machine_list,
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
