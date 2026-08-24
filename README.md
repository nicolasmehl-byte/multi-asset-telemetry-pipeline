# Proyecto IIoT de monitoreo industrial

Este proyecto implementa un sistema de telemetría industrial orientado a la supervisión de activos mediante comunicación Modbus TCP, almacenamiento persistente de datos y visualización en tiempo real. Su objetivo es ofrecer una solución práctica para monitorear variables críticas de equipos industriales y procesos industriales, con respaldo local en caso de fallas de conectividad.

## Descripción general

El sistema permite:
- leer mediciones de presión, temperatura y horas de marcha desde equipos industriales o simuladores Modbus;
- enviar los datos a una base de datos en la nube cuando la conexión está disponible;
- almacenar registros locales en SQLite como respaldo ante interrupciones de red;
- visualizar el estado operativo de la planta mediante un dashboard web construido con Streamlit.

## Arquitectura del sistema

El flujo principal del proyecto consta de tres capas:
1. Captura de datos: lectura de registros Modbus TCP desde los equipos. En este caso con conversores RS485 - TCP/WIFI. 
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
- alertas por temperatura y presión;
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


## Notas de despliegue y correcciones recientes

Se documentan aquí cambios recientes que resolvieron problemas en Streamlit Cloud y comportamientos inesperados del dashboard:

- `get_database_url()` ahora intenta leer `st.secrets.get("DATABASE_URL")` y, si no está disponible, cae en la variable de entorno `DATABASE_URL` (cargada desde `pass.env`). Esto evita errores cuando no hay `secrets.toml` en el entorno de ejecución.

- Debug seguro en el sidebar: el expander de Debug DB ejecuta ahora una consulta inline usando una conexión nueva creada con `psycopg2.connect(db_url, connect_timeout=5)` para verificar acceso y mostrar una tabla de estado por activo. Anteriormente se invocaba una función (`get_latest_data()`) que en algunos despliegues se definía más abajo en el archivo, provocando `NameError` durante la ejecución top-down de Streamlit.

- Evitar cerrar la conexión cacheada: el debug abre y cierra una conexión dedicada para diagnóstico. NO se cierra la conexión devuelta por `init_connection()` (anotada con `@st.cache_resource`) porque esa conexión es compartida por la app y cerrarla producía `psycopg2.InterfaceError` en ejecuciones concurrentes.

- Umbral por defecto de desconexión: `TIMEOUT_DESCONEXION` se aumentó a `200` segundos para evitar falsos positivos de "SIN RECEPCIÓN" cuando la telemetría tiene cierta latencia. Puede ser sobrescrito poniendo en `pass.env` o en `st.secrets` la variable `TIMEOUT_DESCONEXION` (valor en segundos).

Recomendaciones para despliegue en Streamlit Cloud

- Añadir `DATABASE_URL` en Secrets de Streamlit (Settings → Secrets) para evitar exponer credenciales en `pass.env`.
- Si se quiere ajustar el comportamiento sin tocar código, definir `TIMEOUT_DESCONEXION` en `pass.env` o en `st.secrets`.
- Consultar el expander "🔧 Debug DB (solo admin)" en el sidebar para ver: fuente del secret, host:port (enmascarado), test de conexión y tabla con `machine`, `timestamp`, `tz`, `pressure_bar`, `seconds_since`.

Si querés que documente pasos para agregar `TIMEOUT_DESCONEXION` desde la UI del dashboard en lugar de usar la variable de entorno, lo agrego en la próxima versión del README.


## Comunicación RS485/Modbus del compresor Sullair

### Parámetros testeados

Las pruebas se realizaron mediante el gateway HF2211 conectado a:

- Gateway: `192.168.0.128`
- Puerto Modbus TCP: `502`
- Protocolo: Modbus TCP nativo
- Modo físico: Half Duplex
- Configuración serie validada: `19200-8-E-1`
  - Baud rate: `19200`
  - Bits de datos: `8`
  - Paridad: Even
  - Bits de parada: `1`
- ID Modbus confirmado: `1`

Durante las pruebas también se utilizaron las etiquetas:

- `9600-8-N-1`
- `9600-8-E-1`
- `19200-8-E-1`


### Búsqueda del ID Modbus

El script `scan_full.py` recorre los IDs del `1` al `247` y consulta el registro `258` mediante la función `0x03`.

Un ID se considera detectado cuando responde:

- Con una respuesta válida `0x03`.
- Con una excepción Modbus `0x83`, ya que esto confirma que el dispositivo existe aunque el registro o la función no sean válidos.

Ejecutar:

```powershell
python scan_full.py
```

El resultado se guarda en `scan_log.csv`.

### Exploración de registros

`data_collection.py` prueba las funciones:

- `0x03`: Holding Registers.
- `0x04`: Input Registers.

Actualmente explora los registros `0` a `100` usando el ID `1`.

```powershell
python data_collection.py
```

### Trama Modbus TCP en hexadecimal

Una solicitud de lectura utiliza la siguiente estructura:

| Bytes | Descripción |
|---|---|
| `00 01` | Transaction ID |
| `00 00` | Protocol ID |
| `00 06` | Longitud de la trama |
| `01` | Unit ID / Slave ID |
| `04` | Función: Read Input Registers |
| `00 XX` | Dirección del registro |
| `00 01` | Cantidad de registros |

Ejemplo para leer el registro `7`:

```text
00 01 00 00 00 06 01 04 00 07 00 01
```

Una respuesta válida tiene el formato:

```text
00 01 00 00 00 05 01 04 02 VV VV
```

Donde `VV VV` representa el valor del registro en formato entero sin signo y big-endian.

Las respuestas de excepción utilizan:

```text
00 01 00 00 00 03 01 84 EE
```

- `84`: función `0x04` + `0x80`.
- `EE`: código de excepción Modbus.

## Telemetría y decodificación

El script `leer_telemetria.py` lee y decodifica las variables principales del compresor usando el ID `1` y la función `0x04`.

```powershell
python leer_telemetria.py
```

### Mapa de registros

| Registro | Dirección hexadecimal | Variable |
|---:|---:|---|
| 0 | `0x0000` | Código de parada/falla |
| 5 | `0x0005` | Modo de operación |
| 6 | `0x0006` | Estado operativo |
| 7 | `0x0007` | Temperatura T1 |
| 10 | `0x000A` | Presión P1, sumidero |
| 11 | `0x000B` | Presión P2, línea |
| 68 | `0x0044` | Horas de marcha, palabra alta |
| 69 | `0x0045` | Horas de marcha, palabra baja |
| 78 | `0x004E` | Advertencias de mantenimiento |
| 79 | `0x004F` | Advertencias de temperatura |

### Conversiones aplicadas

- Temperatura T1:

```text
temperatura_°C = (valor - 512) / 28.8
```

- Presión P1/P2:

```text
presión_bar = valor / 232
```

- Horas de marcha:

```text
horas = ((registro_alto × 32768) + registro_bajo) / 60
```

### Modos de operación

| Valor | Descripción |
|---:|---|
| 0 | STOPPED |
| 1 | CONTINUOUS |
| 2 | AUTOMATIC |

### Estados operativos

| Valor | Descripción |
|---:|---|
| 0 | OFF / DETENIDO |
| 3 | READY |
| 4 | ENABLED |
| 5 | AUTOENABLED |
| 8 | STARTING |
| 10 | UNLOADED |
| 11 | LOADING |
| 12 | FULL LOAD |
| 13 | MODULATING |
| 14 | STOPPING |

### Códigos de parada

| Código | Alarma |
|---:|---|
| 0 | Sin fallas de parada |
| 1 | Alta temperatura de descarga |
| 2 | Sobrepresión en línea/sumidero |
| 3 | Falla en arrancador o sobrecarga del motor |
| 4 | Parada de emergencia activada |
| 5 | Secuencia o pérdida de fase |
| 6 | Falla del sensor de temperatura T1 |
| 7 | Falla del sensor de presión P1 |
| 8 | Falla del sensor de presión P2 |

### Bits de advertencia de mantenimiento — registro 78

| Máscara | Advertencia |
|---:|---|
| `0x0001` | Reemplazar filtro de aceite/fluido |
| `0x0002` | Reemplazar elemento separador |
| `0x0004` | Reemplazar filtro de aire |
| `0x0008` | Realizar análisis de aceite |
| `0x0010` | Reemplazar aceite/fluido completo |
| `0x0020` | Mantenimiento preventivo programado |

### Bits de advertencia de temperatura — registro 79

| Máscara | Advertencia |
|---:|---|
| `0x0008` | Alta temperatura T1 |
| `0x0020` | Alta temperatura T2 |

Para decodificar un registro de alarmas se aplica una operación AND bit a bit:

```python
if valor & mascara:
    print("Alarma activa")
```


## Archivos de diagnóstico

- `scan_full.py`: búsqueda del Slave ID.
- `data_collection.py`: exploración del mapa de registros.
- `leer_telemetria.py`: lectura y decodificación de telemetría y alarmas.
- `scan_log.csv`: resultados de búsqueda de IDs.
- `modbus_log.csv`: registro de pruebas de velocidad, paridad y respuestas hexadecimales.