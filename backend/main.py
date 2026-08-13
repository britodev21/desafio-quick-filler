import uuid
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI()
transcricoes = {}

class Correcao(BaseModel):
    value: dict

@app.get("/healthz")
def health_check():
    return {"status": "ok"
}

@app.get("/api/transcricoes/{id}")
def get_transcricao(id: str):
    if id not in transcricoes:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")
    return transcricoes[id]


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

@app.post("/api/transcricoes", status_code=202)
def criar_transcricao(
    arquivo: Annotated[UploadFile, File()],
    tipo: Annotated[str, Form()],
):
    novo_id = str(uuid.uuid4())
    transcricoes[novo_id] = {
            "id": novo_id,
            "tipo": tipo,
            "status": "processando",
            "erro": None,
            "value": None,
}
    return {"id": novo_id}
