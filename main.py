import json
import socket
import threading
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pymodbus.client import ModbusTcpClient

import config
from database import save_reading

# ==========================================
# CONFIGURACIÓN SULLAIR (Sockets TCP Puros)
# ==========================================
GATEWAY_IP_SULLAIR = config.IP_SULLAIR_COMPRESSOR
PORT_SULLAIR = 502  # Puerto TCP configurado en el conversor Sullair
SLAVE_ID_SULLAIR = config.MODBUS_SLAVE_ID

ADDR_SHUTDOWN = 0
ADDR_MODE = 5
ADDR_STATE = 6
ADDR_TEMP_T1 = 7
ADDR_PRES_P1 = 10
ADDR_PRES_P2 = 11
ADDR_RUN_HI = 68
ADDR_RUN_LO = 69
ADDR_WARNA = 78
ADDR_WARNB = 79

MODE_NAMES = {0: "STOPPED", 1: "CONTINUOUS", 2: "AUTOMATIC (AUTO)"}
STATE_NAMES = {
    0: "OFF / DETENIDO",
    3: "READY (LISTO)",
    4: "ENABLED",
    5: "AUTOENABLED",
    8: "STARTING (ARRANCANDO)",
    10: "UNLOADED (EN VACÍO)",
    11: "LOADING (CARGANDO)",
    12: "FULL LOAD (PLENA CARGA)",
    13: "MODULATING (MODULANDO)",
    14: "STOPPING (PARANDO)",
}
SHUTDOWN_MAPPING = {
    0: "SIN FALLAS DE PARADA",
    1: "ALTA TEMPERATURA DE DESCARGA",
    2: "SOBREPRESIÓN EN LÍNEA / SUMIDERO",
    3: "FALLA EN ARRANCADOR / SOBRECARGA MOTOR",
    4: "PARADA DE EMERGENCIA ACTIVADA",
    5: "SECUENCIA / PÉRDIDA DE FASE",
    6: "FALLA SENSOR TEMPERATURA T1",
    7: "FALLA SENSOR PRESIÓN P1 (SUMIDERO)",
    8: "FALLA SENSOR PRESIÓN P2 (LÍNEA)",
}

WARNA_BITS = {
    0x0001: "REEMPLAZAR FILTRO DE ACEITE / FLUIDO",
    0x0002: "REEMPLAZAR ELEMENTO SEPARADOR",
    0x0004: "REEMPLAZAR FILTRO DE AIRE",
    0x0008: "REALIZAR ANÁLISIS DE ACEITE",
    0x0010: "REEMPLAZAR ACEITE / FLUIDO COMPLETO",
    0x0020: "MANTENIMIENTO PREVENTIVO PROGRAMADO",
}

WARNB_BITS = {
    0x0008: "ADVERTENCIA: ALTA TEMPERATURA T1",
    0x0020: "ADVERTENCIA: ALTA TEMPERATURA T2",
}

# ==========================================
# CONFIGURACIÓN AERCOM FRECON 22P (Pymodbus)
# ==========================================
AERCOM_IP = config.IP_AERCOM_22P
AERCOM_PORT = 502
AERCOM_POLLING_INTERVAL = getattr(config, "POLLING_INTERVAL", 60)
AERCOM_DEVICE_ID = 1

AERCOM_REG_STATE = 1025
AERCOM_REG_ALARM = 1026
AERCOM_REG_TEMPERATURE = 1029
AERCOM_REG_PRESSURE = 1030
AERCOM_REG_SEPARATOR_PRESSURE = 1031
AERCOM_REG_RUN_HOURS_HIGH = 1536
AERCOM_REG_RUN_HOURS_LOW = 1537
AERCOM_REG_LOAD_HOURS_HIGH = 1538
AERCOM_REG_LOAD_HOURS_LOW = 1539

AERCOM_STATES = {
    0: "APAGADO (OFF)",
    1: "ESPERA (Presion Interna Alta)",
    2: "PARADA REMOTA ACTIVA",
    3: "PARADO POR TIMER",
    4: "DESACELERANDO (IDLE STOP)",
    7: "STANDBY / BACKUP (Presion en Set, Motor Apagado)",
    8: "ESPERA DE SEGURIDAD (Timer Wt5)",
    9: "ARRANCANDO MOTOR",
    10: "MARCHA EN VACIO (IDLE)",
    11: "EN CARGA (LOAD RUNNING)",
    13: "BLOQUEADO POR FALLA",
}

AERCOM_ALARMS = {
    0: "Sin Alarma (OK)",
    1: "A01 - Parada de Emergencia",
    2: "A02 - Sobrecarga Termica Motor Principal",
    3: "A03 - Sobrecarga Termica Electroventilador",
    4: "A04 - Falta de Fase",
    5: "A05 - Secuencia de Fases Incorrecta",
    11: "A11 - Alta Presion de Trabajo",
    12: "A12 - Falla Sonda de Temperatura",
    13: "A13 - Alta Temperatura de Tornillo",
    18: "A18 - Black Out / Corte de Energia",
    28: "A28 - Bajo Voltaje de Alimentacion",
    30: "A30 - Advertencia Alta Temperatura",
}


# ==========================================
# FUNCIONES AUXILIARES GENERALES
# ==========================================
def ajustar_presion(valor):
    valor_decimal = Decimal(str(valor))
    centesimas = int(valor_decimal * 100)
    decimas = centesimas // 10
    resto = centesimas % 10
    if resto <= 6:
        return decimas / 10
    if resto >= 8:
        return (decimas + 1) / 10
    return float(valor_decimal.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


# ==========================================
# LECTURA SULLAIR (Conexión TCP Única Optimizada)
# ==========================================
GATEWAY_IP_SULLAIR = config.IP_SULLAIR_COMPRESSOR
PORT_SULLAIR = 502  # Puerto web confirmado
SLAVE_ID_SULLAIR = config.MODBUS_SLAVE_ID

ADDR_SHUTDOWN = 0
ADDR_MODE = 5
ADDR_STATE = 6
ADDR_TEMP_T1 = 7
ADDR_PRES_P1 = 10
ADDR_PRES_P2 = 11
ADDR_RUN_HI = 68
ADDR_RUN_LO = 69
ADDR_WARNA = 78
ADDR_WARNB = 79

MODE_NAMES = {0: "STOPPED", 1: "CONTINUOUS", 2: "AUTOMATIC (AUTO)"}
STATE_NAMES = {
    0: "OFF / DETENIDO",
    3: "READY (LISTO)",
    4: "ENABLED",
    5: "AUTOENABLED",
    8: "STARTING (ARRANCANDO)",
    10: "UNLOADED (EN VACÍO)",
    11: "LOADING (CARGANDO)",
    12: "FULL LOAD (PLENA CARGA)",
    13: "MODULATING (MODULANDO)",
    14: "STOPPING (PARANDO)",
}
SHUTDOWN_MAPPING = {
    0: "SIN FALLAS DE PARADA",
    1: "ALTA TEMPERATURA DE DESCARGA",
    2: "SOBREPRESIÓN EN LÍNEA / SUMIDERO",
    3: "FALLA EN ARRANCADOR / SOBRECARGA MOTOR",
    4: "PARADA DE EMERGENCIA ACTIVADA",
    5: "SECUENCIA / PÉRDIDA DE FASE",
    6: "FALLA SENSOR TEMPERATURA T1",
    7: "FALLA SENSOR PRESIÓN P1 (SUMIDERO)",
    8: "FALLA SENSOR PRESIÓN P2 (LÍNEA)",
}

WARNA_BITS = {
    0x0001: "REEMPLAZAR FILTRO DE ACEITE / FLUIDO",
    0x0002: "REEMPLAZAR ELEMENTO SEPARADOR",
    0x0004: "REEMPLAZAR FILTRO DE AIRE",
    0x0008: "REALIZAR ANÁLISIS DE ACEITE",
    0x0010: "REEMPLAZAR ACEITE / FLUIDO COMPLETO",
    0x0020: "MANTENIMIENTO PREVENTIVO PROGRAMADO",
}
WARNB_BITS = {
    0x0008: "ADVERTENCIA: ALTA TEMPERATURA T1",
    0x0020: "ADVERTENCIA: ALTA TEMPERATURA T2",
}


def decodificar_alertas_sullair(val_warna, val_warnb):
    alertas = []
    if val_warna and val_warna > 0:
        for bit_mask, desc in WARNA_BITS.items():
            if val_warna & bit_mask:
                alertas.append(f"🟡 MANTENIMIENTO: {desc}")
    if val_warnb and val_warnb > 0:
        for bit_mask, desc in WARNB_BITS.items():
            if val_warnb & bit_mask:
                alertas.append(f"🟡 ADVERTENCIA: {desc}")
    if not alertas:
        alertas.append("🟢 SIN ADVERTENCIAS NI MANTENIMIENTOS PENDIENTES")
    return alertas


def ciclo_sullair():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Abrimos la conexión TCP con un timeout más generoso (4.0 segundos)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(4.0)
    try:
        s.connect((GATEWAY_IP_SULLAIR, PORT_SULLAIR))
    except Exception as e:
        print(f"⚠️ [SULLAIR] Falla de conexión TCP: {e}", flush=True)
        return

    def _leer_interno(addr):
        req = bytes(
            [
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x06,
                SLAVE_ID_SULLAIR,
                0x04,
                (addr >> 8) & 0xFF,
                addr & 0xFF,
                0x00,
                0x01,
            ]
        )
        # Damos hasta 2 intentos por cada registro individual por si el conversor titubea
        for intento in range(2):
            try:
                s.sendall(req)
                resp = s.recv(256)
                if len(resp) >= 9 and resp[7] == 0x04:
                    return int.from_bytes(resp[9:11], byteorder="big")
            except Exception:
                time.sleep(0.2)

        print(f"⚠️ [SULLAIR] Falló lectura del registro {addr}", flush=True)
        return None

    try:
        sdc_code = _leer_interno(ADDR_SHUTDOWN)
        time.sleep(0.08)
        modo_raw = _leer_interno(ADDR_MODE)
        time.sleep(0.08)
        estado_raw = _leer_interno(ADDR_STATE)
        time.sleep(0.08)
        temp_raw = _leer_interno(ADDR_TEMP_T1)
        time.sleep(0.08)
        p_sumidero_raw = _leer_interno(ADDR_PRES_P1)
        time.sleep(0.08)
        p_linea_raw = _leer_interno(ADDR_PRES_P2)
        time.sleep(0.08)
        run_hi = _leer_interno(ADDR_RUN_HI)
        time.sleep(0.08)
        run_lo = _leer_interno(ADDR_RUN_LO)
        time.sleep(0.08)
        warna_raw = _leer_interno(ADDR_WARNA)
        time.sleep(0.08)
        warnb_raw = _leer_interno(ADDR_WARNB)
    finally:
        s.close()

    lecturas_criticas = (temp_raw, p_sumidero_raw, p_linea_raw, run_hi, run_lo)
    if any(valor is None for valor in lecturas_criticas):
        print("⚠️ [SULLAIR] Muestra descartada por lectura incompleta.", flush=True)
        return

    temp_c = ((temp_raw - 512) / 28.8) if temp_raw else 0.0
    p_linea_bar = ajustar_presion((p_linea_raw / 232.0) if p_linea_raw else 0.0)
    p_sumidero_bar = ajustar_presion(
        (p_sumidero_raw / 232.0) if p_sumidero_raw else 0.0
    )
    separator_filter_dp = max(0.0, p_sumidero_bar - p_linea_bar)
    horas_marcha = int(
        (((run_hi * 32768) + run_lo) / 60.0)
        if (run_hi is not None and run_lo is not None)
        else 0
    )

    datos_telemetria = {
        "pressure_bar": p_linea_bar,
        "pressure_sink_bar": p_sumidero_bar,
        "separator_filter_dp": separator_filter_dp,
        "temperature_c": temp_c,
        "run_hours": horas_marcha,
        "operating_state": STATE_NAMES.get(estado_raw, f"DESCONOCIDO ({estado_raw})"),
        "shutdown_code": sdc_code,
        "warnings": json.dumps(
            decodificar_alertas_sullair(warna_raw, warnb_raw), ensure_ascii=False
        ),
    }

    try:
        save_reading(
            machine_name="SULLAIR_COMPRESSOR",
            data=datos_telemetria,
            timestamp=timestamp,
        )
        print("✅ [SULLAIR] Lectura guardada en DB.", flush=True)
    except Exception as exc:
        print(f"⚠️ Error al guardar Sullair: {exc}", flush=True)

    # Vuelve el panel visual a la consola
    print("=" * 65)
    print("📊 TELEMETRÍA SULLAIR SE1507NEW")
    print("=" * 65)
    print(f"Timestamp / Hora  : {timestamp}")
    print(f"Estado Operativo  : {datos_telemetria['operating_state']}")
    print(f"Temperatura T1    : {datos_telemetria['temperature_c']:.1f} °C")
    print(f"Presión Línea P2  : {datos_telemetria['pressure_bar']:.1f} bar")
    print(f"Presión Sumid. P1 : {datos_telemetria['pressure_sink_bar']:.1f} bar")
    print(f"Delta P Separador : {datos_telemetria['separator_filter_dp']:.1f} bar")
    print(f"Horas de Marcha   : {datos_telemetria['run_hours']:,} hs")
    print("=" * 65)


# ==========================================
# LECTURA AERCOM (Pymodbus)
# ==========================================
def _leer_reg_aercom(client, address):
    try:
        respuesta = client.read_holding_registers(
            address=address, count=1, device_id=AERCOM_DEVICE_ID
        )
        if not respuesta.isError() and respuesta.registers:
            return respuesta.registers[0]
    except Exception:
        pass
    return None


def _convertir_contador_horas_aercom(reg_high, reg_low):
    if reg_high is None or reg_low is None:
        return None
    val_low = int.from_bytes(reg_high.to_bytes(2, "little"), "big")
    val_high = int.from_bytes(reg_low.to_bytes(2, "little"), "big")
    minutos_totales = (val_high * 65536) + val_low
    return round(minutos_totales / 60.0, 1)


def leer_aercom():
    client = ModbusTcpClient(host=AERCOM_IP, port=AERCOM_PORT, timeout=2.0, retries=1)
    if not client.connect():
        return None

    try:
        raw_state = _leer_reg_aercom(client, AERCOM_REG_STATE)
        raw_alarm = _leer_reg_aercom(client, AERCOM_REG_ALARM)
        raw_temp = _leer_reg_aercom(client, AERCOM_REG_TEMPERATURE)
        raw_pres = _leer_reg_aercom(client, AERCOM_REG_PRESSURE)
        raw_pres_sep = _leer_reg_aercom(client, AERCOM_REG_SEPARATOR_PRESSURE)
        high_hrs = _leer_reg_aercom(client, AERCOM_REG_RUN_HOURS_HIGH)
        low_hrs = _leer_reg_aercom(client, AERCOM_REG_RUN_HOURS_LOW)
        high_load_hrs = _leer_reg_aercom(client, AERCOM_REG_LOAD_HOURS_HIGH)
        low_load_hrs = _leer_reg_aercom(client, AERCOM_REG_LOAD_HOURS_LOW)

        if None in (raw_state, raw_pres, raw_temp, raw_alarm):
            return None

        alarm_description = AERCOM_ALARMS.get(raw_alarm, f"ALARMA_CODIGO_{raw_alarm}")
        warnings = [] if raw_alarm == 0 else [alarm_description]

        run_hours = _convertir_contador_horas_aercom(high_hrs, low_hrs)
        load_hours = _convertir_contador_horas_aercom(high_load_hrs, low_load_hrs)

        pressure_bar = raw_pres / 10.0
        separator_pressure_bar = (
            raw_pres_sep / 10.0 if raw_pres_sep is not None else 0.0
        )
        separator_filter_dp = max(0.0, round(separator_pressure_bar - pressure_bar, 2))

        datos_aercom = {
            "pressure_bar": pressure_bar,
            "pressure_sink_bar": separator_pressure_bar,
            "separator_filter_dp": separator_filter_dp,
            "temperature_c": raw_temp / 10.0,
            "run_hours": run_hours,
            "load_hours": load_hours,
            "operating_state": AERCOM_STATES.get(
                raw_state, f"ESTADO_DESCONOCIDO_{raw_state}"
            ),
            "shutdown_code": raw_alarm,
            "warnings": json.dumps(warnings, ensure_ascii=False),
        }
        return datos_aercom
    except Exception:
        return None
    finally:
        client.close()


def monitorear_aercom():
    print("[AERCOM] Monitor en segundo plano iniciado.", flush=True)
    while True:
        datos_aercom = leer_aercom()
        if datos_aercom is not None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                save_reading(
                    machine_name="AERCOM_22P",
                    data=datos_aercom,
                    timestamp=timestamp,
                )
                print("✅ [AERCOM] Lectura guardada en DB.", flush=True)

                # Panel visual para la consola
                print("=" * 65)
                print("📊 TELEMETRÍA AERCOM FRECON 22P")
                print("=" * 65)
                print(f"Timestamp / Hora  : {timestamp}")
                print(
                    f"Estado Operativo  : {datos_aercom.get('operating_state', 'N/A')}"
                )
                print(
                    f"Temperatura       : {datos_aercom.get('temperature_c', 0):.1f} °C"
                )
                print(
                    f"Presión Línea     : {datos_aercom.get('pressure_bar', 0):.1f} bar"
                )
                print(
                    f"Presión Separador : {datos_aercom.get('pressure_sink_bar', 0):.1f} bar"
                )
                print(
                    f"Delta P Separador : {datos_aercom.get('separator_filter_dp', 0):.1f} bar"
                )
                print(f"Horas de Marcha   : {datos_aercom.get('run_hours', 0):,} hs")
                print(f"Horas en Carga    : {datos_aercom.get('load_hours', 0):,} hs")
                print(f"Alarmas Activas   : {datos_aercom.get('shutdown_code', 0)}")
                print("=" * 65)

            except Exception as exc:
                print(f"⚠️ Error al guardar telemetría Aercom: {exc}", flush=True)

        time.sleep(AERCOM_POLLING_INTERVAL)


# ==========================================
# BLOQUE PRINCIPAL
# ==========================================
if __name__ == "__main__":
    print("🚀 Iniciando Sistema Colector IIoT (Sullair + Aercom)...")

    # Hilo en segundo plano para el Aercom
    threading.Thread(
        target=monitorear_aercom,
        name="AercomTelemetryThread",
        daemon=True,
    ).start()

    # Bucle principal para el Sullair
    while True:
        try:
            ciclo_sullair()
            time.sleep(getattr(config, "POLLING_INTERVAL", 60))
        except KeyboardInterrupt:
            print("\nLectura detenida por el usuario.")
            break
        except Exception as e:
            print(f"⚠️ Error en bucle principal Sullair: {e}", flush=True)
            time.sleep(10)
