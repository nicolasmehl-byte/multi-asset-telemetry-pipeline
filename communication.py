# communication.py
import logging

from pyModbusTCP.client import ModbusClient

import config

logger = logging.getLogger(__name__)


def read_machine_data(host, port=None, start_address=None):
    """Conecta a un activo Modbus y lee registros de forma robusta.

    Devuelve un diccionario con claves: 'pressure_bar', 'temperature_c', 'run_hours'
    (estas claves coinciden con las columnas de la BD y con el resto del pipeline).
    """
    port = port or config.PORT_MODBUS
    start_address = (
        start_address if start_address is not None else config.REG_START_ADDRESS
    )

    client = ModbusClient(
        host=host,
        port=port,
        unit_id=getattr(config, "MODBUS_SLAVE_ID", 1),
        auto_open=True,
        auto_close=True,
        # Sin timeout explícito, pyModbusTCP espera hasta ~30s por defecto antes
        # de darse por vencido. Con varios equipos y polling cada 10s, una sola
        # máquina caída podía atrasar la lectura de las demás en el mismo ciclo.
        # Con MODBUS_TIMEOUT (2s por defecto) el programa detecta rápido que
        # está offline y sigue de largo.
        timeout=getattr(config, "MODBUS_TIMEOUT", 2.0),
    )

    try:
        registers = client.read_holding_registers(start_address, config.REG_COUNT)
    except Exception as e:
        logger.warning("Modbus read error for %s:%s -> %s", host, port, e)
        return None

    if not registers or len(registers) < config.REG_COUNT:
        logger.warning(
            "Incomplete or empty Modbus response from %s:%s -> %s",
            host,
            port,
            registers,
        )
        return None

    try:
        # Reconstruimos 32 bits para horas de marcha combinando dos registros de 16 bits:
        # (parte_alta << 16) + parte_baja. Ver config.py para los índices exactos.
        run_hours = (registers[config.IDX_RUN_HOURS_HIGH] << 16) + registers[
            config.IDX_RUN_HOURS_LOW
        ]

        return {
            "pressure_bar": registers[config.IDX_PRESSURE] / config.SCALE_PRESSURE,
            "temperature_c": registers[config.IDX_TEMPERATURE]
            / config.SCALE_TEMPERATURE,
            "run_hours": run_hours,
        }
    except Exception as e:
        logger.exception(
            "Error parsing Modbus registers from %s:%s -> %s", host, port, e
        )
        return None
