import json
import os
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
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
                        alert_tooltip = "&#10;".join(maintenance_alerts).replace(
                            '"', "&quot;"
                        )
                        st.markdown(
                            f"<span class='maintenance-badge' title=\"{alert_tooltip}\">🔧 ALARMA MANTENIMIENTO</span>",
                            unsafe_allow_html=True,
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
                else:
                    hs_restantes = None
                    service_progress = 0.0

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

# --- TAB 2: HISTORIAL DE TENDENCIAS ---
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
                index=0,
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
            st.markdown(
                f"#### Historial analítico: **{nombre_activo}** (`{len(df_hist):,} registros cargados`)"
            )
            st.caption(
                f"Período mostrado: {df_hist['timestamp'].min():%d/%m/%Y %H:%M} a {df_hist['timestamp'].max():%d/%m/%Y %H:%M}"
            )

            fig_temp = px.line(
                df_hist,
                x="timestamp",
                y="temperature_c",
                title="📈 Evolución Térmica",
                markers=bool(len(df_hist) < 150),
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
                fig_temp, width="stretch", key=f"chart_h_temp_{selected_machine}"
            )

            fig_pres = px.line(
                df_hist,
                x="timestamp",
                y="pressure_bar",
                title="📉 Comportamiento de Presión",
                markers=bool(len(df_hist) < 150),
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
                fig_pres, width="stretch", key=f"chart_h_pres_{selected_machine}"
            )

            col_view_opt, col_limit_opt = st.columns([1, 1])
            with col_view_opt:
                vista_tabla = st.selectbox(
                    "Vista de la tabla",
                    ["Resumen diario (recomendado)", "Mostrar todos los datos crudos"],
                    key="history_table_view",
                )

            if vista_tabla == "Resumen diario (recomendado)":
                datos_diarios = df_hist.copy()
                datos_diarios["fecha"] = datos_diarios["timestamp"].dt.date

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
                    fecha_str = (
                        fecha.strftime("%d/%m/%Y")
                        if hasattr(fecha, "strftime")
                        else str(fecha)
                    )
                    filas_resumen.append(
                        {
                            "Fecha completa": fecha_str,
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
                    for _, lectura in lecturas_con_desviacion.head(30).iterrows():
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
                with col_limit_opt:
                    if len(df_hist) > 500:
                        limite_filas = st.selectbox(
                            "Registros a mostrar en tabla:",
                            ["Últimos 500", "Últimos 1.000", "Todos los registros"],
                            index=0,
                            key="history_raw_limit",
                        )
                        if limite_filas == "Últimos 500":
                            df_hist_sub = df_hist.tail(500)
                        elif limite_filas == "Últimos 1.000":
                            df_hist_sub = df_hist.tail(1000)
                        else:
                            df_hist_sub = df_hist
                    else:
                        df_hist_sub = df_hist

                tabla_historial = pd.DataFrame(
                    {
                        "Fecha completa": df_hist_sub["timestamp"].dt.strftime(
                            "%d/%m/%Y %H:%M:%S"
                        ),
                        "Activo": nombre_activo,
                        "Presión": df_hist_sub["pressure_bar"],
                        "Temperatura": df_hist_sub["temperature_c"],
                        "Detalle": "Lectura registrada",
                        "Es desviación": False,
                    }
                )

            if not tabla_historial.empty:
                tabla_historial = tabla_historial.reset_index(drop=True)
                es_desviacion_list = tabla_historial["Es desviación"].tolist()
                tabla_display = tabla_historial.drop(
                    columns=["Es desviación"], errors="ignore"
                )

                tabla_mostrada = tabla_display.style.apply(
                    lambda _: [
                        (
                            "background-color: #7f1d1d; color: #ffffff"
                            if es_desviacion_list[i]
                            else ""
                        )
                        for i in range(len(tabla_display))
                    ],
                    axis=0,
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
                f"El activo {selected_machine} no registra datos históricos almacenados en el período seleccionado."
            )
