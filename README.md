# EcoGrid-Link

Sistema telemático en la nube para el monitoreo y balanceo inteligente de microrredes de energía renovable comunitaria (Agenda 2030: ODS 7 y 11).

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
5. Accede a Grafana en http://localhost/dashboard/ o directamente en http://localhost:3000 (usuario/contraseña definidos en `.env`, por defecto `admin` / `grafana_admin_password`). Conéctalo a MySQL (host `mysql`, puerto `3306`, base `ecogrid_link_db`).

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
- **Integrante 2 (Datos y Visualización):** esquema SQL en phpMyAdmin, dashboards en Grafana, script simulador de 50 hogares.
- **Integrante 3 (Telemática y Hardware):** maqueta física, firmware ESP32 (Wi-Fi/MQTT), sensores INA219 y actuadores.
