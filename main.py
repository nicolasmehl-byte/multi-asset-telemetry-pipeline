# main.py
import logging
import time  # Librería nativa para manejar las esperas y tiempos (sleep).
from datetime import (
    datetime,  # Librería nativa para capturar la fecha y hora exacta del sistema de la PC.
    timezone,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Importamos nuestros propios módulos. Python busca estos archivos en la misma carpeta.
import config
from communication import read_machine_data
from database import init_db, save_reading


def main():
    logger = logging.getLogger(__name__)
    logger.info("--- Starting Multi-Asset IIoT Data Logger (Cloud Mode) ---")

    # init_db ya no recibe db_url: la conexión se arma internamente
    # leyendo DATABASE_URL desde el entorno (ver db_connection.py).
    init_db()

    try:
        while (
            True
        ):  # "Mientras sea Verdadero" -> Un bucle infinito. El programa correrá para siempre.

            current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            for machine_name, net_config in config.EQUIPMENT.items():

                sensor_data = read_machine_data(
                    net_config["host"], net_config["port"], net_config["start_address"]
                )

                if sensor_data:
                    # 🛡️ ESCUDO SANITARIO: Protegemos la base de datos contra números basura del simulador.
                    # 99999999.0 es un valor centinela típico que devuelven simuladores/PLCs cuando
                    # el registro Modbus todavía no fue inicializado con un valor real.
                    if (
                        sensor_data.get("run_hours")
                        and sensor_data["run_hours"] > 99999999.0
                    ):
                        logger.warning(
                            "⚠️ [%s] Horas de marcha anómalas detectadas (%s h). Limpiando a 0.0...",
                            machine_name,
                            sensor_data["run_hours"],
                        )
                        sensor_data["run_hours"] = 0.0

                    save_reading(machine_name, sensor_data, current_time)

                    logger.info(
                        "[%s] %s -> Presion: %s Bar | Temp: %s °C | Hrs: %s h | I: %s A",
                        current_time,
                        machine_name,
                        sensor_data["pressure_bar"],
                        sensor_data["temperature_c"],
                        sensor_data["run_hours"],
                        sensor_data["current_amps"],
                    )
                else:
                    # CAMINO DEFENSIVO: La máquina no respondió.
                    offline_data = {
                        "pressure_bar": None,
                        "temperature_c": None,
                        "run_hours": None,
                        "current_amps": None,
                    }

                    save_reading(machine_name, offline_data, current_time)

                    logger.warning(
                        "[%s] ⚠️ ALERT: %s is OFFLINE. Failure logged. Retrying next cycle in %s seconds...",
                        current_time,
                        machine_name,
                        config.POLLING_INTERVAL,
                    )

            logger.info("%s", "-" * 70)

            time.sleep(config.POLLING_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Logger execution stopped by user. Exiting safely...")


if __name__ == "__main__":
    main()
