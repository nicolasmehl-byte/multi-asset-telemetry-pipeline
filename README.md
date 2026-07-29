# proyecto_iiot

Proyecto de telemetría IIoT para monitorear equipos industriales mediante lectura Modbus TCP, almacenamiento en base de datos y visualización en Streamlit.

## ¿Qué hace este proyecto?

Este sistema realiza lo siguiente:
- Lee datos desde equipos industriales por Modbus TCP.
- Recolecta mediciones como presión, temperatura, horas de marcha y corriente.
- Intenta guardar los datos en una base de datos en la nube (PostgreSQL/Supabase).
- Si la conexión a la nube falla, guarda los registros localmente en SQLite como respaldo.
- Muestra la información en un dashboard web con Streamlit.

## Estructura del proyecto

- `main.py`: ejecuta el logger principal y recopila telemetría de forma continua.
- `communication.py`: gestiona la lectura de registros Modbus TCP.
- `database.py`: maneja la conexión a la nube y el respaldo local en SQLite.
- `dashboard.py`: muestra los datos históricos y el estado en tiempo real.
- `config.py`: contiene la configuración de Modbus, IPs del equipo y escalas.
- `pass.env.example`: plantilla de variables de entorno.
- `requirements.txt`: dependencias de Python necesarias.

## Requisitos

- Python 3.10 o superior.
- Windows PowerShell o terminal compatible.
- Acceso a un equipo o simulador Modbus TCP si se quiere probar lectura real.
- Base de datos PostgreSQL/Supabase (opcional si se desea usar la nube).

## Instalación

1. Crear un entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Instalar dependencias:
   ```powershell
   pip install -r requirements.txt
   ```

## Configuración

1. Copiar la plantilla de entorno:
   ```powershell
   copy pass.env.example pass.env
   ```

2. Editar `pass.env` con tus valores reales.

3. Asegurarse de que `pass.env` no se suba al repositorio.

## Variables de entorno soportadas
- `DB_HOST` (por defecto: `aws-1-sa-east-1.pooler.supabase.com`)
- `DB_PORT` (por defecto: `6543`)
- `DB_NAME` (por defecto: `postgres`)
- `DB_USER` (por defecto: `postgres.bmuchkgxvcggummezhhh`)
- `DB_PASSWORD`
- `DB_SSLMODE` (por defecto: `require`)
- `DATABASE_URL` (usado por `main.py` para arrancar el modo nube; también se puede dejar vacío y activar modo offline)

## Ejecución

### 1. Iniciar el logger principal

```powershell
python main.py
```

Este proceso lee continuamente los equipos, intenta subir datos a la nube y, si no hay conexión, guarda los registros localmente en SQLite.

### 2. Iniciar el dashboard

```powershell
py -m streamlit run dashboard.py
```

El dashboard muestra:
- estado operativo de cada máquina,
- mediciones en tiempo real,
- alertas de temperatura, presión y corriente,
- datos históricos.

## Comportamiento del sistema

- Si la conexión a la nube está disponible, los datos se insertan directamente en PostgreSQL.
- Si falla la red, el sistema usa `backup_mantenimiento.db` para guardar los datos localmente.
- El programa reintenta automáticamente en los próximos ciclos de lectura.
- Si un equipo no responde o se desconecta, se registran lecturas con valores nulos y se marca la alerta correspondiente.

## Archivos de respaldo local

El sistema crea un archivo SQLite llamado:

- `backup_mantenimiento.db`

Este archivo almacena una tabla llamada `telemetria_backup` con los registros pendientes.

## Solución de problemas

- Error `ModuleNotFoundError`: ejecutar nuevamente `pip install -r requirements.txt`.
- Dashboard sin datos: verificar que `DATABASE_URL` esté bien definida en `pass.env`.
- Sin lectura Modbus: comprobar que la IP del equipo y el puerto sean correctos en `config.py`.
- Sin conexión a la nube: el sistema seguirá funcionando en modo offline y guardará datos localmente.

## Notas de seguridad

- No subir `pass.env` al repositorio.
- Si el archivo se subió accidentalmente, cambiar la contraseña de la base de datos y eliminarlo del historial de Git.
- No compartir ni exponer credenciales de base de datos en archivos públicos.

## Qué se mejoró en este proyecto

- Normalización de columnas: `pressure_bar`, `temperature_c`, `run_hours`, `current_amps`.
- Uso de logging para trazabilidad y control de errores.
- Lectura robusta de datos Modbus.
- Respaldo local en SQLite ante fallos de red.
- Dashboard con visualización más clara del estado de planta.


