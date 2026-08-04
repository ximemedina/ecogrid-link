# EcoGrid-Link

Sistema telemático en la nube para el monitoreo y balanceo inteligente de microrredes de energía renovable comunitaria (Agenda 2030: ODS 7 y 11).

> 📘 ¿Primera vez con el proyecto? Sigue **[GUIA_DE_USO.md](GUIA_DE_USO.md)** — tutorial paso a paso para levantar el stack y entrar a la API, phpMyAdmin y Grafana.

## 🔧 Estado actual (2026-08-04)

Backend e infraestructura (Integrante 1) listos. Ya está funcionando de punta a punta: MQTT → backend → MySQL → detección de sobrecarga → comando de control. Todo probado localmente con `docker compose up -d --build`.

**Para levantarlo en su máquina:**

```bash
git clone https://github.com/ximemedina/ecogrid-link.git
cd ecogrid-link
cp .env.example .env
docker compose up -d --build
```

**Servicios y accesos:**

- API: http://localhost/api/ — Docs: http://localhost/api/docs
- phpMyAdmin: http://localhost:8080 (Integrante 2 — las tablas `nodos` y `historico_mediciones` ya se crean automáticamente al levantar el backend)
- Grafana: http://localhost:3000 o http://localhost/dashboard/ (usuario/contraseña en `.env`, ya conectable a MySQL con host `mysql`, puerto `3306`, base `ecogrid_link_db`)
- MQTT (Integrante 3 / ESP32): `localhost:1883`, tópicos `microrred/telemetria` (publicar) y `microrred/control` (escuchar)

También agregué una base de firmware para el ESP32 en `firmware/ecogrid_node/` (WiFi + sensor INA219 + MQTT + desconexión de carga), lista para que Integrante 3 la ajuste a su cableado — ver la sección "Firmware ESP32" más abajo.

Cualquier duda, avisen en el chat del equipo.

## Estructura de carpetas

```
ecogrid-link/
├── .env.example          # Plantilla de variables de entorno (sí se sube a GitHub)
├── .env                   # Valores reales locales (NO se sube, está en .gitignore)
├── .gitignore
├── docker-compose.yml     # Orquesta los 6 servicios del stack
├── nginx.conf             # Proxy inverso: /api/ -> backend, /dashboard/ -> grafana
├── README.md
├── mosquitto/
│   └── config/
│       └── mosquitto.conf # Listener 1883 + allow_anonymous (requerido por el broker)
├── backend/
│   ├── Dockerfile
│   ├── main.py            # FastAPI: ingesta MQTT -> MySQL + lógica de balanceo
│   └── requirements.txt
├── firmware/
│   └── ecogrid_node/
│       ├── ecogrid_node.ino   # Firmware ESP32: WiFi + INA219 + MQTT
│       └── config.h.example   # Plantilla de config (WiFi, broker, id del nodo)
├── database/
│   ├── schema.sql             # Esquema de referencia + datos semilla (4 nodos reales)
│   └── consultas_grafana.sql  # Queries SQL usadas por los paneles de Grafana
├── grafana/
│   └── provisioning/
│       ├── datasources/mysql.yml       # Datasource MySQL auto-configurado
│       └── dashboards/
│           ├── provider.yml            # Registra la carpeta de dashboards
│           └── ecogrid_dashboard.json  # Dashboard con 4 paneles listos
├── simulator/
│   ├── simulador_50_hogares.py # 50 hogares MQTT concurrentes (stress test)
│   └── requirements.txt
└── test_simulator.py      # Script de prueba: publica telemetría de ejemplo por MQTT
```

## Arquitectura de contenedores

| Servicio     | Contenedor           | Puerto host | Rol                                          |
|--------------|-----------------------|-------------|-----------------------------------------------|
| nginx        | ecogrid_nginx          | 80          | Única puerta de entrada HTTP                  |
| mosquitto    | ecogrid_mqtt           | 1883        | Bróker MQTT (telemetría y control)            |
| mysql        | ecogrid_db             | 3306        | Base de datos `ecogrid_link_db`               |
| phpmyadmin   | ecogrid_phpmyadmin     | 8080        | Administración visual de MySQL                |
| backend      | ecogrid_backend         | (interno 8000, expuesto en /api/) | Ingesta MQTT + API REST + balanceo |
| grafana      | ecogrid_grafana         | 3000        | Dashboards en tiempo real (también en /dashboard/) |

## Puesta en marcha

1. Copia la plantilla de entorno y ajusta contraseñas si lo deseas:
   ```bash
   cp .env.example .env
   ```
2. Levanta todo el stack:
   ```bash
   docker compose up -d --build
   ```
3. Verifica que el backend responde:
   - API root: http://localhost/api/
   - Docs Swagger: http://localhost/api/docs
4. Administra la base de datos en http://localhost:8080 (usuario `root`, contraseña la de `.env`).
5. Accede a Grafana en http://localhost/dashboard/ o directamente en http://localhost:3000 (usuario/contraseña definidos en `.env`, por defecto `admin` / `grafana_admin_password`). El datasource de MySQL y el dashboard "EcoGrid-Link — Monitoreo de Microrred" ya vienen auto-provisionados — no hace falta configurarlos a mano.

### Probar el flujo de telemetría

Con el stack corriendo, instala el cliente MQTT localmente y ejecuta el simulador:

```bash
pip install paho-mqtt
python test_simulator.py
```

Esto publica una lectura normal (2.5 W) y una de sobrecarga (60 W) en el tópico `microrred/telemetria`. Revisa los logs del backend para confirmar la inserción en MySQL y, en el caso de sobrecarga, el envío del comando de desconexión al tópico `microrred/control`:

```bash
docker compose logs -f backend
```

## Datos y Visualización (Integrante 2)

**Esquema de la base de datos:** `database/schema.sql` documenta las tablas `nodos` e `historico_mediciones` (el backend ya las crea automáticamente al arrancar). Trae datos semilla con los 4 nodos reales de la maqueta — hospital, bomberos y dos casas — para ver algo en Grafana/phpMyAdmin sin esperar al ESP32.

**Dashboard de Grafana:** auto-provisionado en `grafana/provisioning/` — al levantar el stack ya existe el datasource de MySQL y el dashboard "EcoGrid-Link — Monitoreo de Microrred" con 4 paneles:
- Potencia por nodo (serie de tiempo)
- Potencia total actual (stat, con umbrales verde/amarillo/rojo en 30W/50W)
- Consumo por zona en la última hora (barras)
- Última lectura por nodo (tabla)

Las consultas SQL de cada panel están documentadas en `database/consultas_grafana.sql` por si quieres editarlas o agregar paneles nuevos desde la UI de Grafana.

**Simulador de 50 hogares** (para estresar la base de datos con carga concurrente, distinto de los 4 nodos físicos de la maqueta):
```bash
cd simulator
pip install -r requirements.txt
python simulador_50_hogares.py --hogares 50 --intervalo 5
```
Cada hogar virtual (`hogar_virtual_01` … `hogar_virtual_50`) corre en su propio hilo con su propia conexión MQTT, se registra solo vía `POST /api/nodos`, y ocasionalmente (3% de las lecturas) simula un pico de sobrecarga para ejercitar la lógica de balanceo. Detén con `Ctrl+C`.

## Firmware ESP32 (Integrante 3)

El sketch está en `firmware/ecogrid_node/ecogrid_node.ino`.

**1. Instalar librerías** (Arduino IDE → Herramientas → Administrar bibliotecas):
- `PubSubClient` (Nick O'Leary)
- `ArduinoJson` (Benoit Blanchon)
- `Adafruit INA219` (instala también la dependencia `Adafruit BusIO`)

**2. Armar el circuito.** Es el mismo circuito × 4 (hospital, bomberos, casa1, casa2) — solo cambia el `NODE_ID` en `config.h` de cada placa.

Materiales por nodo: 1× ESP32 DevKit, 1× INA219, 1× relevador de 1 canal (5V), 1× LED + resistor 220–330Ω (la "carga"), breadboard y jumpers. La maqueta trabaja en DC bajo (5–12V, igual que `test_simulator.py`), no en 127V AC — no hace falta equipo de protección especial.

Bus I2C (ESP32 ↔ INA219):
```
ESP32 3.3V    → INA219 VCC
ESP32 GND     → INA219 GND
ESP32 GPIO21  → INA219 SDA
ESP32 GPIO22  → INA219 SCL
```

Rama de potencia — todo en serie, en este orden exacto (el INA219 va en serie con la carga, no en paralelo, para medir lo que realmente consume):
```
5V → INA219 (VIN+ → VIN−) → Relevador (COM → NO) → LED+resistor → GND
```

Control del relevador:
```
ESP32 GPIO2 (PIN_ACTUADOR) → Relevador IN
Relevador VCC → 5V
Relevador GND → GND
```

Orden de armado: (1) con el ESP32 desconectado de USB, cablea primero el I2C; (2) arma la rama de potencia en serie; (3) conecta el relevador; (4) revisa continuidad con multímetro — ningún GND en corto contra 5V — antes de energizar; (5) flashea el firmware y abre el Monitor Serial (115200 baudios) para confirmar que lee voltaje/corriente cada 3s (si marca 0.00 en ambos, revisa el I2C antes de seguir).

> **⚠️ Polaridad del relevador:** el firmware espera que `GPIO2` en `HIGH` (estado por defecto al encender) deje la carga **conectada**, y `LOW` la **desconecte**. Los módulos de relevador varían en si activan la bobina con HIGH o con LOW, lo que decide si usas el contacto `NO` o `NC` para que "en reposo" quede conectado. Sube el firmware primero, observa si el LED enciende al arrancar, y ajusta a qué contacto está soldado el cable de carga hasta lograrlo.

**3. Configurar:**
```bash
cd firmware/ecogrid_node
cp config.h.example config.h
```
Edita `config.h` con tu WiFi, la IP (o host de ngrok) del broker MQTT y el `NODE_ID` de esta placa. `config.h` no se sube a GitHub.

**4. Registrar el nodo** en el backend antes de la demo, para que aparezca en Grafana/phpMyAdmin. La maqueta tiene 4 nodos físicos (`database/schema.sql` ya trae estos 4 como semilla); registra el que corresponda a esta placa, por ejemplo:
```bash
curl -X POST http://localhost/api/nodos -H "Content-Type: application/json" \
  -d '{"id_nodo": "casa1", "zona": "Casa 1", "tipo_nodo": "consumo_no_prioritario", "limite_alerta_watts": 50}'
```
Hospital y bomberos deben registrarse como `"tipo_nodo": "consumo_prioritario"` — el backend nunca les envía la orden de desconexión, sin importar cuánta potencia reporten.

**5. Conexión remota (opcional):** si el ESP32 no está en la misma red que el backend, expón el broker con ngrok desde la laptop que corre `docker compose`:
```bash
ngrok tcp 1883
```
Usa el host y puerto que te da ngrok como `MQTT_BROKER` / `MQTT_PORT` en `config.h`.

Cuando el backend detecta sobrecarga, envía la orden de desconexión al `id_nodo` que la reportó — pero solo si ese nodo está registrado como `consumo_no_prioritario` (hospital y bomberos, al ser `consumo_prioritario`, nunca se desconectan). El firmware ignora cualquier comando de control cuyo `id_nodo` no coincida con su propio `NODE_ID`, así que las 4 placas pueden compartir el tópico `microrred/control` sin interferir entre sí.

## Endpoints principales de la API

- `GET /api/nodos` — lista los nodos registrados.
- `POST /api/nodos` — registra un nodo nuevo (`id_nodo`, `zona`, `tipo_nodo`, `limite_alerta_watts`).
- `GET /api/historico/{id_nodo}?limite=50` — últimas mediciones de un nodo.

## Tópicos MQTT

- `microrred/telemetria` — publicado por el ESP32 / simulador: `{"id_nodo": "...", "voltaje": 5.0, "corriente": 0.45}`.
- `microrred/control` — publicado por el backend cuando detecta sobrecarga: `{"id_nodo": "...", "accion": "desconectar"}`.

## Publicar en GitHub

Desde esta carpeta (la que contiene `docker-compose.yml`):

```bash
git init
git add .
git commit -m "EcoGrid-Link: infraestructura Docker + backend FastAPI"
git branch -M main
git remote add origin <URL_DE_TU_REPOSITORIO>
git push -u origin main
```

`.env`, los volúmenes de datos y los archivos `__pycache__` quedan excluidos automáticamente por `.gitignore`.

## Roles del equipo

- **Integrante 1 (Backend e Infraestructura):** `docker-compose.yml`, `nginx.conf`, microservicio FastAPI de ingesta y lógica de balanceo.
- **Integrante 2 (Datos y Visualización):** esquema SQL (`database/schema.sql`), dashboard de Grafana auto-provisionado (`grafana/provisioning/`), script simulador de 50 hogares (`simulator/`).
- **Integrante 3 (Telemática y Hardware):** maqueta física, firmware ESP32 (Wi-Fi/MQTT, base en `firmware/ecogrid_node/`), sensores INA219 y actuadores.
