# Proyecto IIoT de monitoreo industrial

Este proyecto implementa un sistema de telemetría industrial orientado a la supervisión de activos mediante comunicación Modbus TCP, almacenamiento persistente de datos y visualización en tiempo real. Su objetivo es ofrecer una solución práctica para monitorear variables críticas de equipos y procesos industriales, con respaldo local en caso de fallas de conectividad.

## Descripción general

El sistema permite:
- leer mediciones de presión, temperatura, horas de marcha y corriente desde equipos industriales o simuladores Modbus;
- enviar los datos a una base de datos en la nube cuando la conexión está disponible;
- almacenar registros locales en SQLite como respaldo ante interrupciones de red;
- visualizar el estado operativo de la planta mediante un dashboard web construido con Streamlit.

## Arquitectura del sistema

El flujo principal del proyecto consta de tres capas:
1. Captura de datos: lectura de registros Modbus TCP desde los equipos.
2. Procesamiento y almacenamiento: normalización de variables y carga en base de datos.
3. Visualización: presentación del estado operativo y los valores históricos en un panel web.

## Estructura del proyecto

- main.py: ejecuta el proceso principal de recopilación y registro de datos.
- communication.py: gestiona la conexión y la lectura de registros Modbus TCP.
- database.py: administra la persistencia de datos en la nube y el respaldo local.
- dashboard.py: presenta la información en un tablero de monitoreo.
- config.py: centraliza la configuración de equipos, puertos, direcciones de registro y escalas.
- pass.env.example: plantilla de variables de entorno.
- requirements.txt: dependencias de Python necesarias para ejecutar el proyecto.

## Requisitos

- Python 3.10 o superior.
- Windows PowerShell o terminal compatible.
- Acceso a un equipo, PLC o simulador Modbus TCP.
- Base de datos PostgreSQL o Supabase para el modo en la nube.

## Inicio rápido

1. Crear un entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instalar las dependencias:
   ```powershell
   pip install -r requirements.txt
   ```

3. Crear el archivo de entorno:
   ```powershell
   copy pass.env.example pass.env
   ```

4. Editar pass.env con los valores reales de conexión y configuración.

5. Ajustar los parámetros de equipos en config.py si es necesario.

## Configuración

### Variables de entorno

- DATABASE_URL: URL completa de conexión a PostgreSQL o Supabase.
- DB_HOST: host de la base de datos en la nube.
- DB_PORT: puerto de conexión.
- DB_NAME: nombre de la base de datos.
- DB_USER: usuario para la conexión.
- DB_PASSWORD: contraseña del usuario.
- DB_SSLMODE: modo SSL de la conexión.

> Mantener pass.env fuera del repositorio y no compartir credenciales sensibles.

### Configuración Modbus

En config.py se pueden ajustar los siguientes parámetros:
- PORT_MODBUS
- MODBUS_SLAVE_ID
- IPs de los equipos
- dirección inicial de lectura (REG_START_ADDRESS)
- factores de escala (SCALE_*)

## Ejecución

### 1. Iniciar el logger principal

```powershell
python main.py
```

Este proceso lee continuamente los equipos, intenta persistir los datos en la nube y, si la red no está disponible, almacena los registros localmente.

### 2. Iniciar el dashboard

```powershell
py -m streamlit run dashboard.py
```

El dashboard permite visualizar:
- el estado operativo de cada máquina;
- mediciones en tiempo real;
- alertas por temperatura, presión y corriente;
- datos históricos y tendencias.

## Comportamiento del sistema

- Si la conexión a la nube está disponible, los datos se insertan directamente en PostgreSQL.
- Si la red falla, el sistema usa el respaldo local en backup_mantenimiento.db.
- El programa reintenta automáticamente en los siguientes ciclos de lectura.
- Si un equipo no responde o se desconecta, se registran lecturas con valores nulos y se activa la alerta correspondiente.

## Respaldo local

El sistema genera un archivo SQLite denominado backup_mantenimiento.db, el cual almacena la tabla telemetria_backup con los registros pendientes.

## Solución de problemas

- Error ModuleNotFoundError: ejecutar nuevamente pip install -r requirements.txt.
- Dashboard sin datos: verificar que DATABASE_URL esté correctamente definida en pass.env.
- Sin lectura Modbus: comprobar la IP del equipo y el puerto en config.py.
- Sin conexión a la nube: el sistema seguirá operando en modo offline y registrará datos localmente.

## Seguridad

- No subir pass.env al repositorio.
- Si el archivo se compartió de forma accidental, cambiar la contraseña de la base de datos y eliminarlo del historial de Git.
- Evitar compartir credenciales de base de datos en entornos públicos.

## Mejoras incluidas

- Normalización de columnas para análisis consistente.
- Uso de logging para trazabilidad y control de errores.
- Lectura robusta de datos Modbus.
- Respaldo local en SQLite ante fallos de red.
- Panel de monitoreo con visualización clara del estado de la planta.


