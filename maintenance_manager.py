# maintenance_manager.py
"""
Módulo de Gestión de Mantenimiento Preventivo / Service de Equipos
Permite calcular horas restantes, porcentajes de vida útil de consumibles
y persistir la configuración de service en un archivo JSON local.
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "maintenance_config.json")

# Configuración por defecto para cada equipo
DEFAULT_MAINTENANCE_CONFIG = {
    "security": {
        "service_pin": "1234",
    },
    "SULLAIR_COMPRESSOR": {
        "last_service_hours": 48002.0,
        "service_interval_hours": 3500.0,
        "last_service_date": "2026-09-01",
        "notes": "Service estándar: cambio de filtros y aceite",
    },
    "AERCOM_22P": {
        "last_service_hours": 10631.0,
        "service_interval_hours": 3000.0,
        "last_service_date": "",
        "notes": "Service estándar Aercom",
    },
    "CHILLER_TRANE": {
        "last_service_hours": 0.0,
        "service_interval_hours": 4000.0,
        "last_service_date": "",
        "notes": "Service de mantenimiento Chiller Trane",
    },
}


def get_service_pin() -> str:
    """Obtiene el PIN de 4 dígitos de seguridad para autorizar reseteos."""
    config = load_maintenance_config()
    return str(config.get("security", {}).get("service_pin", "1234")).strip()


def verify_service_pin(input_pin: str) -> bool:
    """Verifica si el PIN ingresado coincide con el PIN configurado."""
    if not input_pin:
        return False
    return str(input_pin).strip() == get_service_pin()


def update_service_pin(new_pin: str) -> bool:
    """Actualiza el PIN de seguridad (debe ser de 4 dígitos)."""
    pin_str = str(new_pin).strip()
    if not (len(pin_str) == 4 and pin_str.isdigit()):
        return False
    config = load_maintenance_config()
    if "security" not in config:
        config["security"] = {}
    config["security"]["service_pin"] = pin_str
    return save_maintenance_config(config)


def load_maintenance_config() -> dict:
    """
    Carga la configuración de mantenimiento desde el archivo JSON local.
    Si no existe o está corrupto, lo inicializa con los valores por defecto.
    """
    if not os.path.exists(CONFIG_FILE_PATH):
        save_maintenance_config(DEFAULT_MAINTENANCE_CONFIG)
        return DEFAULT_MAINTENANCE_CONFIG.copy()

    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Garantizar que todas las máquinas por defecto existan en el dict
        updated = False
        for machine_key, defaults in DEFAULT_MAINTENANCE_CONFIG.items():
            if machine_key not in data:
                data[machine_key] = defaults
                updated = True
            else:
                # Asegurar claves mínimas
                for k, v in defaults.items():
                    if k not in data[machine_key]:
                        data[machine_key][k] = v
                        updated = True

        if updated:
            save_maintenance_config(data)

        return data
    except Exception as e:
        print(
            f"⚠️ Error al leer {CONFIG_FILE_PATH}: {e}. Usando configuración por defecto."
        )
        return DEFAULT_MAINTENANCE_CONFIG.copy()


def save_maintenance_config(config_data: dict) -> bool:
    """Guarda la configuración de mantenimiento en el archivo JSON."""
    try:
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error al guardar configuración de mantenimiento: {e}")
        return False


def get_machine_service_config(machine_key: str) -> dict:
    """Obtiene la configuración específica de una máquina."""
    config = load_maintenance_config()
    return config.get(
        machine_key,
        DEFAULT_MAINTENANCE_CONFIG.get(
            machine_key,
            {
                "last_service_hours": 0.0,
                "service_interval_hours": 3500.0,
                "last_service_date": "",
                "notes": "",
            },
        ),
    )


def update_machine_service_config(
    machine_key: str,
    last_service_hours: float,
    service_interval_hours: float,
    last_service_date: str = None,
    notes: str = None,
) -> bool:
    """Actualiza y persiste la configuración de service de una máquina."""
    config = load_maintenance_config()
    if machine_key not in config:
        config[machine_key] = {}

    config[machine_key]["last_service_hours"] = float(last_service_hours)
    config[machine_key]["service_interval_hours"] = float(service_interval_hours)
    if last_service_date is not None:
        config[machine_key]["last_service_date"] = str(last_service_date)
    if notes is not None:
        config[machine_key]["notes"] = str(notes)

    return save_maintenance_config(config)


def reset_service_to_current_hours(
    machine_key: str, current_hours: float, notes: str = "Service completado"
) -> bool:
    """
    Registra que se realizó el service en este momento, reseteando el contador
    con las horas actuales como punto de partida.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    config = load_maintenance_config()
    machine_cfg = config.get(machine_key, {})
    interval = float(machine_cfg.get("service_interval_hours", 3500.0))

    return update_machine_service_config(
        machine_key=machine_key,
        last_service_hours=float(current_hours),
        service_interval_hours=interval,
        last_service_date=now_str,
        notes=notes,
    )


def calculate_service_metrics(
    current_hours: float, machine_key: str = "SULLAIR_COMPRESSOR"
) -> dict:
    """
    Calcula las horas restantes para el próximo service, el porcentaje consumido
    y el estado operativo del mantenimiento preventivo.
    """
    cfg = get_machine_service_config(machine_key)
    last_service = float(cfg.get("last_service_hours", 48002.0))
    interval = float(cfg.get("service_interval_hours", 3500.0))
    last_date = cfg.get("last_service_date", "")

    if interval <= 0:
        interval = 3500.0

    next_service_hours = last_service + interval

    if current_hours is not None:
        try:
            current_hours = float(current_hours)
        except (ValueError, TypeError):
            current_hours = None

    if current_hours is None or current_hours < 0:
        return {
            "last_service_hours": last_service,
            "service_interval_hours": interval,
            "next_service_hours": next_service_hours,
            "hours_since_service": 0.0,
            "hours_remaining": interval,
            "progress_pct": 0.0,
            "status": "UNKNOWN",
            "status_label": "Sin Datos",
            "status_color": "#94A3B8",
            "last_service_date": last_date,
        }

    hours_since_service = current_hours - last_service
    hours_remaining = next_service_hours - current_hours

    # Progreso de 0% (recién hecho) a 100% (intervalo cumplido)
    if interval > 0:
        raw_progress = (hours_since_service / interval) * 100.0
        progress_pct = max(0.0, min(100.0, raw_progress))
    else:
        progress_pct = 0.0

    # Clasificación de Estado
    if hours_remaining <= 0:
        status = "OVERDUE"
        status_label = f"🚨 SERVICE VENCIDO ({abs(int(hours_remaining))} hs excedidas)"
        status_color = "#EF4444"  # Rojo
    elif hours_remaining <= 200:
        status = "WARNING"
        status_label = f"⚠️ SERVICE PRÓXIMO ({int(hours_remaining)} hs restantes)"
        status_color = "#F59E0B"  # Ámbar / Naranja
    else:
        status = "OK"
        status_label = f"🟢 SERVICE EN REGLA ({int(hours_remaining)} hs restantes)"
        status_color = "#10B981"  # Verde esmeralda

    return {
        "last_service_hours": last_service,
        "service_interval_hours": interval,
        "next_service_hours": next_service_hours,
        "hours_since_service": hours_since_service,
        "hours_remaining": hours_remaining,
        "progress_pct": progress_pct,
        "status": status,
        "status_label": status_label,
        "status_color": status_color,
        "last_service_date": last_date,
    }
