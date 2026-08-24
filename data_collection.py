
import socket
import time

# Se leer todos los registros de 0 a 100 para determinar cuales responden y cuales no. 
# Esto nos permite determinar el mapa de memoria del Sullair.
# Es un script de prueba. 
GATEWAY_IP = "192.168.0.128"
PORT = 502
SLAVE_ID = 1  # ID Confirmado del Sullair

# Rangos de registros a probar (bloques de 10)
START_REG = 0
END_REG = 100

print(
    f"🚀 Explorando mapa de memoria del Sullair (ID {SLAVE_ID}) entre registros {START_REG} y {END_REG}...\n"
)


def read_register(fc, reg_addr):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect((GATEWAY_IP, PORT))

        # Trama Modbus TCP para leer 1 registro
        req = bytes(
            [
                0x00,
                0x01,  # Transaction ID
                0x00,
                0x00,  # Protocol ID
                0x00,
                0x06,  # Length
                SLAVE_ID,  # Unit ID (1)
                fc,  # Function Code (3 o 4)
                (reg_addr >> 8) & 0xFF,
                reg_addr & 0xFF,  # Address
                0x00,
                0x01,  # Count: 1 registro
            ]
        )

        s.sendall(req)
        resp = s.recv(256)
        s.close()

        if resp and len(resp) >= 9:
            func_code = resp[7]
            if func_code == fc:
                # Respuesta OK: Los datos vienen a partir del byte 9
                data_val = int.from_bytes(resp[9:11], byteorder="big")
                return True, data_val
            elif func_code == (fc + 0x80):
                exception_code = resp[8]
                return False, f"Excepción {exception_code}"
        return False, "Sin respuesta"
    except Exception as e:
        return False, str(e)


# 1. Probar FC03 (Holding Registers)
print("--- Probando FC03 (Read Holding Registers) ---")
found_fc03 = 0
for reg in range(START_REG, END_REG + 1):
    success, val = read_register(3, reg)
    if success:
        print(f"✅ FC03 | Registro {reg:3d} (0x{reg:04X}): Valor = {val}")
        found_fc03 += 1
    time.sleep(0.02)

if found_fc03 == 0:
    print("❌ Ningún registro respondió en FC03 en este rango.\n")

# 2. Probar FC04 (Read Input Registers)
print("\n--- Probando FC04 (Read Input Registers) ---")
found_fc04 = 0
for reg in range(START_REG, END_REG + 1):
    success, val = read_register(4, reg)
    if success:
        print(f"✅ FC04 | Registro {reg:3d} (0x{reg:04X}): Valor = {val}")
        found_fc04 += 1
    time.sleep(0.02)

if found_fc04 == 0:
    print("❌ Ningún registro respondió en FC04 en este rango.\n")