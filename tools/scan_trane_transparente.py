import socket
import time

from config import IP_CHILLER_TRANE

GATEWAY_IP = IP_CHILLER_TRANE
PORT = 502  # Puerto TCP del conversor en modo Server
SLAVE_ID_RANGE = range(1, 32)  # Probamos del 1 al 31 (ampliable si hace falta)
START_REG = 0  # Registro inicial
COUNT = 1  # Cantidad de registros a pedir
TIMEOUT = 1.5
INTER_QUERY_DELAY = 0.3


def calcular_crc16(data: bytes) -> bytes:
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


def escanear_trane_transparente():
    print(
        f"Escaneando Chiller Trane (Modo Transparent / Raw) contra {GATEWAY_IP}:{PORT}..."
    )
    print(
        f"Rango de Slave IDs a barrer: {SLAVE_ID_RANGE.start} al {SLAVE_ID_RANGE.stop - 1}\n"
    )

    encontrados = []

    for slave_id in SLAVE_ID_RANGE:
        # Armamos la trama Modbus RTU pura: [Slave ID][FC 03][Start Hi][Start Lo][Count Hi][Count Lo]
        pdu = bytes(
            [slave_id, 0x03, START_REG >> 8, START_REG & 0xFF, COUNT >> 8, COUNT & 0xFF]
        )
        trama_completa = pdu + calcular_crc16(pdu)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(TIMEOUT)
            s.connect((GATEWAY_IP, PORT))

            # Enviar trama cruda por el túnel transparente
            s.sendall(trama_completa)
            time.sleep(INTER_QUERY_DELAY)

            respuesta = s.recv(256)
            s.close()

            if respuesta and len(respuesta) >= 5:
                print(f"🎉 ¡ID {slave_id:3d} RESPONDIÓ! -> Hex: {respuesta.hex()}")
                encontrados.append((slave_id, respuesta))
            else:
                print(f"   ID {slave_id:3d}: Sin respuesta / Timeout")

        except TimeoutError:
            print(f"   ID {slave_id:3d}: Timeout")
        except Exception as e:
            print(f"   ID {slave_id:3d}: Error ({e})")

        time.sleep(0.05)

    print("\n" + "=" * 50)
    if encontrados:
        print(f"✅ ¡Se encontraron {len(encontrados)} IDs con respuesta!")
        for sid, resp in encontrados:
            print(f"   - Slave ID {sid}: {resp.hex()}")
    else:
        print("❌ Ningún ID respondió en este rango en modo transparente.")
    print("=" * 50)


if __name__ == "__main__":
    escanear_trane_transparente()
