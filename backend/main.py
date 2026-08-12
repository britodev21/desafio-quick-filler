from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Correcao(BaseModel):
    value: dict

@app.get("/healthz")
def health_check():
    return {"status": "ok"
}

@app.get("/api/transcricoes/{id}")
def get_transcricao(id: str):
    return {"id": id,
            "tipo": "cartao-ponto",
            "status": "concluido",
            "erro": None,
            "value": None,
}

@app.put("/api/transcricoes/{id}")
def put_transcricao(id: str, correcao: Correcao):
    return {"id": id,
            "recebido": correcao.value
}

@app.get("/api/transcricoes/{id}/planilha")
def get_planilha(id: str, formato: str = "xlsx"):
    return {"id": id,
            "planilha": f"planilha.{formato}"
}