import json
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
TOPIC = "microrred/telemetria"

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

print("Enviando telemetria de prueba a EcoGrid-Link...")

# 1. Enviar lectura normal (2.5 W)
payload_normal = {"id_nodo": "casa1", "voltaje": 5.0, "corriente": 0.5}
client.publish(TOPIC, json.dumps(payload_normal))
print(f"Sent: {payload_normal}")
time.sleep(2)

# 2. Enviar lectura de sobrecarga (60 W)
payload_sobrecarga = {"id_nodo": "casa1", "voltaje": 12.0, "corriente": 5.0}
client.publish(TOPIC, json.dumps(payload_sobrecarga))
print(f"Sent: {payload_sobrecarga}")

client.disconnect()
