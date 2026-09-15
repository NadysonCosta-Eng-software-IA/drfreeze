import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="API de Temperatura ESP32 + Dashboard")

# Servir arquivos estáticos (HTML, CSS, JS) da pasta "static"
app.mount("/static", StaticFiles(directory="static"), name="static")

class LeituraSensor(BaseModel):
    dispositivo_id: str
    temperatura: float

def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

# Rota raiz: serve o arquivo HTML do dashboard
@app.get("/")
def root():
    return FileResponse("static/index.html")

# Rota POST: Recebe dados do ESP32 (já existente)
@app.post("/api/temperatura")
def receber_leitura(dados: LeituraSensor, x_api_key: str = Header(None)):
    if x_api_key != os.getenv("API_SECRET_TOKEN"):
        raise HTTPException(status_code=401, detail="Token inválido")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO leituras_temperatura (dispositivo_id, temperatura) VALUES (%s, %s)",
            (dados.dispositivo_id, dados.temperatura)
        )
        conn.commit()
        cur.close()
        conn.close()
        return {"status": "sucesso", "mensagem": "Dados salvos com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no banco: {str(e)}")

# Rota GET: Fornece o histórico para o Dashboard
@app.get("/api/temperatura/historico")
def obter_historico(limite: int = 20):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Busca as últimas leituras, ordenadas por data
        cur.execute(
            "SELECT temperatura, data_hora FROM leituras_temperatura ORDER BY data_hora DESC LIMIT %s", 
            (limite,)
        )
        registros = cur.fetchall()
        cur.close()
        conn.close()
        
        # Formata os dados para o frontend e inverte a ordem (do mais antigo para o mais recente)
        dados = [{"temperatura": float(r[0]), "data_hora": r[1].strftime("%H:%M:%S")} for r in registros]
        dados.reverse() 
        
        return {"status": "sucesso", "dados": dados}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados: {str(e)}")

# Rota GET: Fornece resumo estatístico (média + últimas 5 leituras)
@app.get("/api/temperatura/resumo")
def obter_resumo():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Calcula a temperatura média de todas as leituras
        cur.execute("SELECT AVG(temperatura) FROM leituras_temperatura")
        media_result = cur.fetchone()
        temperatura_media = float(media_result[0]) if media_result[0] else 0.0
        
        # 2. Busca as 5 últimas leituras
        cur.execute(
            "SELECT temperatura, data_hora FROM leituras_temperatura ORDER BY data_hora DESC LIMIT 5"
        )
        ultimas_leituras = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Formata as últimas leituras
        leituras_formatadas = [
            {
                "temperatura": float(r[0]),
                "data_hora": r[1].strftime("%d/%m %H:%M:%S")
            }
            for r in ultimas_leituras
        ]
        
        return {
            "status": "sucesso",
            "temperatura_media": round(temperatura_media, 2),
            "ultimas_leituras": leituras_formatadas
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar resumo: {str(e)}")