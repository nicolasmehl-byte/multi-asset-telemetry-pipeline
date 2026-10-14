import socket

# Configuración de tu conversor
GATEWAY_IP = "192.168.0.196"
PORT = 8899


def sniffer_rs485():
    print(f"Abriendo túnel hacia {GATEWAY_IP}:{PORT} en modo Escucha...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Le damos 15 segundos de paciencia para ver si el Chiller "habla"
        s.settimeout(15.0)
        s.connect((GATEWAY_IP, PORT))
        print("✅ Conectado. Escuchando el puerto J25 (BMS2) en silencio...")
        print("Esperando tráfico bruto del Chiller...\n")

        # Solo recibimos, no enviamos nada
        data = s.recv(2048)

        if data:
            hex_data = data.hex(" ").upper()
            print(f"🔥 ¡TRÁFICO DETECTADO! ({len(data)} bytes recibidos):")
            print(hex_data)

            # Analizamos la firma del protocolo
            if "55 FF" in hex_data:
                print("\n🎯 ¡BINGO! Se detectó la cabecera '55 FF'.")
                print("El Chiller ESTÁ hablando BACnet MS/TP. ¡Podemos integrarlo!")
            else:
                print(
                    "\n⚠️ Hay datos, pero no es la firma de BACnet. Podría ser Comm4/LonTalk."
                )
        else:
            print(
                "\nSilencio total. El Chiller no transmitió nada en estos 15 segundos."
            )

    except socket.timeout:
        print(
            "\n⏰ Timeout: No se escuchó nada en la red. El puerto está completamente mudo a esta velocidad."
        )
    except Exception as e:
        print(f"\n❌ Error de red: {e}")
    finally:
        s.close()


if __name__ == "__main__":
    sniffer_rs485()
