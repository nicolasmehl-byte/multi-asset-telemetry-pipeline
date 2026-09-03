"""
diagnostico_logik26s.py
------------------------

Herramienta de reconocimiento para el controlador Logik 26-S (Aercom 22P).

El manual disponible NO trae la tabla de registros Modbus (esa tabla es un
documento aparte, "Logik26S MODBUS Data", específico por OEM/firmware, que
Logika Control no publica de forma abierta).

Como ya tenés la comunicación funcionando (baud rate, paridad, gateway OK),
el camino más rápido es reconstruir el mapa a mano:

  1. Este script lee un bloque de registros consecutivos (FC03 y FC04).
  2. Vos comparás cada valor crudo contra lo que la pantalla del Logik 26-S
     muestra EN ESE MOMENTO (presión, temperatura, horas, estado).
  3. Anotás qué registro corresponde a qué variable y probás la escala:
       - Si el crudo es ~10x el valor mostrado -> probablemente x0.1
       - Si es un valor "raro" tipo cuentas ADC -> hay offset/factor,
         como en el Sullair: temp = (raw - 512) / 28.8, presión = raw / 232
       - Probá también con signo (registros pueden venir como int16 con
         complemento a dos si el valor real puede ser negativo).

Uso:
    python diagnostico_logik26s.py
"""

import socket
import time

# ============================================================
# CONFIGURACIÓN - AJUSTAR SEGÚN TU GATEWAY
# ============================================================
GATEWAY_IP = "192.168.0.130"  # <-- poné la IP real del conversor del Aercom
PORT = 502  # 502 si el conversor hace Modbus TCP nativo
SLAVE_ID = 1  # Modbus address configurado en el parámetro C08 del Logik26S

START_REG = 0
END_REG = 60  # rango a barrer; ampliar si hace falta
TIMEOUT = 1.0
DELAY_ENTRE_LECTURAS = 0.05


def leer_registro(fc, reg_addr):
    """Lee un registro (FC03 Holding o FC04 Input) usando Modbus TCP."""
    req = bytes(
        [
            0x00,
            0x01,  # Transaction ID
            0x00,
            0x00,  # Protocol ID
            0x00,
            0x06,  # Length
            SLAVE_ID,
            fc,
            (reg_addr >> 8) & 0xFF,
            reg_addr & 0xFF,
            0x00,
            0x01,  # Count: 1 registro
        ]
    )
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((GATEWAY_IP, PORT))
        s.sendall(req)
        resp = s.recv(256)
        if len(resp) >= 9 and resp[7] == fc:
            raw = int.from_bytes(resp[9:11], byteorder="big")
            # Versión con signo (por si el valor real puede ser negativo,
            # por ejemplo alguna temperatura bajo cero)
            signed = raw - 0x10000 if raw >= 0x8000 else raw
            return raw, signed
        elif len(resp) >= 9 and resp[7] == (fc + 0x80):
            return None, None  # excepción Modbus: el registro no existe/no aplica
        return None, None
    except Exception:
        return None, None
    finally:
        s.close()


def barrido_completo():
    print(
        f"Barriendo registros {START_REG} a {END_REG} en {GATEWAY_IP}:{PORT} "
        f"(Slave ID {SLAVE_ID})...\n"
    )
    print(
        f"{'Reg':>4} | {'Hex':>6} | {'FC03 (crudo/con signo)':>24} | "
        f"{'FC04 (crudo/con signo)':>24}"
    )
    print("-" * 70)

    for reg in range(START_REG, END_REG + 1):
        raw3, signed3 = leer_registro(0x03, reg)
        time.sleep(DELAY_ENTRE_LECTURAS)
        raw4, signed4 = leer_registro(0x04, reg)
        time.sleep(DELAY_ENTRE_LECTURAS)

        if raw3 is None and raw4 is None:
            continue  # no responde en ninguna función, no vale la pena mostrarlo

        val3 = f"{raw3} / {signed3}" if raw3 is not None else "-"
        val4 = f"{raw4} / {signed4}" if raw4 is not None else "-"
        print(f"{reg:4d} | 0x{reg:04X} | {val3:>24} | {val4:>24}")


def monitor_registro():
    """
    Modo foco: mirás un solo registro en vivo mientras comparás con la
    pantalla del Logik 26-S. Útil una vez que sospechás cuál es (por
    ejemplo, si en el barrido viste un valor que 'se mueve' cuando cambia
    la presión o temperatura real del compresor).
    """
    reg = int(input("Registro a monitorear: "))
    fc = int(input("Función (3 = Holding, 4 = Input): "))
    print("Ctrl+C para salir.\n")
    try:
        while True:
            raw, signed = leer_registro(fc, reg)
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] Reg {reg} (FC{fc:02d}): crudo={raw}  con_signo={signed}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nMonitor detenido.")


if __name__ == "__main__":
    print("=== Diagnóstico Modbus - Logik 26-S (Aercom 22P) ===")
    print("1) Barrido completo de registros")
    print("2) Monitorear un registro puntual en vivo")
    opcion = input("Elegí una opción (1/2): ").strip()

    if opcion == "2":
        monitor_registro()
    else:
        barrido_completo()
