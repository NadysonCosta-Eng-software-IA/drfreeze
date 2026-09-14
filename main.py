import os
import psycopg2
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

app = FastAPI(title="API de Temperatura ESP32")

# Modelo de dados que a API espera receber
class LeituraSensor(BaseModel):
    dispositivo_id: str
    temperatura: float

# Função para conectar ao banco
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

@app.post("/api/temperatura")
def receber_leitura(dados: LeituraSensor, x_api_key: str = Header(None)):
    # 1. Segurança básica: verifica se o ESP32 enviou a chave correta
    if x_api_key != os.getenv("API_SECRET_TOKEN"):
        raise HTTPException(status_code=401, detail="Token inválido")

    # 2. Conectar ao banco e inserir os dados
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
        raise HTTPException(status_code=500, detail=f"Erro no banco de dados: {str(e)}")

@app.get("/")
def root():
    return {"mensagem": "API de Temperatura está no ar!"}