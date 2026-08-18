import logging
import uuid
from contextlib import asynccontextmanager
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
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.extrator import processar_cartao_ponto
from backend.extrator_holerite import processar_holerite
from backend.planilha import GERADORES

"""
main.py e o ponto de entrada da aplicacao, entao e aqui que o logging se
configura. Sem isso o uvicorn deixa o logger raiz em WARNING e todo INFO
nosso e descartado em silencio.

INFO e nao DEBUG de proposito: o DEBUG do logger raiz liga junto o do
pdfminer, que despeja megabytes de log do parser a cada PDF lido.
"""
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)

transcricoes = {}

# Caminho a partir do arquivo, e nao do cwd, pra funcionar rodando de
# qualquer pasta.
DIRETORIO_UPLOADS = Path(__file__).resolve().parent.parent / "uploads"
DIRETORIO_UPLOADS.mkdir(parents=True, exist_ok=True)

# Todo PDF comeca com esses bytes. A extensao do nome nao prova nada.
ASSINATURA_PDF = b"%PDF"

# Planilhas geradas. Separado de saidas/, que guarda os entregaveis do
# desafio: aqui e artefato de execucao, um arquivo por transcricao.
DIRETORIO_PLANILHAS = Path(__file__).resolve().parent.parent / "planilhas"
DIRETORIO_PLANILHAS.mkdir(parents=True, exist_ok=True)

# Fonte unica da verdade: valida o formato pedido e da o Content-Type.
TIPOS_DE_MIDIA = {
    "xlsx": (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
    ),
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
}

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


def limpar_diretorio(diretorio):
    """
    Apaga os arquivos soltos do diretorio e devolve quantos sairam.

    Um arquivo travado nao derruba a subida: vira aviso no log e a aplicacao
    segue. Nao lista nome de arquivo em log nenhum.
    """
    removidos = 0
    falhas = 0

    for caminho in diretorio.iterdir():
        if not caminho.is_file():
            continue

        try:
            caminho.unlink()
            removidos += 1
        except OSError:
            falhas += 1

    if falhas:
        logger.warning(
            "limpeza de %s/: %s arquivos nao puderam ser removidos",
            diretorio.name,
            falhas,
        )

    return removidos


@asynccontextmanager
async def ciclo_de_vida(app):
    """
    Na subida, esvazia uploads/ e planilhas/.

    transcricoes nasce vazio a cada inicio, entao qualquer arquivo que tenha
    sobrado de uma execucao anterior e orfao: nao existe id que o referencie e
    nenhuma rota vai servi-lo de novo.
    """
    for diretorio in (DIRETORIO_UPLOADS, DIRETORIO_PLANILHAS):
        logger.info(
            "limpeza de inicio: %s arquivos removidos de %s/",
            limpar_diretorio(diretorio),
            diretorio.name,
        )

    yield


app = FastAPI(lifespan=ciclo_de_vida)


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
    if id not in transcricoes:
        raise HTTPException(status_code=404, detail="Transcrição não encontrada")

    transcricao = transcricoes[id]

    if transcricao["status"] != "concluido":
        """
        409 e nao 404: a transcricao existe, o que nao da e gerar planilha de
        um documento que ainda esta processando ou que falhou.
        """
        raise HTTPException(
            status_code=409,
            detail=(
                "A transcrição ainda não está pronta "
                f"(status: {transcricao['status']})."
            ),
        )

    if formato not in TIPOS_DE_MIDIA:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Formato inválido. Use um destes: "
                f"{', '.join(TIPOS_DE_MIDIA)}."
            ),
        )

    gerador = GERADORES[transcricao["tipo"]][formato]

    """
    Gera do value atual, que e o corrigido quando houve PUT - o contrato pede
    a planilha ja com as correcoes aplicadas.

    O nome do arquivo leva o id pra dois pedidos de transcricoes diferentes
    nao brigarem pelo mesmo arquivo em disco.
    """
    caminho = DIRETORIO_PLANILHAS / f"{id}.{formato}"
    gerador(transcricao["value"], str(caminho))

    return FileResponse(
        path=caminho,
        media_type=TIPOS_DE_MIDIA[formato],
        # Em disco vale o id; pro usuario, um nome que diz o que e.
        filename=f"{transcricao['tipo']}-{id[:8]}.{formato}",
    )

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


"""
O front buildado é servido pelo próprio FastAPI, e este bloco fica no fim do
arquivo de propósito: o Starlette casa as rotas na ordem em que foram
registradas, então o catch-all abaixo só é alcançado depois que /healthz e
todas as /api já tiveram sua chance.

Em desenvolvimento a pasta não existe - quem serve o front é o Vite, com
proxy pra cá - e aí nada disso é registrado.
"""
DIRETORIO_FRONT = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if DIRETORIO_FRONT.is_dir():

    @app.get("/{caminho:path}")
    def servir_front(caminho: str):
        """
        Devolve o arquivo estático quando ele existe e o index.html no resto,
        que é o que uma aplicação de página única precisa pra sobreviver a um
        F5 numa rota interna.
        """
        if caminho.startswith("api/"):
            # Sem isso, /api/rota-errada devolveria o index.html com 200 e o
            # cliente receberia HTML onde esperava JSON.
            raise HTTPException(status_code=404, detail="Rota não encontrada")

        alvo = (DIRETORIO_FRONT / caminho).resolve()

        # O is_relative_to barra "../": sem ele, um caminho montado na mão
        # leria arquivo de fora da pasta do front.
        if (
            caminho
            and alvo.is_file()
            and alvo.is_relative_to(DIRETORIO_FRONT)
        ):
            return FileResponse(alvo)

        return FileResponse(DIRETORIO_FRONT / "index.html")
