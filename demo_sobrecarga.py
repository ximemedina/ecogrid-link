"""
Disparador de sobrecarga para la demo en vivo.

Simula que un nodo reporta un consumo por encima del umbral, para que el
backend mande la orden de desconexión igual que lo haría con datos reales
del ESP32. Útil para el día de la presentación: no depende de que el
sensor físico llegue a un consumo real de 50W (imposible a esta escala
de voltaje/corriente).

Uso:
    python demo_sobrecarga.py                # sobrecarga en casa1 (se desconecta)
    python demo_sobrecarga.py casa2           # sobrecarga en casa2 (se desconecta)
    python demo_sobrecarga.py hospital        # sobrecarga en hospital (NO se desconecta, es prioritario)
    python demo_sobrecarga.py casa1 --normal  # manda una lectura normal (2.5W) para "reconectar" visualmente
"""
import json
import sys
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "microrred/telemetria"

nodo = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "casa1"
normal = "--normal" in sys.argv

payload = (
    {"id_nodo": nodo, "voltaje": 5.0, "corriente": 0.5}      # 2.5W, normal
    if normal else
    {"id_nodo": nodo, "voltaje": 12.0, "corriente": 5.0}     # 60W, sobrecarga
)

client = mqtt.Client()
client.connect(BROKER, PORT, 60)
client.publish(TOPIC, json.dumps(payload))
client.disconnect()

print(f"Enviado a [{nodo}]: {payload}")
if not normal:
    print("Si es una carga no prioritaria (casa1/casa2), el backend debe mandar la orden de desconexión.")
    print("Si es hospital/bomberos, el log del backend debe decir 'no se desconecta (carga crítica)'.")
