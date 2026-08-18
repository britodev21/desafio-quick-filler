import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import (
    BackgroundTasks,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from backend.extrator import processar_cartao_ponto
from backend.extrator_holerite import processar_holerite

logger = logging.getLogger(__name__)

app = FastAPI()
transcricoes = {}

# Caminho a partir do arquivo, e nao do cwd, pra funcionar rodando de
# qualquer pasta.
DIRETORIO_UPLOADS = Path(__file__).resolve().parent.parent / "uploads"
DIRETORIO_UPLOADS.mkdir(parents=True, exist_ok=True)

# Todo PDF comeca com esses bytes. A extensao do nome nao prova nada.
ASSINATURA_PDF = b"%PDF"

# Fonte unica da verdade: valida o tipo recebido e escolhe o extrator.
EXTRATORES = {
    "cartao-ponto": processar_cartao_ponto,
    "holerite": processar_holerite,
}

"""
Mensagem unica de falha, de proposito. Nao diz caminho de arquivo, nome de
funcao nem trecho do documento: quem le isso e o cliente da API, e o holerite
e de outra pessoa. O detalhe de verdade vai pro log do servidor.
"""
MENSAGEM_ERRO = (
    "Não foi possível extrair os dados deste documento. "
    "Verifique se o PDF corresponde ao tipo informado."
)


def processar_documento(id_transcricao: str, caminho_pdf: Path, tipo: str):
    """
    Roda o extrator do tipo e guarda o resultado na transcricao.

    Roda em background: ninguem esta esperando o retorno, entao tudo que
    importa - sucesso ou falha - tem que acabar em transcricoes[id].
    """
    try:
        extrator = EXTRATORES[tipo]
        transcricoes[id_transcricao]["value"] = extrator(str(caminho_pdf))
        transcricoes[id_transcricao]["status"] = "concluido"
        transcricoes[id_transcricao]["erro"] = None

    except Exception:
        """
        O traceback completo vai pro log do servidor, onde pode ter caminho de
        arquivo e trecho do documento. Pra transcricao vai so a mensagem
        generica. Sem esse log, uma falha de parsing viraria um erro mudo.
        """
        logger.exception(
            "Falha ao processar a transcricao %s (tipo %s)",
            id_transcricao,
            tipo,
        )
        transcricoes[id_transcricao]["status"] = "erro"
        transcricoes[id_transcricao]["erro"] = MENSAGEM_ERRO
        transcricoes[id_transcricao]["value"] = None

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
    if id not in transcricoes:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")
    transcricoes[id]["value"] = correcao.value
    return {"id": id,
            "recebido": correcao.value
}


@app.get("/api/transcricoes/{id}/planilha")
def get_planilha(id: str, formato: str = "xlsx"):
    return {"id": id,
            "planilha": f"planilha.{formato}"
}

@app.post("/api/transcricoes", status_code=202)
async def criar_transcricao(
    tarefas: BackgroundTasks,
    arquivo: Annotated[UploadFile, File()],
    tipo: Annotated[str, Form()],
):
    if tipo not in EXTRATORES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo inválido. Use um destes: {', '.join(EXTRATORES)}.",
        )

    conteudo = await arquivo.read()

    """
    Le o arquivo inteiro antes de gravar pra checar a assinatura: assim um
    upload invalido nunca deixa um .pdf pela metade em uploads/.
    """
    if not conteudo.startswith(ASSINATURA_PDF):
        raise HTTPException(
            status_code=400,
            detail="O arquivo enviado não é um PDF.",
        )

    novo_id = str(uuid.uuid4())

    # O nome do arquivo e o uuid que nos geramos, nunca o nome que veio do
    # cliente, entao nao da pra escapar do diretorio.
    caminho_pdf = DIRETORIO_UPLOADS / f"{novo_id}.pdf"
    caminho_pdf.write_bytes(conteudo)

    transcricoes[novo_id] = {
        "id": novo_id,
        "tipo": tipo,
        "status": "processando",
        "erro": None,
        "value": None,
    }

    tarefas.add_task(processar_documento, novo_id, caminho_pdf, tipo)

    return {"id": novo_id}
