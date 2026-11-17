import os
import psycopg2
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="DrFreeze - Sistema IoT Profissional")

# CORS para permitir acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# ============ MODELOS ============
class LeituraSensor(BaseModel):
    dispositivo_id: str
    temperatura: float
    umidade: float = None
    status_sensor: str = "OK"

class HeartbeatData(BaseModel):
    dispositivo_id: str
    wifi_status: str = "OK"
    db_status: str = "OK"
    sensor_status: str = "OK"

class NovoDispositivo(BaseModel):
    device_id: str
    nome_setor: str
    nome_freezer: str
    temp_minima: float = 2.0
    temp_maxima: float = 8.0

# ============ CONEXÃO BANCO ============
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# ============ ROTAS PRINCIPAIS ============

@app.get("/")
def root():
    return FileResponse("static/index.html")

# Rota POST: Recebe dados do ESP32 (EXISTENTE - mantida)
@app.post("/api/temperatura")
def receber_leitura(dados: LeituraSensor, x_api_key: str = Header(None)):
    if x_api_key != os.getenv("API_SECRET_TOKEN"):
        raise HTTPException(status_code=401, detail="Token inválido")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insere leitura
        cur.execute(
            "INSERT INTO leituras_temperatura (dispositivo_id, temperatura) VALUES (%s, %s)",
            (dados.dispositivo_id, dados.temperatura)
        )
        
        # Atualiza status do dispositivo e última conexão
        cur.execute(
            """UPDATE dispositivos 
               SET status_conexao = 'ONLINE', 
                   status_sensor = %s,
                   ultima_conexao = NOW()
               WHERE device_id = %s""",
            (dados.status_sensor, dados.dispositivo_id)
        )
        
        # Verifica se temperatura está fora da faixa e gera alerta
        cur.execute(
            "SELECT temp_minima, temp_maxima FROM dispositivos WHERE device_id = %s",
            (dados.dispositivo_id,)
        )
        limites = cur.fetchone()
        
        if limites:
            temp_min, temp_max = limites
            if dados.temperatura > temp_max:
                cur.execute(
                    """INSERT INTO alertas (device_id, tipo_alerta, mensagem, valor_temperatura)
                       VALUES (%s, 'TEMP_ALTA', %s, %s)""",
                    (dados.dispositivo_id, f"Temperatura {dados.temperatura}°C acima do máximo {temp_max}°C", dados.temperatura)
                )
                # Atualiza status para ALERTA
                cur.execute(
                    "UPDATE dispositivos SET status_conexao = 'ALERTA' WHERE device_id = %s",
                    (dados.dispositivo_id,)
                )
            elif dados.temperatura < temp_min:
                cur.execute(
                    """INSERT INTO alertas (device_id, tipo_alerta, mensagem, valor_temperatura)
                       VALUES (%s, 'TEMP_BAIXA', %s, %s)""",
                    (dados.dispositivo_id, f"Temperatura {dados.temperatura}°C abaixo do mínimo {temp_min}°C", dados.temperatura)
                )
                cur.execute(
                    "UPDATE dispositivos SET status_conexao = 'ALERTA' WHERE device_id = %s",
                    (dados.dispositivo_id,)
                )
        
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Dados salvos com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no banco: {str(e)}")

# ============ NOVA ROTA: HEARTBEAT (ESP32 reporta status) ============
@app.post("/api/heartbeat")
def receber_heartbeat(dados: HeartbeatData, x_api_key: str = Header(None)):
    if x_api_key != os.getenv("API_SECRET_TOKEN"):
        raise HTTPException(status_code=401, detail="Token inválido")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """UPDATE dispositivos 
               SET status_conexao = 'ONLINE',
                   status_sensor = %s,
                   ultima_conexao = NOW()
               WHERE device_id = %s""",
            (dados.sensor_status, dados.dispositivo_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ NOVA ROTA: LISTAR DISPOSITIVOS COM STATUS ============
@app.get("/api/dispositivos")
def listar_dispositivos():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Atualiza dispositivos como OFFLINE se não reportaram nos últimos 2 minutos
        cur.execute("""
            UPDATE dispositivos 
            SET status_conexao = 'OFFLINE'
            WHERE ultima_conexao < NOW() - INTERVAL '2 minutes'
            AND status_conexao != 'ALERTA'
        """)
        
        cur.execute("""
            SELECT d.device_id, d.nome_setor, d.nome_freezer, 
                   d.status_conexao, d.status_sensor, d.ultima_conexao,
                   d.temp_minima, d.temp_maxima,
                   l.temperatura as ultima_temp, l.data_hora as ultima_leitura
            FROM dispositivos d
            LEFT JOIN LATERAL (
                SELECT temperatura, data_hora 
                FROM leituras_temperatura 
                WHERE dispositivo_id = d.device_id 
                ORDER BY data_hora DESC LIMIT 1
            ) l ON true
            WHERE d.ativo = true
            ORDER BY d.criado_em DESC
        """)
        
        dispositivos = cur.fetchall()
        cur.close()
        conn.close()
        
        resultado = []
        for d in dispositivos:
            resultado.append({
                "device_id": d[0],
                "nome_setor": d[1],
                "nome_freezer": d[2],
                "status_conexao": d[3],
                "status_sensor": d[4],
                "ultima_conexao": d[5].strftime("%d/%m/%Y %H:%M:%S") if d[5] else "Nunca",
                "temp_minima": float(d[6]),
                "temp_maxima": float(d[7]),
                "ultima_temp": float(d[8]) if d[8] else None,
                "ultima_leitura": d[9].strftime("%d/%m/%Y %H:%M") if d[9] else "Nunca"
            })
        
        return {"status": "sucesso", "dispositivos": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ NOVA ROTA: CADASTRAR DISPOSITIVO ============
@app.post("/api/dispositivos")
def cadastrar_dispositivo(dados: NovoDispositivo):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO dispositivos 
               (device_id, nome_setor, nome_freezer, temp_minima, temp_maxima)
               VALUES (%s, %s, %s, %s, %s)""",
            (dados.device_id, dados.nome_setor, dados.nome_freezer, 
             dados.temp_minima, dados.temp_maxima)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Dispositivo cadastrado!"}
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Device ID já existe!")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ NOVA ROTA: CONFIGURAÇÃO PARA ESP32 (via Captive Portal) ============
@app.get("/api/dispositivo/{device_id}/config")
def obter_config_dispositivo(device_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT wifi_ssid, wifi_password_encrypted, temp_minima, temp_maxima
               FROM dispositivos WHERE device_id = %s""",
            (device_id,)
        )
        config = cur.fetchone()
        cur.close()
        conn.close()
        
        if not config:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
        
        return {
            "device_id": device_id,
            "wifi_ssid": config[0] or "",
            "wifi_password": config[1] or "",
            "temp_minima": float(config[2]),
            "temp_maxima": float(config[3])
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ NOVA ROTA: SALVAR CONFIG DO WIFI (via Captive Portal) ============
@app.post("/api/dispositivo/{device_id}/wifi")
def salvar_wifi(device_id: str, dados: dict):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """UPDATE dispositivos 
               SET wifi_ssid = %s, wifi_password_encrypted = %s
               WHERE device_id = %s""",
            (dados.get("wifi_ssid"), dados.get("wifi_password"), device_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Wi-Fi configurado!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ ROTAS EXISTENTES (mantidas) ============
@app.get("/api/temperatura/historico")
def obter_historico(dispositivo_id: str = "esp32_01", limite: int = 20):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """SELECT temperatura, data_hora FROM leituras_temperatura 
               WHERE dispositivo_id = %s
               ORDER BY data_hora DESC LIMIT %s""",
            (dispositivo_id, limite)
        )
        registros = cur.fetchall()
        cur.close()
        conn.close()
        
        dados = [{"temperatura": float(r[0]), "data_hora": r[1].strftime("%H:%M:%S")} for r in registros]
        dados.reverse()
        return {"status": "sucesso", "dados": dados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/temperatura/resumo")
def obter_resumo(dispositivo_id: str = "esp32_01"):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "SELECT AVG(temperatura) FROM leituras_temperatura WHERE dispositivo_id = %s",
            (dispositivo_id,)
        )
        media_result = cur.fetchone()
        temperatura_media = float(media_result[0]) if media_result[0] else 0.0
        
        cur.execute(
            """SELECT temperatura, data_hora FROM leituras_temperatura 
               WHERE dispositivo_id = %s
               ORDER BY data_hora DESC LIMIT 5""",
            (dispositivo_id,)
        )
        ultimas_leituras = cur.fetchall()
        
        cur.close()
        conn.close()
        
        leituras_formatadas = [
            {"temperatura": float(r[0]), "data_hora": r[1].strftime("%d/%m %H:%M:%S")}
            for r in ultimas_leituras
        ]
        
        return {
            "status": "sucesso",
            "temperatura_media": round(temperatura_media, 2),
            "ultimas_leituras": leituras_formatadas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))