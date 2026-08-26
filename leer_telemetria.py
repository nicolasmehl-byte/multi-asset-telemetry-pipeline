import json
import socket
import time
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

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
    while True:
        try:
            main()
            time.sleep(20)  # Refresca cada 20 segundos
        except KeyboardInterrupt:
            print("\nLectura detenida por el usuario.")
            break
