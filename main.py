import socket
import time

GATEWAY_IP = "192.168.0.128"
PORT = 8899
SULLAIR_ID = 16


def calc_crc(data):
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder="little")


# Probamos leer bloques de 2, 4 y 10 registros desde la dirección 258 y 256
PRUEBAS = [
    {"addr": 258, "count": 2, "fc": 0x03},
    {"addr": 258, "count": 2, "fc": 0x04},
    {"addr": 256, "count": 10, "fc": 0x03},
    {"addr": 256, "count": 10, "fc": 0x04},
    {"addr": 258, "count": 10, "fc": 0x03},
]

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    s.connect((GATEWAY_IP, PORT))
    print(
        f"✅ Conectado a {GATEWAY_IP}:{PORT}. Probando bloque en Dirección 258 / ID {SULLAIR_ID}...\n"
    )

    exito = False
    for p in PRUEBAS:
        addr = p["addr"]
        count = p["count"]
        fc = p["fc"]
        fc_str = "FC03" if fc == 0x03 else "FC04"

        req = (
            bytes([SULLAIR_ID, fc])
            + addr.to_bytes(2, byteorder="big")
            + count.to_bytes(2, byteorder="big")
        )
        req += calc_crc(req)

        # Limpiamos buffer
        s.settimeout(0.1)
        try:
            s.recv(1024)
        except TimeoutError:
            pass

        print(
            f"Consultando Reg {addr} (Cant: {count}, {fc_str})...",
            end=" ",
            flush=True,
        )
        s.sendall(req)
        time.sleep(0.4)

        s.settimeout(0.8)
        try:
            data = s.recv(1024)
            if data:
                hex_str = data.hex(" ").upper()

                # Trama correcta: ID 16 + FC + Cantidad Bytes (count * 2)
                expected_bytes = 3 + (count * 2) + 2
                if len(data) >= 7 and data[0] == SULLAIR_ID and data[1] == fc:
                    print("\n\n🎉 ¡¡¡ÉXITO TOTAL Y DATOS VALIDOS RECIBIDOS!!! 🎉")
                    print(f"    Trama Modbus HEX: {hex_str}")

                    # Decodificamos el primer registro
                    val1 = int.from_bytes(data[3:5], byteorder="big")
                    print(f"    👉 VALOR LEÍDO DEL COMPRESOR (Reg {addr}): {val1}")
                    exito = True
                    break
                else:
                    print(f"Respuesta ({len(data)} bytes): {hex_str}")
            else:
                print("Sin respuesta (Timeout).")
        except TimeoutError:
            print("Timeout.")

    s.close()
except Exception as e:
    print(f"Error de conexión: {e}")
