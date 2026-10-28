import json
import math
import os
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import database as db
import maintenance_manager as mm
from components.gauges import draw_pressure_gauge, draw_temperature_gauge
from components.sidebar import render_sidebar
from components.styles import inject_scada_styles

# 1. Configuración de página e inyección CSS
st.set_page_config(
    page_title="Beniplast | Monitoreo Industrial", page_icon="B", layout="wide"
)
inject_scada_styles()

# 2. Configuración general
DATA_TIMEZONE = db.DATA_TIMEZONE
plotly_theme = "plotly_dark"
card_bg = "#161B22"
text_color = "#FFFFFF"
grid_color = "#21262D"

PREVENTIVE_ALERTS = {
    "AERCOM 22P": {
        "max_temp": 90.0,
        "min_temp": 65.0,
        "max_press": 8,
        "min_press": 6.5,
    },
    "SULLAIR SE1507NEW": {
        "max_temp": 90.0,
        "min_temp": 65.0,
        "max_press": 8,
        "min_press": 6.5,
    },
    "CHILLER TRANE CGAX030": {
        "max_temp": 12.0,
        "min_temp": 4.5,
        "max_press": 8,
        "min_press": 6.5,
    },
}

SULLAIR_MANUAL_DISABLED_STATE = "READY (LISTO)"

SUBSTATE_LABELS = {
    "STOPPED": "DETENIDO",
    "OFF / DETENIDO": "DETENIDO",
    SULLAIR_MANUAL_DISABLED_STATE: "LISTO/DESACTIVADO MANUALMENTE",
    "ENABLED": "HABILITADO",
    "AUTOENABLED": "AUTO HABILITADO",
    "STARTING (ARRANCANDO)": "ARRANCANDO",
    "UNLOADED (EN VACÍO)": "EN VACÍO",
    "LOADING (CARGANDO)": "CARGANDO",
    "FULL LOAD (PLENA CARGA)": "PLENA CARGA",
    "MODULATING (MODULANDO)": "MODULANDO",
    "STOPPING (PARANDO)": "DETENIENDO",
}

SULLAIR_OFF_STATES = {"STOPPED", "OFF / DETENIDO"}
SULLAIR_ON_STATES = {
    SULLAIR_MANUAL_DISABLED_STATE,
    "ENABLED",
    "AUTOENABLED",
    "STARTING (ARRANCANDO)",
    "UNLOADED (EN VACÍO)",
    "LOADING (CARGANDO)",
    "FULL LOAD (PLENA CARGA)",
    "MODULATING (MODULANDO)",
    "STOPPING (PARANDO)",
}


def translate_substate(value):
    return SUBSTATE_LABELS.get(str(value).strip().upper(), str(value))


def estimate_service_days(
    hours_remaining: float | None, start_date: date | None = None
) -> int | None:
    if (
        hours_remaining is None
        or not pd.notna(hours_remaining)
        or not math.isfinite(hours_remaining)
    ):
        return None
    if hours_remaining <= 0:
        return 0

    today = start_date or datetime.now(DATA_TIMEZONE).date()
    service_date = today
    remaining = hours_remaining
    while remaining > 0:
        service_date += timedelta(days=1)
        weekday = service_date.weekday()
        daily_hours = 24 if weekday < 5 else 12 if weekday == 5 else 0
        remaining -= daily_hours

    return (service_date - today).days


def get_preventive_alerts(alert_key: str) -> dict:
    thresholds = PREVENTIVE_ALERTS[alert_key]
    return {
        "max_temp": thresholds["max_temp"],
        "min_temp": thresholds["min_temp"],
        "max_press": thresholds["max_press"],
        "min_press": thresholds["min_press"],
    }


if "acknowledged_alarms" not in st.session_state:
    st.session_state["acknowledged_alarms"] = set()


def trigger_alarm_sound():
    js_code = """
    <script>
    const appWindow = window.parent;
    const appDocument = appWindow.document;
    if (!appDocument.__alarmKeyboardInstalled) {
        appDocument.addEventListener('keydown', (event) => {
            if (event.code === 'Space' || event.key === 'Enter') {
                appWindow.__alarmMuted = true;
                if (appWindow.__alarmInterval) {
                    clearInterval(appWindow.__alarmInterval);
                    appWindow.__alarmInterval = null;
                }
            }
        });
        appDocument.__alarmKeyboardInstalled = true;
    }
    if (!appWindow.__alarmMuted && !appWindow.__alarmInterval) {
        const audioCtx = new (appWindow.AudioContext || appWindow.webkitAudioContext)();
        appWindow.__alarmInterval = setInterval(() => {
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
    if (window.parent.__alarmInterval) {
        clearInterval(window.parent.__alarmInterval);
        window.parent.__alarmInterval = null;
    }
    </script>
    """
    components.html(js_code, height=0, width=0)


# 3. Renderizar Barra Lateral
render_sidebar()

# 4. Encabezado principal
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(BASE_DIR, "assets", "logo_grupo_beniplast.png")
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
    df_latest = db.get_latest_data()
    TIMEOUT_DESCONEXION = int(os.getenv("TIMEOUT_DESCONEXION", "200"))
    has_unacknowledged_critical_alarm = False

    if not df_latest.empty:
        for index, row in df_latest.iterrows():
            with st.container(border=True):
                last_update = pd.to_datetime(row["timestamp"])
                if last_update.tzinfo is None:
                    last_update = last_update.tz_localize(DATA_TIMEZONE)
                now = pd.Timestamp.now(tz="UTC")
                segundos_sin_datos = (
                    now - last_update.astimezone("UTC")
                ).total_seconds()

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
                separator_filter_dp = (
                    float(row["separator_filter_dp"])
                    if pd.notna(row["separator_filter_dp"])
                    else None
                )
                if (
                    separator_filter_dp is None
                    and pressure_sink is not None
                    and press is not None
                ):
                    separator_filter_dp = max(0.0, pressure_sink - press)
                hours = float(row["run_hours"]) if pd.notna(row["run_hours"]) else None
                operating_state = (
                    translate_substate(row["operating_state"])
                    if pd.notna(row["operating_state"])
                    else "N/D"
                )
                is_sullair_manual_disabled = (
                    str(row["machine_key"]) == "SULLAIR_COMPRESSOR"
                    and pd.notna(row["operating_state"])
                    and str(row["operating_state"]).strip().upper()
                    == SULLAIR_MANUAL_DISABLED_STATE
                )
                state_upper = str(operating_state).upper()
                is_standby = "STANDBY" in state_upper or "ESPERA" in state_upper
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

                if segundos_sin_datos > TIMEOUT_DESCONEXION:
                    status = "SIN CONEXIÓN"
                    status_class = "status-offline"
                elif str(row["machine_key"]) == "SULLAIR_COMPRESSOR" and pd.notna(
                    row["operating_state"]
                ):
                    raw_state = str(row["operating_state"]).strip().upper()
                    if raw_state in SULLAIR_ON_STATES:
                        status = "ENCENDIDO"
                        status_class = "status-on"
                    elif raw_state in SULLAIR_OFF_STATES:
                        status = "APAGADO"
                        status_class = "status-off"
                    elif press is not None and press > 1:
                        status = "ENCENDIDO"
                        status_class = "status-on"
                    else:
                        status = "APAGADO"
                        status_class = "status-off"
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

                col_header_title, col_header_status = st.columns([3, 1])
                with col_header_title:
                    st.markdown(f"### ⚙️ {row['machine_label']}")
                with col_header_status:
                    st.markdown(
                        f"<div style='text-align: right; margin-top: 5px;'>{status_badge}</div>",
                        unsafe_allow_html=True,
                    )

                temperature_alert = None
                pressure_alert = None
                maintenance_alerts = []

                if not is_online:
                    st.markdown(
                        "<div class='industrial-alert-compact'>⚠️ Pérdida de comunicación: no se reciben telemetrías válidas.</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    alert_key = db.MACHINE_ALERT_KEY[str(row["machine_key"])]
                    thresholds = get_preventive_alerts(alert_key)

                    if temp is not None:
                        if temp > thresholds["max_temp"]:
                            temperature_alert = f"Alta Temperatura: {temp} °C (Umbral: >{thresholds['max_temp']} °C)"
                        elif (
                            temp < thresholds["min_temp"]
                            and not is_standby
                            and not is_sullair_manual_disabled
                        ):
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
                        with st.popover("🔧 ALARMA MANTENIMIENTO"):
                            st.markdown(
                                "\n".join(
                                    f"- {warning}" for warning in maintenance_alerts
                                )
                            )

                compresor_id = str(row["machine_key"])
                condicion_temp = temperature_alert is not None
                condicion_presion = pressure_alert is not None
                condicion_falla = shutdown_code not in (None, 0)
                alarma_critica = condicion_temp or condicion_presion or condicion_falla

                if (
                    not alarma_critica
                    and compresor_id in st.session_state["acknowledged_alarms"]
                ):
                    st.session_state["acknowledged_alarms"].remove(compresor_id)

                if alarma_critica:
                    is_ack = compresor_id in st.session_state["acknowledged_alarms"]
                    has_unacknowledged_critical_alarm |= not is_ack

                    if condicion_falla:
                        st.markdown(
                            f"<div class='industrial-alert-failure'>🚨 FALLA DE PARADA: código {shutdown_code}</div>",
                            unsafe_allow_html=True,
                        )

                    if not is_ack:
                        components.html(
                            "<script>document.body.focus();</script>", height=0, width=0
                        )

                machine_key = str(row["machine_key"])
                if machine_key in db.ORDEN_PLANTA_KEYS:
                    service_metrics = mm.calculate_service_metrics(
                        current_hours=(
                            hours if is_online and hours is not None else None
                        ),
                        machine_key=machine_key,
                    )
                    hs_restantes = service_metrics["hours_remaining"]
                    pct_prog = service_metrics["progress_pct"]
                    status_col = service_metrics["status_color"]
                    service_progress = min(100.0, max(0.0, pct_prog))
                    if service_metrics["status"] == "UNKNOWN":
                        dias_service_label = "N/D"
                    elif hs_restantes <= 0:
                        dias_service_label = "SERVICE VENCIDO"
                    else:
                        dias_service = estimate_service_days(hs_restantes)
                        unidad_dias = "día" if dias_service == 1 else "días"
                        dias_service_label = (
                            f"{dias_service} {unidad_dias} estimados"
                            if dias_service is not None
                            else "N/D"
                        )
                else:
                    hs_restantes = None
                    service_progress = 0.0
                    status_col = "#94A3B8"
                    dias_service_label = "N/D"

                col_press, col_temp, col_hours = st.columns(3, gap="small")
                delta_pressure = separator_filter_dp

                with col_press:
                    if is_online:
                        st.plotly_chart(
                            draw_pressure_gauge(press if press is not None else 0.0),
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
                            draw_temperature_gauge(temp if temp is not None else 0.0),
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

                    if machine_key in db.ORDEN_PLANTA_KEYS:
                        st.markdown(
                            f"""
                            <div class="service-mini-card">
                                <div class="service-mini-label">Hs restantes para proximo service</div>
                                <div class="service-mini-bar">
                                    <div class="service-mini-bar-fill" style="width: {service_progress:.1f}%; background-color: {status_col};"></div>
                                </div>
                                <div class="service-mini-values">
                                    <span>{int(hs_restantes):,} hs</span>
                                    <span>{service_progress:.0f}%</span>
                                </div>
                                <div style="color: #EF4444; font-size: 1.2rem; font-weight: 200; margin-top: 6px;">
                                    {dias_service_label} para el próximo service
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                st.markdown(
                    f"<p style='color:#94A3B8; font-size:11px; margin:0; text-align:right;'>Última telemetría: {row['timestamp']}</p>",
                    unsafe_allow_html=True,
                )
    else:
        st.warning("No se encontraron activos transmitiendo en vivo.")

    if has_unacknowledged_critical_alarm:
        trigger_alarm_sound()
    else:
        stop_alarm_sound()

# --- TAB 2: HISTORIAL DE TENDENCIAS (VERSION MEJORADA) ---
with tab2:
    df_latest_names = db.get_latest_data()

    if not df_latest_names.empty:
        col_select_asset, col_select_period = st.columns([1, 1])
        with col_select_asset:
            machine_list = df_latest_names["machine_key"].tolist()
            selected_machine = st.selectbox(
                "Seleccione el activo a analizar:",
                machine_list,
                format_func=lambda x: db.MACHINE_DISPLAY_LABEL.get(x, x),
                key="select_history_asset",
            )
        with col_select_period:
            periodo_opcion = st.selectbox(
                "Período a consultar:",
                [
                    "📅 Hoy",
                    "⏱️ Últimas 24 horas",
                    "📊 Últimos 3 días",
                    "📆 Últimos 7 días",
                    "🗓️ Personalizado",
                ],
                index=1,
                key="history_period_preset",
            )

        today = datetime.now(DATA_TIMEZONE).date()
        if periodo_opcion == "📅 Hoy":
            start_date = today
            end_date = today
        elif periodo_opcion == "⏱️ Últimas 24 horas":
            start_date = today - timedelta(days=1)
            end_date = today
        elif periodo_opcion == "📊 Últimos 3 días":
            start_date = today - timedelta(days=2)
            end_date = today
        elif periodo_opcion == "📆 Últimos 7 días":
            start_date = today - timedelta(days=6)
            end_date = today
        else:
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                start_date = st.date_input(
                    "Fecha inicial",
                    value=today - timedelta(days=1),
                    format="DD/MM/YYYY",
                    key="history_start_date",
                )
            with col_d2:
                end_date = st.date_input(
                    "Fecha final",
                    value=today,
                    format="DD/MM/YYYY",
                    key="history_end_date",
                )

        if start_date > end_date:
            st.error("La fecha inicial no puede ser posterior a la fecha final.")
            st.stop()

        df_hist = db.get_historical_data(selected_machine, start_date, end_date)

        if not df_hist.empty:
            nombre_activo = db.MACHINE_DISPLAY_LABEL.get(
                selected_machine, selected_machine
            )

            # --- 1. RESUMEN EJECUTIVO (KPI CARDS) ---
            t_max = df_hist["temperature_c"].max()
            t_avg = df_hist["temperature_c"].mean()
            p_min = df_hist["pressure_bar"].min()
            p_avg = df_hist["pressure_bar"].mean()
            reg_count = len(df_hist)

            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric(
                "🌡️ Temp. Máx / Prom.",
                f"{t_max:.1f} °C",
                f"Prom: {t_avg:.1f} °C",
                delta_color="off",
            )
            kpi2.metric(
                "📉 Presión Mín / Prom.",
                f"{p_min:.1f} Bar",
                f"Prom: {p_avg:.1f} Bar",
                delta_color="off",
            )
            kpi3.metric("📊 Total Registros", f"{reg_count:,}")
            kpi4.metric(
                "⏱️ Período",
                f"{(df_hist['timestamp'].max() - df_hist['timestamp'].min()).total_seconds()/3600:.1f} hs",
            )
            run_hours = (
                pd.to_numeric(df_hist["run_hours"], errors="coerce").dropna()
                if "run_hours" in df_hist.columns
                else pd.Series(dtype="float64")
            )
            if len(run_hours) >= 2 and run_hours.iloc[-1] >= run_hours.iloc[0]:
                hours_on = run_hours.iloc[-1] - run_hours.iloc[0]
                hours_on_value = f"{hours_on:.1f} hs"
            else:
                hours_on_value = "N/D"
            kpi5.metric("⚙️ Horas encendido", hours_on_value)

            st.markdown("---")

            # --- 2. GRÁFICOS COMPACTOS EN 2 COLUMNAS ---
            # Romper líneas continuas si hay baches de más de 15 mins (evitar la recta en vacíos)
            df_plot = df_hist.copy().sort_values("timestamp")
            df_plot["time_diff"] = df_plot["timestamp"].diff().dt.total_seconds()
            df_plot.loc[
                df_plot["time_diff"] > 900, ["temperature_c", "pressure_bar"]
            ] = None

            c_graph1, c_graph2 = st.columns(2)

            with c_graph1:
                st.markdown("##### 📈 Evolución Térmica")
                fig_temp = px.line(
                    df_plot, x="timestamp", y="temperature_c", height=280
                )
                fig_temp.update_traces(
                    line_color="#FF5252", line_width=1.8, connectgaps=False
                )
                fig_temp.update_layout(
                    template=plotly_theme,
                    hovermode="x unified",
                    margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor=card_bg,
                    font=dict(color=text_color, size=11),
                    xaxis=dict(showgrid=True, gridcolor=grid_color, title=""),
                    yaxis=dict(showgrid=True, gridcolor=grid_color, title="°C"),
                )
                st.plotly_chart(
                    fig_temp, use_container_width=True, key=f"c_temp_{selected_machine}"
                )

            with c_graph2:
                st.markdown("##### 📉 Comportamiento de Presión")
                fig_pres = px.line(df_plot, x="timestamp", y="pressure_bar", height=280)
                fig_pres.update_traces(
                    line_color="#00E676", line_width=1.8, connectgaps=False
                )
                fig_pres.update_layout(
                    template=plotly_theme,
                    hovermode="x unified",
                    margin=dict(l=10, r=10, t=20, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor=card_bg,
                    font=dict(color=text_color, size=11),
                    xaxis=dict(showgrid=True, gridcolor=grid_color, title=""),
                    yaxis=dict(showgrid=True, gridcolor=grid_color, title="Bar"),
                )
                st.plotly_chart(
                    fig_pres, use_container_width=True, key=f"c_pres_{selected_machine}"
                )

            # --- 3. EXPANDER PARA ZOOM O CORRELACIÓN AVANZADA ---
            with st.expander("🔍 Ver Análisis Combinado y Zoom Detallado"):
                fig_comb = go.Figure()
                fig_comb.add_trace(
                    go.Scatter(
                        x=df_plot["timestamp"],
                        y=df_plot["pressure_bar"],
                        name="Presión (Bar)",
                        line=dict(color="#00E676", width=2),
                        connectgaps=False,
                    )
                )
                fig_comb.add_trace(
                    go.Scatter(
                        x=df_plot["timestamp"],
                        y=df_plot["temperature_c"],
                        name="Temperatura (°C)",
                        yaxis="y2",
                        line=dict(color="#FF5252", width=2),
                        connectgaps=False,
                    )
                )

                fig_comb.update_layout(
                    template=plotly_theme,
                    height=420,
                    hovermode="x unified",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor=card_bg,
                    font=dict(color=text_color),
                    xaxis=dict(
                        showgrid=True, gridcolor=grid_color, title="Fecha y Hora"
                    ),
                    yaxis=dict(
                        title=dict(text="Presión (Bar)", font=dict(color="#00E676")),
                        showgrid=True,
                        gridcolor=grid_color,
                        tickfont=dict(color="#00E676"),
                    ),
                    yaxis2=dict(
                        title=dict(text="Temperatura (°C)", font=dict(color="#FF5252")),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                        tickfont=dict(color="#FF5252"),
                    ),
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                    ),
                )
                st.plotly_chart(
                    fig_comb, use_container_width=True, key=f"comb_{selected_machine}"
                )

            st.markdown("---")

            # --- 4. TABLA DE REGISTROS Y DESVIACIONES CRÍTICAS ---
            alert_key = db.MACHINE_ALERT_KEY.get(selected_machine, selected_machine)
            thresholds = PREVENTIVE_ALERTS.get(
                alert_key,
                {
                    "max_temp": 90.0,
                    "min_temp": 65.0,
                    "max_press": 8.0,
                    "min_press": 6.5,
                },
            )

            col_t_title, col_t_filter, col_t_export = st.columns(
                [2, 2, 1], vertical_alignment="center"
            )
            with col_t_title:
                st.markdown("##### 📋 Registro Histórico de Operación")
            with col_t_filter:
                solo_anomalias = st.checkbox(
                    "⚠️ Filtrar solo anomalías u omisiones fuera de rango", value=False
                )
            with col_t_export:
                csv_data = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Exportar CSV",
                    data=csv_data,
                    file_name=f"historial_{selected_machine}_{today}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            # Lógica inteligente de detección de anomalías
            df_table = df_hist.copy().sort_values("timestamp", ascending=False)

            def evaluar_anomalia(row):
                motivos = []
                temp = row["temperature_c"]
                press = row["pressure_bar"]

                if pd.notna(temp) and temp > thresholds["max_temp"]:
                    motivos.append(
                        f"Alta Temp ({temp:.1f}°C > {thresholds['max_temp']}°C)"
                    )
                if pd.notna(press) and (
                    press > thresholds["max_press"] or press < thresholds["min_press"]
                ):
                    motivos.append(f"Presión fuera de rango ({press:.1f} Bar)")

                return ", ".join(motivos) if motivos else "Normal"

            df_table["Detalle_Estado"] = df_table.apply(evaluar_anomalia, axis=1)
            df_table["Es_Anomalia"] = df_table["Detalle_Estado"] != "Normal"

            if solo_anomalias:
                df_table_display = df_table[df_table["Es_Anomalia"]].copy()
            else:
                df_table_display = df_table.copy()

            if not df_table_display.empty:
                df_show = pd.DataFrame(
                    {
                        "Fecha y Hora": df_table_display["timestamp"].dt.strftime(
                            "%d/%m/%Y %H:%M:%S"
                        ),
                        "Activo": nombre_activo,
                        "Presión": df_table_display["pressure_bar"],
                        "Temperatura": df_table_display["temperature_c"],
                        "Estado / Advertencia": df_table_display["Detalle_Estado"],
                        "_es_anomalia": df_table_display["Es_Anomalia"],
                    }
                )

                es_anomalia_list = df_show["_es_anomalia"].tolist()
                df_show_clean = df_show.drop(columns=["_es_anomalia"])

                # Aplicar color rojo suave SOLO a las anomalías reales
                tabla_estilizada = df_show_clean.style.apply(
                    lambda _: [
                        (
                            "background-color: rgba(153, 27, 27, 0.4); color: #ffffff; font-weight: bold;"
                            if es_anomalia_list[i]
                            else ""
                        )
                        for i in range(len(df_show_clean))
                    ],
                    axis=0,
                )

                st.dataframe(
                    tabla_estilizada,
                    use_container_width=True,
                    hide_index=True,
                    height=350,
                    column_config={
                        "Presión": st.column_config.NumberColumn(
                            "Presión", format="%.1f Bar"
                        ),
                        "Temperatura": st.column_config.NumberColumn(
                            "Temperatura", format="%.1f °C"
                        ),
                    },
                )
            else:
                st.success(
                    "✅ No se detectaron anomalías fuera de rango en el período consultado."
                )
        else:
            st.info(
                f"El activo {selected_machine} no registra datos históricos almacenados en el período seleccionado."
            )
