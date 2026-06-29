# main.py
import time              # Librería nativa para manejar las esperas y tiempos (sleep).
from datetime import datetime  # Librería nativa para capturar la fecha y hora exacta del sistema de la PC.

# Importamos nuestros propios módulos. Python busca estos archivos en la misma carpeta.
import config
from database import init_db, save_reading
from communication import read_machine_data

def main():
    print("--- Starting Multi-Asset IIoT Data Logger (Cloud Mode) ---")
    
    # LLAMADA CORREGIDA: Pasamos la URL cloud de config.py para verificar la conexión a internet al arrancar.
    init_db(config.DATABASE_URL)
    
    # Usamos un bloque "try / except" (intentar / capturar excepción).
    # Sirve para atrapar errores o acciones del usuario y evitar que el programa se cierre con un cartel de error feo.
    try:
        while True:  # "Mientras sea Verdadero" -> Un bucle infinito. El programa correrá para siempre.
            
            # Capturamos el momento exacto en el formato estándar: Año-Mes-Día Hora:Minuto:Segundo.
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Recorremos el diccionario EQUIPMENT que está en config.py.
            # .items() nos desarma el diccionario en parejas: machine_name (la clave) y net_config (los datos de adentro).
            for machine_name, net_config in config.EQUIPMENT.items():
                
                # Le pedimos al módulo de comunicación que vaya a buscar los datos de la máquina actual
                sensor_data = read_machine_data(
                    net_config["host"], 
                    net_config["port"], 
                    net_config["start_address"]
                )
                
                # Si la máquina respondió bien (sensor_data no está vacío):
                if sensor_data:
                    # CORREGIDO: Reemplazamos config.DB_NAME por config.DATABASE_URL para insertar en la nube
                    save_reading(config.DATABASE_URL, machine_name, sensor_data, current_time)
                    
                    # Mostramos un reporte limpio en la consola para el operario que mira la pantalla.
                    print(f"[{current_time}] {machine_name} -> Presion: {sensor_data['pressure']} Bar | Temp: {sensor_data['temperature']} °C | Hrs: {sensor_data['run_hours']} h | I: {sensor_data['current']} A")
                else:
                    # CAMINO DEFENSIVO: La máquina no respondió. 
                    # Armamos un diccionario con valores None (que Postgres guardará como NULL).
                    offline_data = {
                        "pressure": None, 
                        "temperature": None, 
                        "run_hours": None, 
                        "current": None
                    }
            
                    save_reading(config.DATABASE_URL, machine_name, offline_data, current_time)
                    
                    # Avisamos con una alerta visual en la consola de la planta.
                    print(f"[{current_time}] ⚠️ ALERT: {machine_name} is OFFLINE. Failure logged. Retrying next cycle in {config.POLLING_INTERVAL} seconds...")
                    
            
            print("-" * 70)  # Imprime una línea separadora estética cada vez que termina de escanear toda la planta.
            
            # Duerme el programa los segundos configurados en config.py para no saturar el procesador de la PC.
            time.sleep(config.POLLING_INTERVAL)
            
    except KeyboardInterrupt:
        # Si el usuario aprieta CTRL + C en la terminal, Python frena el "try" y salta directo acá.
        print("\nLogger execution stopped by user. Exiting safely...")

# Si el usuario ejecutó este archivo directamente (py main.py), arrancá ejecutando la función main().
if __name__ == "__main__":
    main()