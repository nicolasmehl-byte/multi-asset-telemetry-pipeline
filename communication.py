# communication.py
from pyModbusTCP.client import ModbusClient

def read_machine_data(host, port, start_address):
    """Connects to a specific Modbus target and reads 4 telemetric variables."""
    client = ModbusClient(host=host, port=port, auto_open=True, auto_close=True)
    
    # Reads 4 consecutive registers: [Pressure, Temp, Run Hours, Current]
    registers = client.read_holding_registers(start_address, 4)
    
    if registers:
        return {
            "pressure": registers[0] / 10.0,   # Scale: 66 -> 6.6 Bar
            "temperature": registers[1],       # Int: °C
            "run_hours": registers[2],         # Int: Hours of operation
            "current": registers[3] / 10.0     # Scale: 145 -> 14.5 Amps
        }
    return None