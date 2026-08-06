import asyncio
import json
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker
import aiomqtt

# Configuración del registrador de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EcoGridBackend")

# 1. Configuración de la Base de Datos Relacional (SQLAlchemy / MySQL)
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://ecogrid_user:ecogrid_user_password@mysql/ecogrid_link_db")
engine = create_engine(DATABASE_URL, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos para ORM
class Nodo(Base):
    __tablename__ = 'nodos'
    id_nodo = Column(String(50), primary_key=True)
    zona = Column(String(50), nullable=False)
    tipo_nodo = Column(String(30), nullable=False)
    limite_alerta_watts = Column(Float, default=100.0)

class HistoricoMedicion(Base):
    __tablename__ = 'historico_mediciones'
    id_medicion = Column(Integer, primary_key=True, autoincrement=True)
    id_nodo = Column(String(50), nullable=False, index=True)
    voltaje = Column(Float, nullable=False)
    corriente = Column(Float, nullable=False)
    potencia_watts = Column(Float, nullable=False)
    fecha_hora = Column(DateTime, nullable=False, server_default=func.now(), index=True)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 1b. Esquemas Pydantic (necesarios para serializar los modelos de SQLAlchemy a JSON)
class NodoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_nodo: str
    zona: str
    tipo_nodo: str
    limite_alerta_watts: float

class NodoCreate(BaseModel):
    id_nodo: str
    zona: str
    tipo_nodo: str
    limite_alerta_watts: float = 100.0

class HistoricoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_medicion: int
    id_nodo: str
    voltaje: float
    corriente: float
    potencia_watts: float
    fecha_hora: Optional[datetime] = None

# 2. Configuración de MQTT y Parámetros Telemáticos
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
TOPIC_TELEMETRIA = "microrred/telemetria"
TOPIC_CONTROL = "microrred/control"
UMBRAL_SOBRECARGA_WATTS = float(os.getenv("UMBRAL_SOBRECARGA_WATTS", 50.0))

async def listen_mqtt_telemetry():
    """Tarea asíncrona en segundo plano para procesar telemetría e interacciones de balanceo"""
    await asyncio.sleep(5)
    logger.info(f"Conectando al broker MQTT en {MQTT_BROKER}:{MQTT_PORT}...")
    while True:
        try:
            async with aiomqtt.Client(hostname=MQTT_BROKER, port=MQTT_PORT) as client:
                logger.info(f"Suscrito exitosamente al tópico: {TOPIC_TELEMETRIA}")
                await client.subscribe(TOPIC_TELEMETRIA)
                async for message in client.messages:
                    try:
                        payload_data = json.loads(message.payload.decode())
                        id_nodo = payload_data.get("id_nodo")
                        voltaje = float(payload_data.get("voltaje") or 0.0)
                        corriente = float(payload_data.get("corriente") or 0.0)
                        
                        # Cálculo del consumo real en el Backend (P = V * I)
                        potencia_watts = voltaje * corriente
                        
                        logger.info(f"Métrica procesada para [{id_nodo}]: {potencia_watts:.2f} W")
                        
                        # Inserción en MySQL
                        db = SessionLocal()
                        nueva_medicion = HistoricoMedicion(
                            id_nodo=id_nodo,
                            voltaje=voltaje,
                            corriente=corriente,
                            potencia_watts=potencia_watts
                        )
                        db.add(nueva_medicion)
                        db.commit()
                        db.close()
                        
                        # Lógica de Balanceo: si sobrepasa el límite, se emite una orden de desconexión.
                        # Las cargas prioritarias (hospital, bomberos) nunca se desconectan; solo
                        # se corta el nodo que reportó la sobrecarga si es consumo_no_prioritario.
                        if potencia_watts > UMBRAL_SOBRECARGA_WATTS:
                            db = SessionLocal()
                            nodo_info = db.get(Nodo, id_nodo)
                            db.close()
                            es_prioritario = nodo_info is not None and nodo_info.tipo_nodo == "consumo_prioritario"

                            if es_prioritario:
                                logger.warning(f"¡SOBRECARGA EN CARGA PRIORITARIA {id_nodo}! Potencia: {potencia_watts}W — no se desconecta (carga crítica)")
                            else:
                                logger.warning(f"¡SOBRECARGA DETECTADA EN {id_nodo}! Potencia: {potencia_watts}W")
                                control_command = {
                                    "id_nodo": id_nodo,
                                    "accion": "desconectar"
                                }
                                await client.publish(TOPIC_CONTROL, payload=json.dumps(control_command))
                                logger.info(f"Comando de emergencia enviado al tópico {TOPIC_CONTROL}")
                    except Exception as e:
                        logger.error(f"Error procesando mensaje MQTT: {e}")
        except Exception as conn_error:
            logger.error(f"Fallo de conexión MQTT: {conn_error}. Reintentando en 5 segundos...")
            await asyncio.sleep(5)

# 3. Manejo del Ciclo de Vida de FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Reintentos de conexión inicial a MySQL mientras el contenedor de DB termina de levantar
    db_connected = False
    retries = 10
    while not db_connected and retries > 0:
        try:
            Base.metadata.create_all(bind=engine)
            db_connected = True
            logger.info("¡Conexión exitosa y tablas inicializadas en MySQL!")
        except Exception as e:
            retries -= 1
            logger.warning(f"Esperando a MySQL... Reintentos restantes: {retries}. Info: {e}")
            await asyncio.sleep(3)

    if not db_connected:
        logger.error("No se pudo establecer conexión con MySQL tras varios intentos.")

    # Lanzar consumidor asíncrono de MQTT
    mqtt_task = asyncio.create_task(listen_mqtt_telemetry())
    yield
    mqtt_task.cancel()

app = FastAPI(title="EcoGrid-Link API", lifespan=lifespan, root_path="/api", openapi_url="/openapi.json", docs_url="/docs")

# 4. Endpoints de la API REST
@app.get("/")
def read_root():
    return {
        "proyecto": "EcoGrid-Link",
        "rol": "Integrante 1 (Backend e Infraestructura)",
        "estado": "Operativo"
    }

@app.get("/nodos", response_model=List[NodoSchema])
def list_nodos(db: Session = Depends(get_db)):
    return db.query(Nodo).all()

@app.post("/nodos", response_model=NodoSchema)
def create_nodo(nodo: NodoCreate, db: Session = Depends(get_db)):
    if db.get(Nodo, nodo.id_nodo):
        raise HTTPException(status_code=409, detail=f"El nodo '{nodo.id_nodo}' ya existe")
    nuevo_nodo = Nodo(**nodo.model_dump())
    db.add(nuevo_nodo)
    db.commit()
    db.refresh(nuevo_nodo)
    return nuevo_nodo

@app.get("/historico/{id_nodo}", response_model=List[HistoricoSchema])
def get_historico(id_nodo: str, limite: int = 50, db: Session = Depends(get_db)):
    return (
        db.query(HistoricoMedicion)
        .filter(HistoricoMedicion.id_nodo == id_nodo)
        .order_by(HistoricoMedicion.fecha_hora.desc())
        .limit(limite)
        .all()
    )
