// EcoGrid-Link — Firmware de nodo ESP32 (2 canales, 1 sensor compartido)
// Rol: Integrante 3 (Telemática y Hardware)
//
// El circuito físico ya está armado así y no se puede modificar:
//   5V -> INA219 (único, compartido) -> se divide en 2 ramas con relevador:
//     Canal 1 (relevador CH1) -> 3 LEDs: zona prioritaria (hospital + bomberos)
//     Canal 2 (relevador CH2) -> 3 LEDs: zona no prioritaria (casa1 + casa2)
//
// Como el INA219 está antes de la división, mide la corriente TOTAL del
// circuito (ambos canales juntos), no una lectura por canal. Por eso los 4
// nodos (hospital, bomberos, casa1, casa2) reportan la misma lectura de
// voltaje/corriente en cada ciclo — es una limitación física del circuito
// (un solo sensor para 2 ramas), no del software.
//
// El control sí es independiente por canal: cada relevador se activa por
// separado, así que una orden de desconexión para un nodo del canal 2 apaga
// ese canal (casa1 + casa2 juntas) sin tocar el canal 1. En la práctica el
// canal 1 nunca se desconecta, porque el backend solo envía la orden de
// corte a nodos "consumo_no_prioritario", y hospital/bomberos son
// "consumo_prioritario".
//
// Publica telemetría por MQTT en microrred/telemetria y escucha
// microrred/control para desconectar el canal correspondiente.
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
static const int NUM_CANALES = 2;
static const int NODOS_POR_CANAL = 2;

struct Canal {
  const char* nodeIds[NODOS_POR_CANAL];
  int pinRelevador;
};

Canal canales[NUM_CANALES] = {
  { { NODE_ID_CH1_A, NODE_ID_CH1_B }, PIN_RELAY_CH1 },
  { { NODE_ID_CH2_A, NODE_ID_CH2_B }, PIN_RELAY_CH2 },
};

WiFiClient espClient;
PubSubClient mqttClient(espClient);
Adafruit_INA219 ina219; // sensor único, compartido por los 2 canales

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

bool canalTieneNodo(const Canal& canal, const char* idNodo) {
  for (int j = 0; j < NODOS_POR_CANAL; j++) {
    if (strcmp(idNodo, canal.nodeIds[j]) == 0) return true;
  }
  return false;
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

  for (int i = 0; i < NUM_CANALES; i++) {
    if (!canalTieneNodo(canales[i], idNodoDestino)) continue; // el comando no es para este canal

    if (strcmp(accion, "desconectar") == 0) {
      digitalWrite(canales[i].pinRelevador, LOW);
      Serial.printf("Canal %d DESCONECTADO (pedido por %s, afecta a %s y %s)\n",
                    i + 1, idNodoDestino, canales[i].nodeIds[0], canales[i].nodeIds[1]);
    } else if (strcmp(accion, "conectar") == 0) {
      digitalWrite(canales[i].pinRelevador, HIGH);
      Serial.printf("Canal %d RECONECTADO (pedido por %s, afecta a %s y %s)\n",
                    i + 1, idNodoDestino, canales[i].nodeIds[0], canales[i].nodeIds[1]);
    }
  }
}

void reconectarMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Conectando al broker MQTT...");
    String clientId = "ecogrid-node-" + String(random(0xffff), HEX);
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
  Wire.begin();

  for (int i = 0; i < NUM_CANALES; i++) {
    pinMode(canales[i].pinRelevador, OUTPUT);
    digitalWrite(canales[i].pinRelevador, HIGH); // carga conectada por defecto
  }

  if (!ina219.begin()) {
    Serial.println("No se encontro el sensor INA219. Revisa el cableado I2C (SDA/SCL).");
  }
  // Fija la calibración explícitamente: en algunas versiones de la librería,
  // begin() no la deja bien establecida y getCurrent_mA() devuelve NaN.
  ina219.setCalibration_32V_2A();

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

    // Una sola lectura para todo el circuito: el INA219 está antes de la
    // división en canales, así que mide la corriente total de ambas ramas.
    float voltaje = ina219.getBusVoltage_V();
    float corriente = ina219.getCurrent_mA() / 1000.0; // mA -> A

    for (int i = 0; i < NUM_CANALES; i++) {
      for (int j = 0; j < NODOS_POR_CANAL; j++) {
        StaticJsonDocument<128> doc;
        doc["id_nodo"] = canales[i].nodeIds[j];
        doc["voltaje"] = voltaje;
        doc["corriente"] = corriente;

        char buffer[128];
        size_t n = serializeJson(doc, buffer);
        mqttClient.publish(TOPIC_TELEMETRIA, buffer, n);
      }
    }

    Serial.printf("Lectura compartida (los 4 nodos): V=%.2f I=%.3f\n", voltaje, corriente);
  }
}
