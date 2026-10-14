import time

from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.0.130", port=502, timeout=2)


def leer_reg(client, addr):
    res = client.read_holding_registers(address=addr, count=1, device_id=1)
    return res.registers[0] if not res.isError() else 0


if client.connect():
    print("🎯 Lectura con Direcciones Oficiales del Manual (Hex -> Dec):\n")
    try:
        while True:
            # Direcciones convertidas de Hexadecimal a Decimal
            raw_temp = leer_reg(client, 1029)  # 0x0405: Temp Screw
            raw_pres = leer_reg(client, 1030)  # 0x0406: Press Work
            raw_stat = leer_reg(client, 1025)  # 0x0400: State Internal

            temp = raw_temp / 10.0
            presion = raw_pres / 10.0

            print(
                f"🌡️ Temp Principal (Reg 1029): {temp:4.1f} °C  |  "
                f"💨 Presión Línea (Reg 1030): {presion:4.1f} bar  |  "
                f"🔄 Estado (Reg 1024): {raw_stat}"
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nPrueba finalizada.")
    client.close()
else:
    print("❌ Sin conexión TCP con 192.168.0.130")
