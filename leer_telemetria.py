import json
import socket
import threading
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from pymodbus.client import ModbusTcpClient

import config
from database import save_reading

GATEWAY_IP = config.IP_SULLAIR_COMPRESSOR
PORT = config.PORT_MODBUS
SLAVE_ID = config.MODBUS_SLAVE_ID

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

AERCOM_IP = config.IP_AERCOM_22P
AERCOM_PORT = 502
AERCOM_POLLING_INTERVAL = getattr(config, "POLLING_INTERVAL", 60)
AERCOM_TIMEOUT = 2.0
AERCOM_DEVICE_ID = 1
AERCOM_REGISTER_RETRIES = 2

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
    5: "DESACELERANDO POR PARADA REMOTA",
    6: "DESACELERANDO POR TIMER",
    7: "STANDBY / BACKUP (Presion en Set, Motor Apagado)",
    8: "ESPERA DE SEGURIDAD (Timer Wt5)",
    9: "ARRANCANDO MOTOR",
    10: "MARCHA EN VACIO (IDLE)",
    11: "EN CARGA (LOAD RUNNING)",
    12: "BLOQUEO SUAVE (30 SEG)",
    13: "BLOQUEADO POR FALLA",
    14: "TEST DE FABRICA",
}

AERCOM_ALARMS = {
    0: "Sin Alarma (OK)",
    1: "A01 - Parada de Emergencia",
    2: "A02 - Sobrecarga Termica Motor Principal",
    3: "A03 - Sobrecarga Termica Electroventilador",
    4: "A04 - Falta de Fase",
    5: "A05 - Secuencia de Fases Incorrecta",
    7: "A07 - Puerta Abierta",
    9: "A09 - Falla en Inversor / Variador",
    11: "A11 - Alta Presion de Trabajo",
    12: "A12 - Falla Sonda de Temperatura",
    13: "A13 - Alta Temperatura de Tornillo",
    14: "A14 - Baja Temperatura de Tornillo",
    15: "A15 - Falla Filtro Separador",
    18: "A18 - Black Out / Corte de Energia",
    20: "A20 - Falla Sensor PTC Motor",
    21: "A21 - Falla Alimentacion de Entradas",
    22: "A22 - Falla Generica Entrada IN7",
    25: "A25 - Presostato Filtro Separador Abierto",
    26: "A26 - Falla Transductor Presion de Trabajo",
    27: "A27 - Falla Transductor Presion Auxiliar",
    28: "A28 - Bajo Voltaje de Alimentacion",
    29: "A29 - Seguridad / Mantenimiento Vencido",
    30: "A30 - Advertencia Alta Temperatura",
    32: "A32 - Mantenimiento Bloqueante",
    33: "A33 - Error de Comunicacion RS485",
    60: "A60 - Falla en Inversor (VFD)",
    61: "A61 - Advertencia de Inversor",
    62: "A62 - Sin Comunicacion con Inversor",
}


def leer_registro(reg_addr):
    req = bytes(
        [
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x06,
            SLAVE_ID,
            0x04,
            (reg_addr >> 8) & 0xFF,
            reg_addr & 0xFF,
            0x00,
            0x01,
        ]
    )

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect((GATEWAY_IP, PORT))
        s.sendall(req)
        resp = s.recv(256)
        if len(resp) >= 9 and resp[7] == 0x04:
            return int.from_bytes(resp[9:11], byteorder="big")
    except Exception:
        pass
    finally:
        s.close()
    return None


def _leer_reg_aercom(client, address):
    """Lee un registro Aercom individual usando siempre count=1 y device_id=1."""
    for intento in range(AERCOM_REGISTER_RETRIES + 1):
        try:
            respuesta = client.read_holding_registers(
                address=address,
                count=1,
                device_id=AERCOM_DEVICE_ID,
            )
            if not respuesta.isError() and respuesta.registers:
                return respuesta.registers[0]
        except Exception:
            if intento < AERCOM_REGISTER_RETRIES:
                time.sleep(0.2)
    return None


def _convertir_contador_horas_aercom(reg_high, reg_low):
    """Corrige byte-swap y combina dos palabras de minutos como horas."""
    if reg_high is None or reg_low is None:
        return None
    val_low = int.from_bytes(reg_high.to_bytes(2, "little"), "big")
    val_high = int.from_bytes(reg_low.to_bytes(2, "little"), "big")
    minutos_totales = (val_high * 65536) + val_low
    return round(minutos_totales / 60.0, 1)


def leer_aercom():
    """Lee una muestra Aercom usando el mapa oficial del Logik 26-S."""
    client = ModbusTcpClient(
        host=AERCOM_IP,
        port=AERCOM_PORT,
        timeout=AERCOM_TIMEOUT,
        retries=0,
    )
    print(f"[AERCOM] Conectando a {AERCOM_IP}:{AERCOM_PORT}...", flush=True)

    if not client.connect():
        print("[AERCOM] Error de conexion TCP.", flush=True)
        client.close()
        return None

    try:
        print("[AERCOM] Conexion OK. Leyendo mapa oficial...", flush=True)
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
            print("[AERCOM] Faltan datos criticos en la lectura Modbus.", flush=True)
            return None

        alarm_description = AERCOM_ALARMS.get(
            raw_alarm,
            f"ALARMA_CODIGO_{raw_alarm}",
        )
        warnings = [] if raw_alarm == 0 else [alarm_description]
        run_hours = None
        if low_hrs is not None and high_hrs is not None:
            run_hours = _convertir_contador_horas_aercom(high_hrs, low_hrs)
        load_hours = None
        if low_load_hrs is not None and high_load_hrs is not None:
            load_hours = _convertir_contador_horas_aercom(
                high_load_hrs,
                low_load_hrs,
            )
        pressure_bar = raw_pres / 10.0
        separator_pressure_bar = (
            raw_pres_sep / 10.0 if raw_pres_sep is not None else None
        )
        separator_filter_dp = 0.0

        datos_aercom = {
            "pressure_bar": pressure_bar,
            "pressure_sink_bar": separator_pressure_bar,
            "separator_filter_dp": separator_filter_dp,
            "temperature_c": raw_temp / 10.0,
            "run_hours": run_hours,
            "load_hours": load_hours,
            "operating_state": AERCOM_STATES.get(
                raw_state,
                f"ESTADO_DESCONOCIDO_{raw_state}",
            ),
            "shutdown_code": raw_alarm,
            "warnings": json.dumps(warnings, ensure_ascii=False),
        }
        print(
            "[AERCOM] Datos recibidos: "
            f"Temperatura {datos_aercom['temperature_c']:.1f} °C | "
            f"Presion {datos_aercom['pressure_bar']:.1f} bar | "
            f"Estado {datos_aercom['operating_state']}",
            flush=True,
        )
        return datos_aercom
    except Exception as exc:
        print(f"[AERCOM] Excepcion durante la lectura: {exc}", flush=True)
        return None
    finally:
        client.close()


def monitorear_aercom():
    """Lee y guarda Aercom sin detener el bucle de lectura del Sullair."""
    print("[AERCOM] Monitor iniciado.", flush=True)
    while True:
        datos_aercom = leer_aercom()
        if datos_aercom is not None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                print("[AERCOM] Guardando lectura...", flush=True)
                save_reading(
                    machine_name="AERCOM_22P",
                    data=datos_aercom,
                    timestamp=timestamp,
                )
                print("[AERCOM] Lectura guardada correctamente.", flush=True)
            except Exception as exc:
                print(
                    f"⚠️ No se pudo guardar telemetria del Aercom: {exc}",
                    flush=True,
                )

        print(
            f"[AERCOM] Proxima lectura en {AERCOM_POLLING_INTERVAL} segundos.",
            flush=True,
        )
        time.sleep(AERCOM_POLLING_INTERVAL)


def decodificar_alertas_reales(val_warna, val_warnb):
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


def ajustar_presion(valor):
    """Trunca o redondea la presion a una decimal segun sus centesimas."""
    valor_decimal = Decimal(str(valor))
    centesimas = int(valor_decimal * 100)
    decimas = centesimas // 10
    resto = centesimas % 10

    if resto <= 6:
        return decimas / 10
    if resto >= 8:
        return (decimas + 1) / 10
    return float(valor_decimal.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def main():
    # 📌 Captura de Fecha y Hora en Tiempo Real (ISO / Formato Estándar)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Lecturas Modbus
    sdc_code = leer_registro(ADDR_SHUTDOWN)
    time.sleep(0.03)
    modo_raw = leer_registro(ADDR_MODE)
    time.sleep(0.03)
    estado_raw = leer_registro(ADDR_STATE)
    time.sleep(0.03)
    temp_raw = leer_registro(ADDR_TEMP_T1)
    time.sleep(0.03)
    p_sumidero_raw = leer_registro(ADDR_PRES_P1)
    time.sleep(0.03)
    p_linea_raw = leer_registro(ADDR_PRES_P2)
    time.sleep(0.03)
    run_hi = leer_registro(ADDR_RUN_HI)
    time.sleep(0.03)
    run_lo = leer_registro(ADDR_RUN_LO)
    time.sleep(0.03)
    warna_raw = leer_registro(ADDR_WARNA)
    time.sleep(0.03)
    warnb_raw = leer_registro(ADDR_WARNB)

    # No guardar una muestra parcial: un timeout Modbus no debe convertirse en ceros.
    lecturas_criticas = (
        temp_raw,
        p_sumidero_raw,
        p_linea_raw,
        run_hi,
        run_lo,
    )
    if any(valor is None for valor in lecturas_criticas):
        print("⚠️ Muestra descartada: lectura Modbus incompleta.")
        return

    # Conversiones
    temp_c = ((temp_raw - 512) / 28.8) if temp_raw else 0.0
    p_linea_bar = ajustar_presion((p_linea_raw / 232.0) if p_linea_raw else 0.0)
    p_sumidero_bar = ajustar_presion(
        (p_sumidero_raw / 232.0) if p_sumidero_raw else 0.0
    )
    horas_marcha = int(
        (((run_hi * 32768) + run_lo) / 60.0)
        if (run_hi is not None and run_lo is not None)
        else 0
    )

    modo_str = MODE_NAMES.get(modo_raw, f"DESCONOCIDO ({modo_raw})")
    estado_str = STATE_NAMES.get(estado_raw, f"DESCONOCIDO ({estado_raw})")
    text_shutdown = SHUTDOWN_MAPPING.get(sdc_code, f"CÓDIGO DESCONOCIDO ({sdc_code})")
    lista_alertas = decodificar_alertas_reales(warna_raw, warnb_raw)

    # Guarda en la nube y utiliza SQLite automáticamente si falla la conexión.
    datos_telemetria = {
        "pressure_bar": p_linea_bar,
        "pressure_sink_bar": p_sumidero_bar,
        "temperature_c": temp_c,
        "run_hours": horas_marcha,
        "operating_state": estado_str,
        "shutdown_code": sdc_code,
        "warnings": json.dumps(lista_alertas, ensure_ascii=False),
    }

    try:
        save_reading(
            machine_name="SULLAIR_COMPRESSOR",
            data=datos_telemetria,
            timestamp=timestamp,
        )
    except Exception as exc:
        print(f"⚠️ No se pudo persistir la telemetría: {exc}")

    # Salida por pantalla
    print("=" * 65)
    print("📊 TELEMETRÍA SULLAIR SE1507NEW")
    print("=" * 65)
    print(f"Timestamp / Hora  : {timestamp}")
    print(f"Modo de Operación : {modo_str}")
    print(f"Estado Operativo  : {estado_str}")
    print(f"Temperatura T1    : {temp_c:.1f} °C")
    print(f"Presión Línea P2  : {p_linea_bar:.1f} bar")
    print(f"Presión Sumid. P1 : {p_sumidero_bar:.1f} bar")
    print(f"Horas de Marcha   : {horas_marcha:,} hs")

    print("\n" + "=" * 65)
    print("🚨 ESTADO DE FALLAS Y ADVERTENCIAS")
    print("=" * 65)

    if sdc_code == 0:
        print(f"• Falla de Parada : 🟢 {text_shutdown}")
    else:
        print(f"• Falla de Parada : 🔴 [CÓDIGO {sdc_code}] {text_shutdown}")

    print("• Advertencias    :")
    for alt in lista_alertas:
        print(f"   {alt}")

    print("=" * 65)


# Al final del archivo leer_telemetria.py:

if __name__ == "__main__":
    threading.Thread(
        target=monitorear_aercom,
        name="AercomTelemetry",
        daemon=True,
    ).start()

    while True:
        try:
            main()
            time.sleep(getattr(config, "POLLING_INTERVAL", 60))
        except KeyboardInterrupt:
            print("\nLectura detenida por el usuario.")
            break
