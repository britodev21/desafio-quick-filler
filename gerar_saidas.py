"""
Gera as planilhas de todos os PDFs de exemplos/ em saidas/, nos tres formatos.

Roda o lote inteiro de uma vez: descobre o tipo de cada documento, chama o
extrator correspondente e grava xlsx, csv e json. Arquivo que nao da pra
processar nao interrompe os outros - o motivo fica registrado e aparece no
resumo do fim.

Uso:
    python gerar_saidas.py

Sai com codigo 1 se algum arquivo falhou, pra servir em automacao.
"""

import logging
import sys
import traceback
from pathlib import Path

import pdfplumber

RAIZ = Path(__file__).resolve().parent

# O backend importa como pacote ("from backend.extrator import ..."), igual o
# main.py faz. Garantir a raiz no sys.path deixa rodar de qualquer pasta.
sys.path.insert(0, str(RAIZ))

from backend.extrator import processar_cartao_ponto  # noqa: E402
from backend.extrator_holerite import processar_holerite  # noqa: E402
from backend.planilha import GERADORES  # noqa: E402

DIRETORIO_EXEMPLOS = RAIZ / "exemplos"
DIRETORIO_SAIDAS = RAIZ / "saidas"

CARTAO_PONTO = "cartao-ponto"
HOLERITE = "holerite"

EXTRATORES = {
    CARTAO_PONTO: processar_cartao_ponto,
    HOLERITE: processar_holerite,
}

"""
Prefixos aceitos por tipo. Sao dois por tipo de proposito: os arquivos em
exemplos/ vieram em ingles (time-card-01.pdf), mas o README da pasta descreve
os mesmos documentos em portugues (cartao-ponto-1.pdf). Aceitar os dois evita
que um exemplo renomeado apareca no resumo como falha sem ser.
"""
PREFIXOS = {
    CARTAO_PONTO: ("time-card", "cartao-ponto"),
    HOLERITE: ("payroll", "holerite"),
}

"""
Marcas do texto pra quando o nome nao denuncia o tipo. Sao as mesmas ancoras
que cada extrator usa pra achar a tabela, entao o que casa aqui e o que ele
consegue ler la.
"""
MARCAS = {
    CARTAO_PONTO: ("Entrada", "Saida"),
    HOLERITE: ("Cod.", "Proventos"),
}

OK = "OK"
FALHOU = "FALHOU"

"""
Minimo de caracteres pra considerar que uma pagina tem texto de verdade.

PDF escaneado que passou por processo judicial costuma vir com uma tarja de
texto por cima ("Assinado eletronicamente por: ... - Juntado em: ..."), entao
"tem texto" e "da pra ler o documento" nao sao a mesma coisa: o payroll-04
devolve 83 caracteres por pagina, todos da tarja, e o resto e imagem.

200 fica bem no meio da separacao medida nos exemplos: a tarja da 83 e a
pagina mais pobre com conteudo de verdade da 885.
"""
LIMIAR_TEXTO_UTIL = 200


def descobrir_tipo_pelo_nome(caminho_pdf):
    """Devolve o tipo pelo prefixo do nome, ou None se nenhum casar."""
    nome = caminho_pdf.stem.lower()

    for tipo, prefixos in PREFIXOS.items():
        if nome.startswith(prefixos):
            return tipo

    return None


def descobrir_tipo_pelo_conteudo(caminho_pdf):
    """
    Devolve o tipo olhando o texto das primeiras paginas, ou None.

    Fallback pra documento com nome fora do padrao. O README de exemplos avisa
    que os arquivos sao amostra, e nao especificacao: chutar pelo nome e so a
    primeira tentativa, nao a unica.

    Le no maximo tres paginas porque a primeira pode ser capa ou vir vazia num
    PDF misto, e varrer o arquivo inteiro sem necessidade custa caro.
    """
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            textos = [pagina.extract_text() or "" for pagina in pdf.pages[:3]]
    except Exception:
        return None

    texto = "\n".join(textos)

    for tipo, marcas in MARCAS.items():
        if all(marca in texto for marca in marcas):
            return tipo

    return None


def medir_texto(caminho_pdf):
    """
    Devolve (total de paginas, paginas com texto util, maior pagina em chars).

    So e chamado quando a extracao nao rendeu nada, pra separar "PDF e imagem"
    de "PDF tem texto mas o layout nao foi reconhecido". Sao motivos
    diferentes e levam a solucoes diferentes: um pede OCR, o outro pede mexer
    no extrator.
    """
    with pdfplumber.open(caminho_pdf) as pdf:
        tamanhos = [
            len((pagina.extract_text() or "").strip()) for pagina in pdf.pages
        ]

    uteis = sum(1 for tamanho in tamanhos if tamanho >= LIMIAR_TEXTO_UTIL)

    return len(tamanhos), uteis, max(tamanhos, default=0)


def medir_extracao(tipo, dados):
    """
    Mede o que o extrator rendeu: (paginas com dado, total de paginas, itens).

    "Itens" e batida no cartao de ponto e verba no holerite - a unidade que
    prova que a leitura funcionou. Contar pagina nao serve: os dois extratores
    devolvem uma entrada por pagina do PDF mesmo quando nao acharam nada.
    """
    paginas = dados["pages"]

    if tipo == CARTAO_PONTO:
        com_dado = sum(1 for pagina in paginas if pagina["days"])
        itens = sum(
            len(dia["punches"]) for pagina in paginas for dia in pagina["days"]
        )
    else:
        com_dado = sum(1 for pagina in paginas if pagina["fields"])
        itens = sum(len(pagina["fields"]) for pagina in paginas)

    return com_dado, len(paginas), itens


def explicar_extracao_vazia(caminho_pdf, tipo):
    """
    Diz por que a extracao nao rendeu nada, abrindo o PDF pra olhar o texto.

    Sem isso o resumo diria so "nao extraiu", que nao ajuda ninguem a decidir
    o que fazer: falta de OCR e layout desconhecido tem causas distintas.
    """
    try:
        total, uteis, maior = medir_texto(caminho_pdf)
    except Exception as erro:
        return f"não extraiu nada e o PDF não pôde ser reaberto: {erro}"

    if maior == 0:
        return (
            f"PDF sem camada de texto ({total} páginas, todas imagem): "
            "precisa passar por OCR, que ainda não está no pipeline"
        )

    if uteis == 0:
        """
        Tem texto, mas pouco demais pra ser o documento. Chamar isso de
        "layout nao reconhecido" mandaria alguem depurar o extrator quando o
        que falta e OCR.
        """
        return (
            f"PDF é imagem com uma tarja de texto por cima (no máximo {maior} "
            f"caracteres por página, contra as {LIMIAR_TEXTO_UTIL} que um "
            "documento legível teria): o conteúdo está na imagem e precisa "
            "de OCR"
        )

    if uteis < total:
        return (
            f"o extrator de {tipo} não encontrou dado em nenhuma página "
            f"(só {uteis} de {total} páginas têm texto legível; as demais "
            "são imagem e precisam de OCR)"
        )

    return (
        f"o PDF tem texto nas {total} páginas, mas o extrator de {tipo} não "
        "reconheceu a tabela: layout diferente do esperado"
    )


def gerar_formatos(dados, tipo, nome_base):
    """
    Grava os tres formatos e devolve (formatos gravados, lista de erros).

    Um formato por try: se o xlsx quebrar, o csv e o json ainda saem, e a
    falha aparece no resumo em vez de sumir junto com os outros dois.
    """
    gerados = []
    erros = []

    for formato, gerador in GERADORES[tipo].items():
        caminho = DIRETORIO_SAIDAS / f"{nome_base}.{formato}"

        try:
            gerador(dados, str(caminho))
            gerados.append(formato)
        except Exception as erro:
            erros.append(f"{formato}: {type(erro).__name__}: {erro}")

    return gerados, erros


def processar_arquivo(caminho_pdf):
    """
    Trata UM PDF de ponta a ponta e devolve o registro dele pro resumo.

    Nunca levanta: qualquer falha vira status FALHOU com motivo, pra que um
    arquivo problematico nao leve o lote inteiro junto.
    """
    registro = {
        "arquivo": caminho_pdf.name,
        "tipo": None,
        "status": FALHOU,
        "motivo": "",
        "detalhe": "",
        "formatos": [],
    }

    tipo = descobrir_tipo_pelo_nome(caminho_pdf)

    if tipo is None:
        tipo = descobrir_tipo_pelo_conteudo(caminho_pdf)

        if tipo is None:
            registro["motivo"] = (
                "não deu pra identificar o tipo do documento: o nome não "
                "segue os prefixos conhecidos e o texto não tem as marcas de "
                "cartão de ponto nem de holerite"
            )
            return registro

        registro["detalhe"] = "tipo deduzido pelo conteúdo, não pelo nome"

    registro["tipo"] = tipo

    try:
        dados = EXTRATORES[tipo](str(caminho_pdf))
    except Exception as erro:
        registro["motivo"] = f"erro no extrator: {type(erro).__name__}: {erro}"
        # O traceback fica so no detalhe, que o resumo nao imprime: ele serve
        # pra quem for depurar, nao pra tabela final.
        registro["detalhe"] = traceback.format_exc().strip()
        return registro

    com_dado, total_paginas, itens = medir_extracao(tipo, dados)

    if itens == 0:
        """
        Extracao vazia nao e sucesso. Gerar planilha aqui produziria um xlsx
        so com cabecalho em saidas/, que passa por entregavel valido e esconde
        o problema - que e justamente o que este script existe pra evitar.
        """
        registro["motivo"] = explicar_extracao_vazia(caminho_pdf, tipo)
        return registro

    gerados, erros = gerar_formatos(dados, tipo, caminho_pdf.stem)
    registro["formatos"] = gerados

    unidade = "batidas" if tipo == CARTAO_PONTO else "verbas"
    resumo_dado = (
        f"{com_dado}/{total_paginas} páginas com dado, {itens} {unidade}"
    )

    if erros:
        registro["motivo"] = "falha ao gravar: " + "; ".join(erros)

        if gerados:
            # Saida parcial continua sendo falha, mas o resumo precisa dizer o
            # que sobrou em disco.
            registro["detalhe"] = (
                f"{resumo_dado}; gravados mesmo assim: {', '.join(gerados)}"
            )

        return registro

    registro["status"] = OK

    if registro["detalhe"]:
        registro["detalhe"] = f"{resumo_dado} ({registro['detalhe']})"
    else:
        registro["detalhe"] = resumo_dado

    if com_dado < total_paginas:
        """
        Pagina vazia dentro de um arquivo que funcionou nao invalida a
        planilha, mas precisa aparecer: pode ser pagina de rosto e pode ser
        dado perdido, e so quem olha o PDF sabe qual dos dois.
        """
        registro["detalhe"] += (
            f" - atenção: {total_paginas - com_dado} página(s) sem dado"
        )

    return registro


def imprimir_resumo(registros):
    """
    Imprime o resumo final e devolve quantos arquivos falharam.

    Separa por status em vez de repetir a ordem do lote: no fim da execucao o
    que interessa e a lista do que precisa de acao, junta.
    """
    sucessos = [r for r in registros if r["status"] == OK]
    falhas = [r for r in registros if r["status"] != OK]

    print()
    print("=" * 72)
    print(f"RESUMO: {len(sucessos)} de {len(registros)} arquivos gerados")
    print("=" * 72)

    if sucessos:
        print()
        print(f"Deram certo ({len(sucessos)}):")

        for registro in sucessos:
            print(f"  [OK] {registro['arquivo']}  ({registro['tipo']})")
            print(
                f"       saidas/{Path(registro['arquivo']).stem}."
                f"{{{','.join(registro['formatos'])}}}"
            )
            print(f"       {registro['detalhe']}")

    if falhas:
        print()
        print(f"Não deram certo ({len(falhas)}):")

        for registro in falhas:
            tipo = registro["tipo"] or "tipo desconhecido"
            print(f"  [FALHOU] {registro['arquivo']}  ({tipo})")
            print(f"           motivo: {registro['motivo']}")

            # Traceback tem quebra de linha; no resumo entra so detalhe curto.
            if registro["detalhe"] and "\n" not in registro["detalhe"]:
                print(f"           {registro['detalhe']}")

    print()

    return len(falhas)


def main():
    """
    Configura o log em WARNING de proposito: os extratores falam em DEBUG (e
    ligar isso traria junto megabytes do parser do pdfminer), mas planilha.py
    avisa em WARNING quando uma verba repete na mesma pagina, e esse aviso tem
    que aparecer.
    """
    logging.basicConfig(format="  aviso: %(message)s", level=logging.WARNING)

    if not DIRETORIO_EXEMPLOS.is_dir():
        print(f"Pasta não encontrada: {DIRETORIO_EXEMPLOS}")
        return 1

    DIRETORIO_SAIDAS.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(DIRETORIO_EXEMPLOS.glob("*.pdf"))

    if not pdfs:
        print(f"Nenhum PDF em {DIRETORIO_EXEMPLOS}")
        return 1

    print(f"{len(pdfs)} PDFs em exemplos/ -> saidas/ (xlsx, csv, json)")
    print()

    registros = []

    for numero, caminho_pdf in enumerate(pdfs, start=1):
        # Impresso antes de processar: PDF grande demora, e sem isso a tela
        # fica parada sem dizer em qual arquivo esta.
        print(f"[{numero}/{len(pdfs)}] {caminho_pdf.name}")

        registro = processar_arquivo(caminho_pdf)
        registros.append(registro)

        if registro["status"] == OK:
            print(f"  OK - {registro['detalhe']}")
        else:
            print(f"  FALHOU - {registro['motivo']}")

    return 1 if imprimir_resumo(registros) else 0


if __name__ == "__main__":
    sys.exit(main())
