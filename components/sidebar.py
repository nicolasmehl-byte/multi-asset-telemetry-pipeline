import streamlit as st

import maintenance_manager as mm

RECOVERY_MASTER_PIN = "0084"


def is_valid_service_pin(pin_value):
    pin_str = str(pin_value or "").strip()
    return len(pin_str) == 4 and pin_str.isdigit()


def verify_service_pin_value(pin_value):
    if hasattr(mm, "verify_service_pin"):
        return bool(mm.verify_service_pin(pin_value))

    pin_str = str(pin_value or "").strip()
    if not is_valid_service_pin(pin_str):
        return False

    cfg = mm.load_maintenance_config() if hasattr(mm, "load_maintenance_config") else {}
    expected = str(cfg.get("security", {}).get("service_pin", "1234")).strip()
    return pin_str == expected


def update_service_pin_value(new_pin):
    if hasattr(mm, "update_service_pin"):
        return mm.update_service_pin(new_pin)

    pin_str = str(new_pin or "").strip()
    if len(pin_str) != 4 or not pin_str.isdigit():
        return False

    if hasattr(mm, "load_maintenance_config") and hasattr(
        mm, "save_maintenance_config"
    ):
        config = mm.load_maintenance_config()
        config.setdefault("security", {})
        config["security"]["service_pin"] = pin_str
        return mm.save_maintenance_config(config)
    return False


def render_sidebar():
    with st.sidebar:
        st.markdown("### 🛠️ Mantenimiento Preventivo")

        st.markdown(
            """
            <div class="admin-config-box">
                <div class="admin-config-header">Acceso Admin</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        admin_pin = st.text_input(
            "PIN administrador",
            type="password",
            max_chars=4,
            key="sb_admin_pin",
            help="PIN requerido para guardar o resetear el service.",
        )

        with st.expander("🔐 Recuperar contraseña", expanded=False):
            recovery_pin = st.text_input(
                "Clave de recuperación",
                type="password",
                max_chars=4,
                key="sb_recovery_pin",
                placeholder="1234",
                help="Solo esta clave maestra permite cambiar el PIN admin del equipo.",
            )
            new_admin_pin = st.text_input(
                "Nuevo PIN admin",
                type="password",
                max_chars=4,
                key="sb_recovery_new_admin_pin",
                placeholder="1234",
                help="Se usa solo si se ingresa la clave maestra correcta.",
            )
            if st.button(
                "Cambiar PIN admin",
                key="sb_btn_recovery_change_pin",
                use_container_width=True,
            ):
                if recovery_pin != RECOVERY_MASTER_PIN:
                    st.warning("❌ Clave de recuperación incorrecta.")
                elif not is_valid_service_pin(new_admin_pin):
                    st.warning("❌ El nuevo PIN admin debe tener 4 dígitos numéricos.")
                else:
                    update_service_pin_value(new_admin_pin)
                    st.success("✅ PIN admin actualizado correctamente.")
                    st.rerun()

        stored_admin_pin = (
            mm.get_service_pin() if hasattr(mm, "get_service_pin") else "1234"
        )
        initial_setup = str(stored_admin_pin or "").strip() in ("", "1234")

        # --- SECCIÓN SULLAIR ---
        with st.expander("⚙️ Configuración Service Sullair", expanded=False):
            cfg_sullair = mm.get_machine_service_config("SULLAIR_COMPRESSOR")
            sb_last = st.number_input(
                "Último service (hs):",
                min_value=0.0,
                max_value=200000.0,
                value=float(cfg_sullair.get("last_service_hours", 48002.0)),
                step=50.0,
                key="sb_last_service_sullair",
            )
            sb_interval = st.number_input(
                "Intervalo entre services (hs):",
                min_value=100.0,
                max_value=50000.0,
                value=float(cfg_sullair.get("service_interval_hours", 3500.0)),
                step=100.0,
                key="sb_interval_sullair",
            )

            c_sb1, c_sb2 = st.columns([1, 1])
            with c_sb1:
                if st.button(
                    "💾 Guardar", key="sb_btn_save_sullair", use_container_width=True
                ):
                    if initial_setup:
                        if not is_valid_service_pin(admin_pin):
                            st.warning(
                                "❌ El PIN admin debe tener 4 dígitos numéricos."
                            )
                        else:
                            update_service_pin_value(admin_pin)
                            mm.update_machine_service_config(
                                machine_key="SULLAIR_COMPRESSOR",
                                last_service_hours=sb_last,
                                service_interval_hours=sb_interval,
                            )
                            st.success(
                                "✅ PIN inicial configurado y configuración guardada."
                            )
                            st.rerun()
                    elif not admin_pin or not verify_service_pin_value(admin_pin):
                        st.warning(
                            "❌ PIN admin incorrecto. Debe ingresar 4 dígitos válidos."
                        )
                    else:
                        mm.update_machine_service_config(
                            machine_key="SULLAIR_COMPRESSOR",
                            last_service_hours=sb_last,
                            service_interval_hours=sb_interval,
                        )
                        st.success("✅ Configuración guardada.")
                        st.rerun()
            with c_sb2:
                if st.button(
                    "🔄 Reset Service",
                    key="sb_btn_reset_sullair",
                    use_container_width=True,
                    help="Resetea tomando las horas ingresadas en 'Último service'",
                ):
                    if initial_setup:
                        if not is_valid_service_pin(admin_pin):
                            st.warning(
                                "❌ El PIN admin debe tener 4 dígitos numéricos."
                            )
                        else:
                            update_service_pin_value(admin_pin)
                            mm.reset_service_to_current_hours(
                                machine_key="SULLAIR_COMPRESSOR",
                                current_hours=sb_last,
                            )
                            st.success(
                                "✅ PIN inicial configurado y service reseteado."
                            )
                            st.rerun()
                    elif not admin_pin or not verify_service_pin_value(admin_pin):
                        st.warning(
                            "❌ PIN admin incorrecto. No se puede resetear el service."
                        )
                    else:
                        mm.reset_service_to_current_hours(
                            machine_key="SULLAIR_COMPRESSOR",
                            current_hours=sb_last,
                        )
                        st.success("✅ Service reseteado.")
                        st.rerun()

        # --- SECCIÓN AERCOM ---
        with st.expander("⚙️ Configuración Service Aercom", expanded=False):
            cfg_aercom = mm.get_machine_service_config("AERCOM_22P")
            aercom_last = st.number_input(
                "Último service Aercom (hs):",
                min_value=0.0,
                max_value=200000.0,
                value=float(cfg_aercom.get("last_service_hours", 10631.0)),
                step=50.0,
                key="sb_last_service_aercom",
            )
            aercom_interval = st.number_input(
                "Intervalo service Aercom (hs):",
                min_value=100.0,
                max_value=50000.0,
                value=float(cfg_aercom.get("service_interval_hours", 3000.0)),
                step=100.0,
                key="sb_interval_service_aercom",
            )
            aercom_col_save, aercom_col_reset = st.columns([1, 1])
            with aercom_col_save:
                if st.button("💾 Guardar Aercom", key="sb_save_service_aercom"):
                    if not admin_pin or not verify_service_pin_value(admin_pin):
                        st.warning("❌ PIN admin incorrecto.")
                    else:
                        mm.update_machine_service_config(
                            machine_key="AERCOM_22P",
                            last_service_hours=aercom_last,
                            service_interval_hours=aercom_interval,
                        )
                        st.success("✅ Configuración Aercom guardada.")
                        st.rerun()
            with aercom_col_reset:
                if st.button("🔄 Reset Aercom", key="sb_reset_service_aercom"):
                    if not admin_pin or not verify_service_pin_value(admin_pin):
                        st.warning("❌ PIN admin incorrecto.")
                    else:
                        mm.reset_service_to_current_hours(
                            machine_key="AERCOM_22P",
                            current_hours=aercom_last,
                        )
                        st.success("✅ Service Aercom reseteado.")
                        st.rerun()
