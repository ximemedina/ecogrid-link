# EcoGrid-Link — Cómo funciona el proyecto

Resumen técnico del sistema completo, para que cualquiera del equipo entienda cómo se conecta todo. Para
instrucciones paso a paso de instalación/uso ver `GUIA_DE_USO.md`; para detalles de cada rol ver
`README.md`.

## Qué es

Un sistema que simula una microrred eléctrica comunitaria (hospital, estación de bomberos, 2 casas) que:
1. Recibe telemetría (voltaje/corriente) de cada nodo por MQTT.
2. La guarda en MySQL y la muestra en un dashboard de Grafana.
3. Si un nodo reporta una sobrecarga, decide automáticamente si desconectarlo:
   - `hospital` y `bomberos` son `consumo_prioritario` → **nunca** se desconectan.
   - `casa1` y `casa2` son `consumo_no_prioritario` → se desconectan si se sobrecargan.

## Arquitectura

```
ESP32 (WiFi/MQTT) ──▶ Mosquitto (broker MQTT) ──▶ Backend (FastAPI)
                                                        │
                                                        ▼
                                                   MySQL (datos)
                                                        │
                                                        ▼
                                                     Grafana (dashboard)

nginx expone todo por el puerto 80: /api/ → backend, /dashboard/ → Grafana
```

## Servicios (Docker Compose)

| Servicio | Puerto | Función |
|---|---|---|
| `nginx` | 80 | Proxy único de entrada |
| `mosquitto` | 1883 | Broker MQTT |
| `mysql` | 3306 | Base de datos |
| `phpmyadmin` | 8080 | Administración de la base de datos |
| `backend` | interno (vía nginx) | Lógica de negocio: recibe telemetría, decide desconexiones, expone la API |
| `grafana` | 3000 | Dashboard |

## Flujo de datos

1. El ESP32 (o un simulador) publica en el tópico MQTT `microrred/telemetria`:
   `{"id_nodo": "casa1", "voltaje": 8.19, "corriente": 0.045}`
2. El backend está suscrito a ese tópico, calcula `potencia_watts = voltaje * corriente`, y guarda la
   lectura en la tabla `historico_mediciones`.
3. Si `potencia_watts` supera `UMBRAL_SOBRECARGA_WATTS` (50W por defecto), el backend revisa el
   `tipo_nodo` en la tabla `nodos`:
   - Si es `consumo_prioritario` → solo registra una advertencia en el log.
   - Si es `consumo_no_prioritario` → publica `{"id_nodo": "casa1", "accion": "desconectar"}` en el
     tópico `microrred/control`.
4. El ESP32 está suscrito a `microrred/control` y, si el `id_nodo` coincide con uno de sus canales,
   apaga el relevador correspondiente.
5. Grafana consulta MySQL directamente (no pasa por MQTT ni por el backend) cada 5 segundos para
   refrescar el dashboard.

## Base de datos

- **`nodos`**: catálogo de nodos (`id_nodo`, `zona`, `tipo_nodo`, `limite_alerta_watts`).
- **`historico_mediciones`**: historial de lecturas (`id_nodo`, `voltaje`, `corriente`,
  `potencia_watts`, `fecha_hora`).

## API del backend

Base: `http://localhost/api/` — Swagger interactivo en `http://localhost/api/docs`.

- `GET /` — estado del backend
- `GET /nodos` — lista de nodos registrados
- `POST /nodos` — registra un nodo nuevo
- `GET /historico/{id_nodo}?limite=50` — historial de un nodo

## Circuito físico (maqueta)

Un solo ESP32 con un sensor INA219 compartido y un relevador de 2 canales:
- **Canal 1** (3 LEDs): `hospital` + `bomberos` — nunca se desconecta.
- **Canal 2** (3 LEDs): `casa1` + `casa2` — se desconectan juntas si hay sobrecarga (comparten el mismo
  relevador físico).

Como el sensor es compartido, los 4 nodos reportan la misma lectura de voltaje en cada ciclo — es una
limitación del hardware disponible para la maqueta, no del diseño de software (en un despliegue real,
cada nodo tendría su propio sensor y actuador independiente).

Firmware: `firmware/ecogrid_node/ecogrid_node.ino` (configurar `config.h` a partir de
`config.h.example`, no se sube a git).

## Cómo correr el stack

```bash
docker compose up -d --build
```

Ver `GUIA_DE_USO.md` para el paso a paso completo (accesos, contraseñas, cómo generar telemetría de
prueba, cómo probar la desconexión automática).

Para disparar una desconexión manualmente (útil para pruebas o demos):
```bash
python demo_sobrecarga.py casa1          # sobrecarga → se desconecta
python demo_sobrecarga.py hospital       # sobrecarga → NO se desconecta (prioritario)
python demo_sobrecarga.py casa1 --normal # reconecta
```

## Roles del equipo

- **Integrante 1 (Backend e Infraestructura):** Docker Compose, nginx, backend FastAPI, MQTT, base de
  datos, lógica de balanceo.
- **Integrante 2 (Datos y Visualización):** esquema SQL, dashboard de Grafana, simulador de 50 hogares.
- **Integrante 3 (Telemática y Hardware):** firmware ESP32, circuito físico, pruebas de hardware.
