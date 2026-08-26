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

- leer_telemetria.py: ejecuta el proceso de recopilación y registro de datos del compresor Sullair real.
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

# Proyecto IIoT de monitoreo industrial

## Brief para continuar el desarrollo con Gemini

Este repositorio contiene un sistema de monitoreo industrial para activos conectados por Modbus TCP. La aplicación captura telemetría, la guarda en PostgreSQL/Supabase, utiliza SQLite como respaldo cuando falla la red y la muestra en un dashboard Streamlit.

Al continuar el trabajo, conservar estas reglas:

- Trabajar sobre la estructura y los nombres existentes.
- No exponer ni modificar credenciales de `pass.env`.
- Mantener separados los nombres técnicos de base de datos, las claves de configuración y los nombres visibles.
- Validar cada cambio con `py -m py_compile dashboard.py`.
- No reemplazar consultas PostgreSQL por `pd.read_sql` con conexiones DBAPI de psycopg2: el proyecto usa cursores mediante `read_postgres_dataframe()`.
- Antes de cambiar el dashboard, revisar los cambios locales porque `dashboard.py` puede ser editado por el usuario o por un formateador.

## Arquitectura y archivos

- `leer_telemetria.py`: lectura y decodificación Modbus del compresor Sullair; normaliza presión, temperatura, horas, estado y advertencias.
- `communication.py`: conexión Modbus TCP y lectura robusta de registros.
- `database.py`: persistencia en PostgreSQL/Supabase y respaldo local SQLite.
- `dashboard.py`: aplicación Streamlit de monitoreo en vivo, alertas e historial.
- `config.py`: IP, puerto, Slave ID, registros y factores de escala.
- `main.py`: punto de entrada del proceso principal, si se utiliza.
- `data_collection.py`, `scan_full.py`, `buscar_registro_corriente.py`: herramientas de exploración y diagnóstico Modbus.
- `db_connection.py`: utilidades de conexión a la base de datos.
- `logo_grupo_beniplast.png`: logo institucional usado en la cabecera del dashboard.
- `logo_sullair.jpg`: recurso visual del equipo Sullair.
- `pass.env.example`: plantilla de variables de entorno. `pass.env` contiene secretos y no debe compartirse.
- `requirements.txt`: dependencias Python.
- `iniciar_programa.bat`: inicio del sistema en Windows.

## Requisitos y ejecución

Requisitos: Python 3.10 o superior, Windows PowerShell, acceso a Modbus TCP y una base PostgreSQL/Supabase.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy pass.env.example pass.env
```

Configurar `pass.env` y luego ejecutar en terminales separadas:

```powershell
python leer_telemetria.py
py -m streamlit run dashboard.py
```

En Windows, si `python` no está disponible en un terminal pero existe el launcher, usar `py`.

## Configuración de conexión

El dashboard intenta obtener `DATABASE_URL` desde `st.secrets` y, si no existe, desde `pass.env`/variables de entorno. En Streamlit Cloud se recomienda configurar `DATABASE_URL` en Settings → Secrets.

También se admite `TIMEOUT_DESCONEXION`, expresado en segundos. El valor utilizado por defecto en el código es `200` segundos.

Nunca incluir valores reales de `DATABASE_URL`, usuarios, contraseñas o tokens en documentación, commits o mensajes.

## Nombres de equipos y umbrales

Los nombres no tienen que ser iguales. Se usan tres niveles:

| Propósito | Ejemplo |
|---|---|
| Nombre técnico guardado en DB | `SULLAIR_COMPRESSOR` |
| Clave de alertas | `SULLAIR SE1507NEW` |
| Nombre visible | `Compresor Sullair` |

El mapeo vigente en `dashboard.py` es:

```python
MACHINE_DISPLAY_LABEL = {
    "AERCOM_22P": "Compresor Aercom",
    "SULLAIR_COMPRESSOR": "Compresor Sullair",
    "CHILLER_TRANE": "Chiller Trane",
}

MACHINE_ALERT_KEY = {
    "AERCOM_22P": "AERCOM 22P",
    "SULLAIR_COMPRESSOR": "SULLAIR SE1507NEW",
    "CHILLER_TRANE": "CHILLER TRANE CGAX030",
}
```

Los únicos umbrales efectivos son los definidos en `PREVENTIVE_ALERTS`. No existe un bloque de defaults: cada equipo debe tener `max_temp`, `min_temp`, `max_press` y `min_press`. Usar `None` en `min_press` significa que no se controla presión mínima para ese equipo.

Configuración actual documentada:

| Equipo | Temperatura | Presión máxima | Presión mínima |
|---|---:|---:|---:|
| Aercom | 65 a 95 °C | 7.5 bar | 6.5 bar |
| Sullair | 65 a 95 °C | 6.9 bar | 6.5 bar |
| Chiller Trane | 4.5 a 12 °C | 27 bar | 6.5 bar |

Si se cambia un umbral, modificar `PREVENTIVE_ALERTS`, no `MACHINE_DISPLAY_LABEL`. La función `get_preventive_alerts()` accede directamente a la configuración del equipo y no aplica valores alternativos.

## Dashboard actual

`dashboard.py` tiene dos pestañas:

### Monitoreo en Vivo

- Muestra cada activo dentro de una tarjeta.
- Indica estado `ENCENDIDO`, `APAGADO` o `SIN CONEXIÓN`.
- Actualiza el fragmento cada 10 segundos.
- Presenta gauges de `Presión Línea` y `Temperatura`, horas de marcha y Delta P del filtro separador.
- Los gauges tienen altura fija de 300 px, valor central de 34 px, título de 34 px y escala de 19 px.
- La presión y la temperatura se convierten a `float` antes de compararlas o restarlas.
- Las alertas de presión y temperatura aparecen debajo de su gauge correspondiente.
- Las advertencias de mantenimiento aparecen en un cartel `ALARMA MANTENIMIENTO`; al pasar el cursor se muestran mediante tooltip.
- Las fallas de parada y pérdida de comunicación se muestran en sus banners correspondientes.

### Historial de Tendencias

- Permite seleccionar activo y período.
- Muestra dos gráficos: evolución térmica y presión.
- La tabla inicia en `Resumen diario`.
- Agrupa las lecturas por fecha y muestra el promedio diario de presión y temperatura.
- Lecturas cuya presión o temperatura se separa al menos un 20% del promedio diario aparecen debajo del día correspondiente, en rojo, con la hora y el porcentaje de desviación.
- El porcentaje se calcula como `abs(valor - promedio) / abs(promedio) * 100`.
- El selector `Mostrar todos los datos` permite revisar todas las lecturas horarias.
- La tabla contiene fecha completa, activo, presión, temperatura y detalle.

## Correcciones importantes realizadas

- Se eliminó `DEFAULT_PREVENTIVE_ALERTS`, que podía ocultar una configuración faltante aplicando valores no deseados.
- Se corrigió el mapeo entre `SULLAIR_COMPRESSOR`, `SULLAIR SE1507NEW` y `Compresor Sullair`.
- Se corrigió `TypeError: unsupported operand type(s) for -: 'float' and 'decimal.Decimal'` convirtiendo las presiones provenientes de PostgreSQL a `float`.
- Se reemplazaron todos los `use_container_width=True` por `width="stretch"`, según la API actual de Streamlit.
- Se reemplazó `pd.read_sql` sobre conexiones psycopg2 por `read_postgres_dataframe()`, evitando el warning de compatibilidad de Pandas.
- Se separaron las alertas de presión y temperatura de las advertencias de mantenimiento.
- Las alertas de presión y temperatura ahora se muestran debajo del gauge correspondiente.
- Las advertencias de mantenimiento volvieron al cartel con tooltip, en lugar de mezclarse en un banner único.
- Se añadió una cabecera institucional con el logo `logo_grupo_beniplast.png` y el título `Sistema de Monitoreo Industrial`.
- Se ampliaron los textos de las pestañas, las etiquetas de métricas y los valores numéricos.
- Se intentó estabilizar el layout responsive de Plotly frente al zoom del navegador fijando altura, márgenes y ancho mínimo de columnas.

## Problemas conocidos y precauciones

- El zoom del navegador puede afectar el layout de Streamlit/Plotly; no usar CSS global que fuerce `overflow: hidden` sobre los SVG de Plotly porque puede recortar títulos, números o escalas.
- Si un equipo no aparece o falla al resolver alertas, verificar primero que su clave técnica esté en `ORDEN_PLANTA_KEYS`, `MACHINE_DISPLAY_LABEL`, `MACHINE_ALERT_KEY` y `PREVENTIVE_ALERTS`.
- Si `pressure_sink_bar` es `NULL`, Delta P del filtro separador queda como `N/D`; la presión de línea y temperatura no dependen de esa columna.
- Los registros históricos de Aercom y Chiller pueden no tener `pressure_sink_bar`; no inventar Delta P para esos registros.
- Los diagnósticos actuales del editor muestran advertencias preexistentes sobre `except Exception`, `dict()` y `datetime.now()`; no son errores de sintaxis ni impiden ejecutar el dashboard.

## Validación mínima

Después de modificar Python:

```powershell
py -m py_compile dashboard.py
```

Para verificar que no reaparezcan avisos antiguos:

```powershell
rg "use_container_width|pd\.read_sql" dashboard.py
```

La búsqueda debería no devolver resultados.

## Seguridad

- No subir `pass.env` ni bases locales con datos sensibles.
- Mantener `pass.env.example` sin secretos reales.
- Si una credencial fue expuesta, revocarla y cambiarla.
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