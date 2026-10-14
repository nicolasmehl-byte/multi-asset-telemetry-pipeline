import time

from leer_telemetria import leer_registro

for muestra in range(3):
    print(f"\nMUESTRA {muestra + 1}")
    for registro in range(301):
        valor = leer_registro(registro)
        if valor is not None:
            print(f"Registro {registro:03d}: {valor:5d} | 0x{valor:04X}")
        time.sleep(0.02)

    if muestra < 2:
        print("\nEsperando cambio de carga...")
        time.sleep(10)
