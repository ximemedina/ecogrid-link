# Guía de uso — EcoGrid-Link

Tutorial paso a paso para levantar el stack completo y entrar a cada herramienta (API, phpMyAdmin, Grafana). Pensada para cualquiera del equipo que clone el repo por primera vez.

## 0. Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y abierto (en Windows, con WSL2 habilitado).
- Git.
- (Opcional, solo para el simulador de 50 hogares) Python 3.10+.

Verifica que Docker responde antes de seguir:
```bash
docker --version
docker compose version
```

## 1. Clonar y configurar

```bash
git clone https://github.com/ximemedina/ecogrid-link.git
cd ecogrid-link
cp .env.example .env
```

`.env` trae valores de ejemplo que ya funcionan para desarrollo local (usuario/contraseña de MySQL, admin/`admin` de Grafana, umbral de sobrecarga). No hace falta editarlo para probar el proyecto — solo cámbialo si vas a exponerlo fuera de tu máquina.

## 2. Levantar el stack

```bash
docker compose up -d --build
```

La primera vez descarga las imágenes (MySQL, Grafana, Mosquitto, phpMyAdmin, nginx) y construye el backend — tarda unos minutos. Verifica que los 6 contenedores quedaron arriba:

```bash
docker compose ps
```

Deberías ver `ecogrid_nginx`, `ecogrid_mqtt`, `ecogrid_db`, `ecogrid_phpmyadmin`, `ecogrid_backend` y `ecogrid_grafana`, todos en estado `Up`.

Si algo no arrancó, revisa sus logs:
```bash
docker compose logs -f backend
docker compose logs -f grafana
```

## 3. Entrar a la API (backend)

- Estado general: http://localhost/api/
- Documentación interactiva (Swagger): http://localhost/api/docs — desde ahí puedes probar `GET /nodos`, `POST /nodos` y `GET /historico/{id_nodo}` sin escribir código.

Prueba rápida por terminal:
```bash
curl http://localhost/api/nodos
```

## 4. Entrar a phpMyAdmin (base de datos)

1. Abre http://localhost:8080
2. Servidor: ya viene preseleccionado (`mysql`).
3. Usuario: `root`
4. Contraseña: la de `MYSQL_ROOT_PASSWORD` en tu `.env` (por defecto `root_secure_password`).
5. Entra a la base `ecogrid_link_db` → tablas `nodos` (los 4 nodos de la maqueta: `hospital`, `bomberos`, `casa1`, `casa2`) e `historico_mediciones` (telemetría cronológica).

El esquema y los datos semilla están documentados en `database/schema.sql`, por si necesitas recrearlos manualmente desde la pestaña "SQL" de phpMyAdmin.

## 5. Entrar a Grafana (dashboards)

1. Abre http://localhost:3000 (o http://localhost/dashboard/ vía nginx).
2. Usuario: `admin`
3. Contraseña: la de `GRAFANA_ADMIN_PASSWORD` en tu `.env` (por defecto `admin`).
4. Menú lateral → **Dashboards** → **EcoGrid-Link — Monitoreo de Microrred**. Ya viene armado con 4 paneles:
   - Potencia por nodo (serie de tiempo)
   - Potencia total actual (con umbrales verde/amarillo/rojo en 30W/50W)
   - Consumo por zona en la última hora (barras)
   - Última lectura por nodo (tabla)

No hace falta configurar el datasource a mano — ya se auto-provisiona apuntando a MySQL. Si el dashboard se ve vacío es porque todavía no hay telemetría (ver siguiente paso).

> Si cambias `GRAFANA_ADMIN_PASSWORD` en `.env` **después** de que Grafana ya arrancó una vez, ese cambio no se aplica solo — Grafana guarda el usuario admin en su propia base interna la primera vez. Para resetear la contraseña sin perder el dashboard:
> ```bash
> docker exec ecogrid_grafana grafana cli admin reset-admin-password TU_NUEVA_CONTRASEÑA
> ```

## 6. Generar telemetría de prueba

Para ver los paneles con datos reales, necesitas que algo publique en el tópico MQTT `microrred/telemetria`. Tres formas, de más simple a más completa:

**A. Una lectura de prueba (rápido, 2 mensajes):**
```bash
pip install paho-mqtt
python test_simulator.py
```
Envía una lectura normal (2.5W) y una de sobrecarga (60W) para el nodo `casa1`.

**B. Simulador de 50 hogares (carga sostenida, para ver el dashboard "vivo"):**
```bash
cd simulator
pip install -r requirements.txt
python simulador_50_hogares.py --hogares 10 --intervalo 3
```
Bájale el número de hogares para una prueba rápida; usa `--hogares 50` para la prueba de estrés completa. Detén con `Ctrl+C`.

**C. Un ESP32 real**, siguiendo la guía de armado en la sección "Firmware ESP32" del `README.md`.

Después de cualquiera de las tres, refresca el dashboard de Grafana (arriba a la derecha, ícono de refresco — ya está en modo auto-refresh cada 5s).

## 7. Probar la lógica de balanceo (desconexión automática)

Publica una sobrecarga para una carga **no prioritaria** (una casa) y mira los logs del backend:
```bash
docker compose logs -f backend
```
Deberías ver `¡SOBRECARGA DETECTADA...!` seguido de `Comando de emergencia enviado`. Si la sobrecarga es en `hospital` o `bomberos` (cargas prioritarias), el log dice `no se desconecta (carga crítica)` — nunca se envía la orden de corte.

## 8. Apagar el stack

```bash
docker compose down
```
Esto detiene los contenedores pero conserva los datos (usa los volúmenes de Docker). Si además quieres borrar todos los datos y empezar de cero:
```bash
docker compose down -v
```

## Resumen de accesos

| Herramienta | URL | Usuario | Contraseña |
|---|---|---|---|
| API / Swagger | http://localhost/api/docs | — | — |
| phpMyAdmin | http://localhost:8080 | `root` | `MYSQL_ROOT_PASSWORD` en `.env` |
| Grafana | http://localhost:3000 | `admin` | `GRAFANA_ADMIN_PASSWORD` en `.env` |
| MQTT (broker) | `localhost:1883` | — (anónimo permitido) | — |
| MySQL (directo) | `localhost:3306` | `MYSQL_USER` | `MYSQL_PASSWORD` en `.env` |
