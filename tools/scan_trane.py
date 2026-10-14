"""
diagnostico_trane_ch535.py
---------------------------
Diagnóstico Modbus TCP para el Tracer CH535 (Chiller Trane) conectado vía
conversor RS485 -> WiFi/TCP al puerto J25 (BMS2).

IMPORTANTE: el baud rate y la paridad NO se configuran acá. Se configuran
en el propio conversor (su página de configuración serie). Este script solo
habla Modbus TCP contra la IP del conversor; si la config serie del conversor
no coincide con la del J25 del Tracer CH535, vas a ver timeouts o basura.

Flujo de uso:
    1. Configurá en el conversor una combinación baud/paridad candidata
       (ver lista en el script principal).
    2. Corré este script.
    3. Si no aparece ningún ID/registro válido, cambiá la combinación en el
       conversor y volvé a correr.

Aplica el mismo patrón que ya usamos en el Sullair/Aercom:
    - una sola conexión TCP persistente por combinación probada
    - flush de buffer antes de cada consulta
    - delay >= 250ms entre consultas (turnaround RS485 semidúplex)
    - escaneo de Slave ID si no se sabe la dirección
"""

import socket
import time

from config import IP_CHILLER_TRANE

# ------------------------------------------------------------------
# CONFIGURACIÓN - AJUSTAR SEGÚN TU CONVERSOR
# ------------------------------------------------------------------
GATEWAY_IP = IP_CHILLER_TRANE
PORT = 502  # puerto Modbus TCP estándar (ajustar si el conversor usa otro, ej. 8899)

SLAVE_ID_RANGE = range(
    1, 248
)  # probamos primero IDs bajos (1-20); ampliar a 247 si hace falta
START_REG = 0  # dirección de registro inicial a barrer
END_REG = 50  # dirección de registro final a barrer
INTER_QUERY_DELAY = 0.25  # segundos entre consultas (turnaround RS485 半duplex)
TIMEOUT = 1.0

# Combinación baud/paridad que tenés configurada AHORA MISMO en el conversor
# (solo para que quede en el log qué se probó; no afecta la conexión TCP)
CONFIG_SERIE_ACTUAL = "19200-8-N-1"


def calc_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder="little")


def flush_buffer(sock):
    sock.settimeout(0.1)
    try:
        sock.recv(1024)
    except TimeoutError:
        pass
    sock.settimeout(TIMEOUT)


def leer_holding_tcp(sock, slave_id, addr, count=1, transaction_id=1):
    """Lectura FC03 usando encabezado Modbus TCP (MBAP), no RTU sobre TCP."""
    pdu = bytes([slave_id, 0x03]) + addr.to_bytes(2, "big") + count.to_bytes(2, "big")
    mbap = (
        transaction_id.to_bytes(2, "big") + b"\x00\x00" + (len(pdu)).to_bytes(2, "big")
    )
    # OJO: el Unit ID va DENTRO del pdu para MBAP; lo separamos correctamente:
    # MBAP = TransID(2) + ProtoID(2)=0000 + Length(2) + UnitID(1)
    # PDU  = FC(1) + datos
    mbap = (
        transaction_id.to_bytes(2, "big")
        + b"\x00\x00"
        + (len(pdu) - 1 + 1).to_bytes(2, "big")  # length = UnitID+FC+datos
    )
    frame = mbap + pdu
    flush_buffer(sock)
    sock.sendall(frame)
    time.sleep(INTER_QUERY_DELAY)
    try:
        resp = sock.recv(256)
    except TimeoutError:
        return None, "timeout"

    if not resp or len(resp) < 9:
        return None, "sin respuesta / trama corta"

    func_code = resp[7]
    if func_code == 0x03:
        n_bytes = resp[8]
        payload = resp[9 : 9 + n_bytes]
        valores = [
            int.from_bytes(payload[i : i + 2], "big") for i in range(0, len(payload), 2)
        ]
        return valores, "OK"
    elif func_code == 0x83:
        codigo_err = resp[8] if len(resp) > 8 else None
        return None, f"excepcion_modbus({codigo_err})"
    else:
        return None, f"respuesta_rara(fc={func_code})"


def escanear_slave_ids():
    print(f"Config serie asumida en el conversor: {CONFIG_SERIE_ACTUAL}")
    print(
        f"Escaneando Slave IDs {SLAVE_ID_RANGE.start}-{SLAVE_ID_RANGE.stop - 1} "
        f"contra {GATEWAY_IP}:{PORT}, registro {START_REG}...\n"
    )

    encontrados = []
    for slave_id in SLAVE_ID_RANGE:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(TIMEOUT)
            s.connect((GATEWAY_IP, PORT))
        except Exception as e:
            print(f"❌ No se pudo conectar al conversor: {e}")
            return []

        try:
            valores, estado = leer_holding_tcp(s, slave_id, START_REG, count=2)
        finally:
            s.close()

        if estado == "OK":
            print(f"🎉 ID {slave_id:3d}: RESPUESTA VÁLIDA -> {valores}")
            encontrados.append((slave_id, valores))
        elif estado.startswith("excepcion_modbus"):
            print(
                f"⚠️  ID {slave_id:3d}: {estado} (el ID existe, pero el registro/función no)"
            )
            encontrados.append((slave_id, estado))
        else:
            print(f"   ID {slave_id:3d}: {estado}")

        time.sleep(0.05)

    return encontrados


def barrer_registros(slave_id):
    print(
        f"\nBarriendo registros {START_REG}-{END_REG} en Slave ID {slave_id} (FC03)...\n"
    )
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    s.connect((GATEWAY_IP, PORT))

    encontrados = 0
    for reg in range(START_REG, END_REG + 1):
        valores, estado = leer_holding_tcp(s, slave_id, reg, count=1)
        if estado == "OK":
            print(f"✅ Registro {reg:3d} (0x{reg:04X}): Valor = {valores[0]}")
            encontrados += 1
        time.sleep(INTER_QUERY_DELAY)

    s.close()
    if encontrados == 0:
        print("❌ Ningún registro respondió en este rango con este Slave ID.")


if __name__ == "__main__":
    resultados = escanear_slave_ids()

    print("\n" + "=" * 60)
    if resultados:
        print(f"📝 IDs que respondieron algo ({len(resultados)}):")
        for slave_id, detalle in resultados:
            print(f"   ID {slave_id}: {detalle}")

        # Si encontramos al menos un ID con respuesta OK, barremos registros
        id_ok = next((sid for sid, det in resultados if isinstance(det, list)), None)
        if id_ok is not None:
            barrer_registros(id_ok)
    else:
        print("❌ Ningún ID respondió nada en este rango.")
        print("   -> Probá cambiar la combinación baud/paridad en el conversor")
        print("      y correr el script de nuevo.")
    print("=" * 60)
