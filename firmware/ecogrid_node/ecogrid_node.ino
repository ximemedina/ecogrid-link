// EcoGrid-Link — Firmware de nodo ESP32
// Rol: Integrante 3 (Telemática y Hardware)
//
// Lee voltaje/corriente del sensor INA219, publica telemetría por MQTT en
// microrred/telemetria, y escucha microrred/control para desconectar la
// carga (relevador/LED) cuando el backend detecta una sobrecarga.
//
// Librerías requeridas (Arduino IDE > Herramientas > Administrar bibliotecas):
//   - PubSubClient (Nick O'Leary)
//   - ArduinoJson  (Benoit Blanchon)
//   - Adafruit INA219 (+ dependencia Adafruit BusIO)
//
// Conexión I2C del INA219 (pines por defecto en la mayoría de placas ESP32):
//   VCC -> 3.3V   GND -> GND   SDA -> GPIO21   SCL -> GPIO22

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_INA219.h>
#include "config.h"

static const char* TOPIC_TELEMETRIA = "microrred/telemetria";
static const char* TOPIC_CONTROL = "microrred/control";

WiFiClient espClient;
PubSubClient mqttClient(espClient);
Adafruit_INA219 ina219;

unsigned long ultimoEnvio = 0;

void conectarWiFi() {
  Serial.printf("Conectando a WiFi: %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.printf("WiFi conectado. IP: %s\n", WiFi.localIP().toString().c_str());
}

void alRecibirMensaje(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  if (error) {
    Serial.print("Error al parsear JSON de control: ");
    Serial.println(error.c_str());
    return;
  }

  const char* idNodoDestino = doc["id_nodo"];
  const char* accion = doc["accion"];
  if (idNodoDestino == nullptr || accion == nullptr) return;
  if (strcmp(idNodoDestino, NODE_ID) != 0) return; // El comando no es para este nodo

  if (strcmp(accion, "desconectar") == 0) {
    digitalWrite(PIN_ACTUADOR, LOW);
    Serial.println("Carga DESCONECTADA por orden del servidor");
  } else if (strcmp(accion, "conectar") == 0) {
    digitalWrite(PIN_ACTUADOR, HIGH);
    Serial.println("Carga RECONECTADA por orden del servidor");
  }
}

void reconectarMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Conectando al broker MQTT...");
    String clientId = String(NODE_ID) + "-" + String(random(0xffff), HEX);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" conectado");
      mqttClient.subscribe(TOPIC_CONTROL);
    } else {
      Serial.printf(" fallo, rc=%d. Reintentando en 3s\n", mqttClient.state());
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(PIN_ACTUADOR, OUTPUT);
  digitalWrite(PIN_ACTUADOR, HIGH); // Carga conectada por defecto

  Wire.begin();
  if (!ina219.begin()) {
    Serial.println("No se encontro el sensor INA219. Revisa el cableado I2C (SDA/SCL).");
  }

  conectarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(alRecibirMensaje);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
  }
  if (!mqttClient.connected()) {
    reconectarMQTT();
  }
  mqttClient.loop();

  unsigned long ahora = millis();
  if (ahora - ultimoEnvio >= INTERVALO_ENVIO_MS) {
    ultimoEnvio = ahora;

    float voltaje = ina219.getBusVoltage_V();
    float corriente = ina219.getCurrent_mA() / 1000.0; // mA -> A

    StaticJsonDocument<128> doc;
    doc["id_nodo"] = NODE_ID;
    doc["voltaje"] = voltaje;
    doc["corriente"] = corriente;

    char buffer[128];
    size_t n = serializeJson(doc, buffer);
    mqttClient.publish(TOPIC_TELEMETRIA, buffer, n);

    Serial.printf("Telemetria enviada: V=%.2f I=%.3f\n", voltaje, corriente);
  }
}
