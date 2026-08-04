"""
EcoGrid-Link — Simulador de hogares concurrentes
Rol: Integrante 2 (Datos y Visualización)

Simula N hogares virtuales de la microrred (distintos de los 4 nodos físicos
de la maqueta: hospital, bomberos, casa1, casa2). Cada hogar es un cliente
MQTT independiente que:
  1. Se registra como nodo en el backend (POST /api/nodos), si aún no existe.
  2. Publica telemetría periódica en microrred/telemetria con voltaje/corriente
     a la escala de la maqueta, y ocasionalmente simula picos de sobrecarga
     para poner a prueba la lógica de balanceo y llenar los dashboards de
     Grafana con datos fluyendo en tiempo real.

Uso:
    pip install -r requirements.txt
    python simulador_50_hogares.py --hogares 50 --intervalo 5

Variables de entorno opcionales:
    MQTT_BROKER (default: localhost)
    MQTT_PORT   (default: 1883)
    API_URL     (default: http://localhost/api)
"""

import argparse
import json
import os
import random
import signal
import threading
import time

import paho.mqtt.client as mqtt
import requests

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
API_URL = os.getenv("API_URL", "http://localhost/api")
TOPIC_TELEMETRIA = "microrred/telemetria"

PROB_SOBRECARGA = 0.03  # 3% de las lecturas simulan un pico de sobrecarga

detener = threading.Event()


def registrar_nodo(id_nodo: str, zona: str, tipo_nodo: str, limite: float = 50.0):
    payload = {
        "id_nodo": id_nodo,
        "zona": zona,
        "tipo_nodo": tipo_nodo,
        "limite_alerta_watts": limite,
    }
    try:
        resp = requests.post(f"{API_URL}/nodos", json=payload, timeout=5)
        if resp.status_code not in (200, 409):
            print(f"[{id_nodo}] No se pudo registrar (status {resp.status_code}): {resp.text}")
    except requests.RequestException as e:
        print(f"[{id_nodo}] Backend no disponible para registrar el nodo: {e}")


def generar_lectura():
    if random.random() < PROB_SOBRECARGA:
        # Pico de sobrecarga: dispara la lógica de balanceo del backend
        voltaje = round(random.uniform(11.0, 13.0), 2)
        corriente = round(random.uniform(4.0, 6.0), 3)
    else:
        # Consumo normal a la escala de la maqueta (~2-4 W)
        voltaje = round(random.uniform(4.7, 5.3), 2)
        corriente = round(random.uniform(0.2, 0.8), 3)
    return voltaje, corriente


def simular_hogar(indice: int, intervalo: float):
    id_nodo = f"hogar_virtual_{indice:02d}"
    registrar_nodo(id_nodo, zona=f"Hogar Virtual {indice}", tipo_nodo="consumo_no_prioritario")

    client = mqtt.Client(client_id=f"sim-{id_nodo}")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=30)
    except Exception as e:
        print(f"[{id_nodo}] No se pudo conectar al broker MQTT: {e}")
        return
    client.loop_start()

    while not detener.is_set():
        voltaje, corriente = generar_lectura()
        payload = {"id_nodo": id_nodo, "voltaje": voltaje, "corriente": corriente}
        client.publish(TOPIC_TELEMETRIA, json.dumps(payload))
        detener.wait(max(0.5, intervalo + random.uniform(-0.5, 0.5)))

    client.loop_stop()
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Simulador de N hogares virtuales concurrentes para EcoGrid-Link")
    parser.add_argument("--hogares", type=int, default=50, help="Cantidad de hogares virtuales (default: 50)")
    parser.add_argument("--intervalo", type=float, default=5.0, help="Segundos entre lecturas por hogar (default: 5)")
    args = parser.parse_args()

    def manejar_salida(sig, frame):
        print("\nDeteniendo simulación...")
        detener.set()

    signal.signal(signal.SIGINT, manejar_salida)

    print(f"Simulando {args.hogares} hogares virtuales -> MQTT {MQTT_BROKER}:{MQTT_PORT} (topico {TOPIC_TELEMETRIA})")
    hilos = []
    for i in range(1, args.hogares + 1):
        t = threading.Thread(target=simular_hogar, args=(i, args.intervalo), daemon=True)
        t.start()
        hilos.append(t)
        time.sleep(0.05)  # escalonar conexiones para no saturar el broker de golpe

    for t in hilos:
        t.join()

    print("Simulación detenida.")


if __name__ == "__main__":
    main()
