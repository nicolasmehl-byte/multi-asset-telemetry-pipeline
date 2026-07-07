# proyecto_iiot

Proyecto de telemetría IIoT con lectura Modbus, respaldo local en SQLite y dashboard en Streamlit.

## Archivo importante
- `pass.env.example`: plantilla de configuración de variables de entorno. No incluyas valores secretos aquí.

## Instalación
1. Crea un entorno virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instala dependencias:
   ```powershell
   pip install -r requirements.txt
   ```

## Configuración
1. Copia el archivo de ejemplo:
   ```powershell
   copy pass.env.example pass.env
   ```
2. Edita `pass.env` con tu contraseña de base de datos y otros valores si es necesario.
3. Asegúrate de que `pass.env` esté en `.gitignore` para no subirlo al repositorio.

## Variables de entorno soportadas
- `DB_HOST` (por defecto: `aws-1-sa-east-1.pooler.supabase.com`)
- `DB_PORT` (por defecto: `6543`)
- `DB_NAME` (por defecto: `postgres`)
- `DB_USER` (por defecto: `postgres.bmuchkgxvcggummezhhh`)
- `DB_PASSWORD`
- `DB_SSLMODE` (por defecto: `require`)
- `DATABASE_URL` (usado por `main.py` para arrancar el modo nube; también se puede dejar vacío y activar modo offline)

## Ejecución
- Iniciar el logger principal:
  ```powershell
  python main.py
  ```
- Iniciar el dashboard de Streamlit:
 py -m streamlit run dashboard.py

## Qué se corrigió y mejoró
- Normalización de campos: `pressure_bar`, `temperature_c`, `run_hours`, `current_amps`.
- Uso de logging en lugar de `print()` para mensajes operativos y errores.
- Lectura segura de credenciales desde variables de entorno.
- Consulta SQL parametrizada en `dashboard.py` para reducir riesgo de inyección.
- Manejo robusto de errores en lecturas Modbus y backup local.

## Nota de seguridad
No subas `pass.env` al repositorio. Si ya se subió accidentalmente, cambia la contraseña de la base de datos y elimina el archivo del historial de Git.


