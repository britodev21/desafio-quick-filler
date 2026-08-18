import logging
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side

logger = logging.getLogger(__name__)

COR_CABECALHO = "173772"
COR_AMARELO = "FFF3CD"
COR_VERMELHO = "F8D7DA"
COR_BORDA_VERMELHA = "DC3545"

FONTE_CABECALHO = Font(bold=True, color="FFFFFF")
FUNDO_CABECALHO = PatternFill("solid", start_color=COR_CABECALHO)
FUNDO_AMARELO = PatternFill("solid", start_color=COR_AMARELO)
FUNDO_VERMELHO = PatternFill("solid", start_color=COR_VERMELHO)
BORDA_VERMELHA = Border(left=Side(style="medium", color=COR_BORDA_VERMELHA))

LARGURA_MINIMA = 12
LARGURA_MAXIMA = 30


# ---------------------------------------------------------------------------
# Pecas compartilhadas pelas duas planilhas
# ---------------------------------------------------------------------------


def escrever_cabecalho(aba, colunas):
    aba.append(colunas)

    for celula in aba[1]:
        celula.font = FONTE_CABECALHO
        celula.fill = FUNDO_CABECALHO


def escrever_linha(aba, numero_linha, valores, largura, aviso):
    """
    Escreve uma linha de dados ja com o destaque aplicado.

    Escreve celula a celula em vez de append() pra garantir que o
    preenchimento cubra a largura toda da linha, inclusive as colunas que
    ficam vazias - que na planilha do holerite sao a maioria.
    """
    # Vermelho ganha do amarelo quando os dois valem pra mesma linha.
    if aviso["nao_sequencial"]:
        fundo = FUNDO_VERMELHO
    elif aviso["amarelo"]:
        fundo = FUNDO_AMARELO
    else:
        fundo = None

    for numero_coluna in range(1, largura + 1):
        celula = aba.cell(row=numero_linha, column=numero_coluna)

        if numero_coluna <= len(valores):
            celula.value = valores[numero_coluna - 1]

        if fundo is not None:
            celula.fill = fundo

    if aviso["nao_sequencial"]:
        aba.cell(row=numero_linha, column=1).border = BORDA_VERMELHA


def ajustar_larguras(aba, cabecalho):
    for numero_coluna, titulo in enumerate(cabecalho, start=1):
        letra = aba.cell(row=1, column=numero_coluna).column_letter
        largura = max(LARGURA_MINIMA, min(len(titulo) + 2, LARGURA_MAXIMA))
        aba.column_dimensions[letra].width = largura


def tem_incerteza(textos):
    """O "?" do contrato marca caractere que nao deu pra ler com seguranca."""
    return any("?" in (texto or "") for texto in textos)


# ---------------------------------------------------------------------------
# Cartao de ponto
# ---------------------------------------------------------------------------


def linhas_do_cartao_ponto(dados):
    """
    Achata as paginas numa lista unica de dias, na ordem do documento.

    Nao ordena por data de proposito: a planilha tem que refletir a ordem em
    que os dias aparecem no PDF, senao uma data fora de lugar - que e
    justamente o que o aviso de nao-sequencial existe pra mostrar - sumiria
    depois de ordenar.
    """
    return [dia for pagina in dados["pages"] for dia in pagina["days"]]


def ler_data(date_raw):
    """
    "01/07/2012" -> date. Devolve None quando nao da pra ler, que e o caso de
    uma data com "?" de caractere ilegivel.
    """
    try:
        return datetime.strptime(date_raw, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return None


def contar_pares(linhas):
    """
    Quantos pares Entrada/Saida a planilha precisa, olhando o dia com mais
    batidas. Arredonda pra cima: um dia com 1 batida so ainda ocupa um par
    inteiro, com a Saida vazia.
    """
    maximo = max((len(linha["punches"]) for linha in linhas), default=0)
    return (maximo + 1) // 2


def montar_cabecalho_cartao_ponto(pares):
    colunas = ["Data"]

    for numero in range(1, pares + 1):
        colunas.append(f"Entrada {numero}")
        colunas.append(f"Saída {numero}")

    return colunas


def derivar_avisos_cartao_ponto(linhas):
    """
    Calcula os avisos de cada dia a partir do proprio dado, na hora de gerar.

    Nenhum deles e campo do JSON: batida impar sai de contar os punches, e
    nao-sequencial sai de comparar com a linha anterior.

    Uma data ilegivel nao quebra a cadeia: ela mesma nao vira aviso vermelho, e
    a proxima data legivel e comparada com a ultima legivel, nao com ela.
    """
    avisos = []
    ultima_data = None

    for linha in linhas:
        data = ler_data(linha["date_raw"])

        textos = [linha["date_raw"]]
        for punch in linha["punches"]:
            textos.append(punch["time_raw"])
            textos.append(punch["time_hhmm"])

        incerto = tem_incerteza(textos)
        impar = len(linha["punches"]) % 2 != 0

        if data is None or ultima_data is None:
            # Primeira linha, ou data ilegivel: nao ha com o que comparar.
            nao_sequencial = False
        else:
            nao_sequencial = (data - ultima_data).days != 1

        if data is not None:
            ultima_data = data

        avisos.append({
            "impar": impar,
            "incerto": incerto,
            "amarelo": impar or incerto,
            "nao_sequencial": nao_sequencial,
        })

    return avisos


def gerar_planilha_cartao_ponto(dados, caminho_saida):
    """
    Escreve o xlsx do cartao de ponto e devolve o caminho.

    Uma linha por dia, uma coluna Data mais os pares Entrada/Saida.
    """
    linhas = linhas_do_cartao_ponto(dados)
    cabecalho = montar_cabecalho_cartao_ponto(contar_pares(linhas))
    avisos = derivar_avisos_cartao_ponto(linhas)

    planilha = Workbook()
    aba = planilha.active
    aba.title = "Cartão de ponto"

    escrever_cabecalho(aba, cabecalho)

    for numero_linha, (linha, aviso) in enumerate(zip(linhas, avisos), start=2):
        valores = [linha["date_raw"]]
        valores += [punch["time_hhmm"] for punch in linha["punches"]]

        escrever_linha(aba, numero_linha, valores, len(cabecalho), aviso)

    aba.freeze_panes = "A2"
    ajustar_larguras(aba, cabecalho)
    planilha.save(caminho_saida)

    logger.debug(
        "planilha de cartao de ponto: %s linhas, %s colunas, %s destaques",
        len(linhas),
        len(cabecalho),
        sum(1 for a in avisos if a["amarelo"] or a["nao_sequencial"]),
    )

    return caminho_saida


# ---------------------------------------------------------------------------
# Holerite
# ---------------------------------------------------------------------------


def colunas_de_verbas(dados):
    """
    Uniao de todos os label de fields, na ordem de primeira aparicao no
    documento.

    dict.fromkeys guarda a ordem de insercao e ignora repetido, que e
    exatamente "primeira aparicao vence".
    """
    return list(dict.fromkeys(
        field["label"]
        for pagina in dados["pages"]
        for field in pagina["fields"]
    ))


def valores_por_verba(pagina):
    """
    Mapeia label -> value dentro de uma pagina.

    Se a mesma verba aparecer duas vezes na mesma pagina, a primeira vence e a
    segunda vira aviso no log: a planilha tem uma celula so pra ela, entao
    escolher em silencio esconderia um dado do documento.
    """
    valores = {}

    for field in pagina["fields"]:
        if field["label"] in valores:
            logger.warning(
                "pagina %s: verba %r aparece mais de uma vez, mantendo o "
                "primeiro valor (%r) e ignorando %r",
                pagina["page"],
                field["label"],
                valores[field["label"]],
                field["value"],
            )
            continue

        valores[field["label"]] = field["value"]

    return valores


def ler_competencia(pagina):
    """
    Vira a competencia num numero absoluto de meses (ano * 12 + mes).

    Compara em meses absolutos pra dezembro -> janeiro contar como
    consecutivo. Devolve None quando a competencia nao deu pra ler.
    """
    try:
        return int(pagina["year"]) * 12 + int(pagina["month"])
    except (ValueError, TypeError):
        return None


def derivar_avisos_holerite(paginas):
    """
    Calcula os avisos de cada pagina a partir do proprio dado.

    Pagina vazia e a que nao rendeu verba nenhuma - a linha dela sai so com
    Pag./Mes/Ano e o resto em branco, entao precisa saltar aos olhos.

    Competencia ilegivel nao quebra a cadeia: ela mesma nao vira vermelho, e a
    proxima legivel e comparada com a ultima legivel, nao com ela.
    """
    avisos = []
    ultima_competencia = None

    for pagina in paginas:
        competencia = ler_competencia(pagina)

        textos = [pagina["month"], pagina["year"]]
        textos += [field["value"] for field in pagina["fields"]]

        vazia = not pagina["fields"]
        incerto = tem_incerteza(textos)

        if competencia is None or ultima_competencia is None:
            nao_sequencial = False
        else:
            nao_sequencial = competencia - ultima_competencia != 1

        if competencia is not None:
            ultima_competencia = competencia

        avisos.append({
            "vazia": vazia,
            "incerto": incerto,
            "amarelo": vazia or incerto,
            "nao_sequencial": nao_sequencial,
        })

    return avisos


def gerar_planilha_holerite(dados, caminho_saida):
    """
    Escreve o xlsx do holerite e devolve o caminho.

    O documento e uma lista vertical de verbas por pagina; a planilha e uma
    matriz larga, uma linha por pagina e uma coluna por verba distinta. Essa
    transposicao e o trabalho.
    """
    paginas = dados["pages"]
    verbas = colunas_de_verbas(dados)
    cabecalho = ["Pág.", "Mês", "Ano"] + verbas
    avisos = derivar_avisos_holerite(paginas)

    planilha = Workbook()
    aba = planilha.active
    aba.title = "Holerite"

    escrever_cabecalho(aba, cabecalho)

    for numero_linha, (pagina, aviso) in enumerate(zip(paginas, avisos), start=2):
        valores_da_pagina = valores_por_verba(pagina)

        """
        Mes e Ano ficam string, como vieram do contrato: virar numero comeria
        o zero a esquerda de "01" e a planilha mostraria 1.
        """
        valores = [pagina["page"], pagina["month"], pagina["year"]]

        # None deixa a celula em branco de verdade quando a verba nao aparece
        # nesta pagina; "" criaria uma string vazia.
        valores += [valores_da_pagina.get(verba) for verba in verbas]

        escrever_linha(aba, numero_linha, valores, len(cabecalho), aviso)

    aba.freeze_panes = "D2"
    ajustar_larguras(aba, cabecalho)
    planilha.save(caminho_saida)

    logger.debug(
        "planilha de holerite: %s linhas, %s colunas (%s verbas), %s destaques",
        len(paginas),
        len(cabecalho),
        len(verbas),
        sum(1 for a in avisos if a["amarelo"] or a["nao_sequencial"]),
    )

    return caminho_saida
