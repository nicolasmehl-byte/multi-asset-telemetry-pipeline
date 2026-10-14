"""
scan_full.py
------------

-----FINALIZADO- SE DETERMINO QUE EL SLAVE ID ES 1.----

Barrido completo de Slave IDs Modbus (1 a 247) contra el HF2211 en modo
## Modbus TCP nativo (Protocol=Modbus, puerto 502, Half Duplex, 19200-8-E-1).

- Abre una conexión NUEVA por cada ID (evita que un corte de socket a
  mitad de camino tire abajo todo el barrido).
- Si un ID responde con función 0x03 (lectura OK) o 0x83 (excepción
  Modbus), lo registra igual — una excepción Modbus significa que el
  ID SÍ existe, solo que el registro/función no es válido para ese
  dispositivo.
- Guarda todo en scan_log.csv para que quede documentado, no solo en
  pantalla.

Uso:
    python scan_full.py
"""

import csv
import os
import socket
import time

GATEWAY_IP = "192.168.0.128"  # confirmá que sea la IP real actual
PORT = 502
START_REG = 258
COUNT = 2
MAX_ID = 247
TIMEOUT = 1.0
LOG_FILE = "scan_log.csv"


def consultar(ip, port, slave_id, start_reg, count, timeout):
    req = bytes(
        [
            0x00,
            0x01,  # Transaction ID
            0x00,
            0x00,  # Protocol ID
            0x00,
            0x06,  # Longitud
            slave_id,  # Unit ID
            0x03,  # FC03 Read Holding Registers
            (start_reg >> 8) & 0xFF,
            start_reg & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
        ]
    )

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.sendall(req)
        resp = s.recv(256)
    finally:
        s.close()

    return resp


def registrar(writer, slave_id, estado, detalle, valores=None):
    writer.writerow(
        [time.strftime("%Y-%m-%d %H:%M:%S"), slave_id, estado, detalle, valores]
    )


def main():
    existe = os.path.isfile(LOG_FILE)
    encontrados = []

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        if not existe:
            writer.writerow(["timestamp", "slave_id", "estado", "detalle", "valores"])

        print(f"Escaneando IDs 1 a {MAX_ID} contra {GATEWAY_IP}:{PORT}...\n")

        for slave_id in range(1, MAX_ID + 1):
            print(f"Probando ID {slave_id:3d}...", end=" ", flush=True)
            try:
                resp = consultar(GATEWAY_IP, PORT, slave_id, START_REG, COUNT, TIMEOUT)

                if not resp or len(resp) < 8:
                    print("sin respuesta")
                    continue

                func_code = resp[7]

                if func_code == 0x03:
                    payload = resp[9 : 9 + COUNT * 2]
                    valores = [
                        int.from_bytes(payload[i : i + 2], byteorder="big")
                        for i in range(0, len(payload), 2)
                    ]
                    print(f"🎉 RESPUESTA VÁLIDA -> {valores}")
                    registrar(writer, slave_id, "OK", resp.hex(" ").upper(), valores)
                    encontrados.append((slave_id, "OK", valores))

                elif func_code == 0x83:
                    codigo_err = resp[8] if len(resp) > 8 else None
                    print(f"⚠️ excepción Modbus (código {codigo_err}) -> el ID existe")
                    registrar(writer, slave_id, "EXCEPCION", f"codigo={codigo_err}")
                    encontrados.append((slave_id, "EXCEPCION", codigo_err))

                else:
                    print(f"respuesta rara (func={func_code}): {resp.hex(' ').upper()}")
                    registrar(writer, slave_id, "RARO", resp.hex(" ").upper())

            except TimeoutError:
                print("timeout")
            except ConnectionResetError:
                print("⚠️ conexión cortada por el gateway")
                registrar(writer, slave_id, "RESET", "-")
                time.sleep(0.5)
            except Exception as e:
                print(f"error: {e}")
                registrar(writer, slave_id, "ERROR", str(e))

            time.sleep(0.05)

    print("\n" + "=" * 50)
    if encontrados:
        print(f"📝 IDs que respondieron algo ({len(encontrados)}):")
        for slave_id, estado, detalle in encontrados:
            print(f"   ID {slave_id}: {estado} -> {detalle}")
    else:
        print("❌ Ningún ID respondió nada (ni OK ni excepción) en todo el rango.")
    print(f"📄 Detalle completo guardado en {LOG_FILE}")
    print("=" * 50)


if __name__ == "__main__":
    main()
