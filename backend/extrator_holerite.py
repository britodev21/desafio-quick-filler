import logging
import re
from itertools import pairwise

from backend.ocr import extrair_textos

logger = logging.getLogger(__name__)

CABECALHO = "CABECALHO"
VERBA = "VERBA"
BASE = "BASE"
LIXO = "LIXO"

"""
Competencia da folha, nas duas grafias que os documentos usam: "Periodo :
10/2019" e "Mes/Ano: 08/2018". Os dois trazem mes e ano na mesma ordem, entao
mudam o rotulo e nao o conteudo. O \\w cobre a letra acentuada sem depender do
encoding.
"""
PADRAO_PERIODO = re.compile(r"Per\wodo\s*:\s*(\d{1,2})/(\d{4})")
PADRAO_MES_ANO = re.compile(r"M\ws/Ano\s*:\s*(\d{1,2})/(\d{4})")
PADROES_COMPETENCIA = (PADRAO_PERIODO, PADRAO_MES_ANO)

"""
Valor monetario brasileiro: "1.678,61", "76,30", "0,00", "-433,20".

O sinal e opcional porque nem todo modelo separa provento de desconto em duas
colunas: parte deles usa uma coluna Valor so, e marca o desconto com o menos
na frente. Sem o "-?", o token "-433,20" nao e reconhecido como valor, a verba
inteira vira label e o desconto some da transcricao.
"""
PADRAO_VALOR = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}")

"""
Rotulo da folha dentro da pagina: "Folha de Pagamento: MES", "... : ACERTO".

Uma pagina pode trazer mais de uma folha da mesma competencia (a do mes e a de
acerto), cada uma com sua tabela e seus totais. Exige os dois-pontos pra nao
casar com o titulo "Declaracao Remuneracao - Folha de Pagamento", que e outra
coisa e aparece na mesma pagina.
"""
PADRAO_FOLHA = re.compile(r"Folha de Pagamento\s*:\s*(\S+)")

"""
Codigo da verba no comeco da linha: "0105", "4039", "/314", "/B02", "010".

Aceita tres ou quatro caracteres porque o tamanho do codigo e escolha de cada
sistema - um usa "0105" e outro "010" pra mesma coisa. Se nao casar, a verba
fica com code "" e a label comeca do inicio da linha, que e o que o contrato
pede pra documento sem codigo.
"""
PADRAO_CODIGO = re.compile(r"^([0-9/][0-9A-Za-z]{2,3})\b")

"""
Palavras que identificam o cabecalho da tabela de verbas, um conjunto por
modelo de documento. Basta um conjunto inteiro aparecer na linha.

  "Cod. Descricao Unidade Proventos Descontos"
  "Verba Nome Base / Saldo / Beneficio Valor"

Todas ASCII de proposito, porque "Descricao" e "Beneficio" vem acentuados e
nao da pra confiar no acento.
"""
CABECALHOS_DE_TABELA = (
    ("Cod.", "Proventos", "Descontos"),
    ("Verba", "Nome", "Valor"),
)

"""
O que fecha a tabela e abre a regiao de totais.

Um modelo termina com a linha "Total ..."; o outro nao tem Total nenhum e
emenda direto nos totais da folha, que sempre trazem "Proventos Retidos".
"""
MARCADOR_TOTAL = "Total"
MARCADOR_TOTAIS_DA_FOLHA = "Proventos Retidos"

"""
Rotulos da secao de bases e totais. Sao ancorados no nome inteiro: "Base
I.R.R.F." e base, mas "Dep. I.R.R.F." (numero de dependentes) nao e, e as duas
aparecem na mesma regiao.
"""
ROTULOS_BASE = (
    re.compile(r"^Total\b"),
    re.compile(r"L\wq\wido"),
    re.compile(r"Base I\.N\.S\.S\."),
    re.compile(r"Base I\.R\.R\.F\."),
    re.compile(r"F\.G\.T\.S\."),
    re.compile(r"Base FGTS"),
    # Totais do modelo que fecha a folha sem linha "Total": todos vem
    # rotulados na propria linha, no formato "rotulo: valor".
    re.compile(r"^Proventos\b"),
    re.compile(r"^Provis\wo FGTS"),
    re.compile(r"^Margem\b"),
    re.compile(r"^Consigna"),
    re.compile(r"^Adiantamento\b"),
    re.compile(r"^Remunera\w\wo Fun"),
)


def extrair_periodo(linhas):
    """
    Le a competencia e devolve (year, month) como string, month com zero a
    esquerda. Devolve ("", "") se a folha nao trouxer competencia nenhuma.
    """
    for linha in linhas:
        for padrao in PADROES_COMPETENCIA:
            casamento = padrao.search(linha)
            if casamento:
                return casamento.group(2), f"{int(casamento.group(1)):02}"

    return "", ""


def eh_inicio_tabela(linha):
    """Diz se a linha e o cabecalho da tabela, em qualquer um dos modelos."""
    return any(
        all(marcador in linha for marcador in conjunto)
        for conjunto in CABECALHOS_DE_TABELA
    )


def eh_fim_da_tabela(linha):
    """
    Diz se a linha fecha a tabela de verbas.

    Ela propria ja e a primeira linha de totais nos dois modelos, entao quem
    chama classifica como BASE em vez de descartar.
    """
    return (
        linha.startswith(MARCADOR_TOTAL)
        or MARCADOR_TOTAIS_DA_FOLHA in linha
    )


def eh_rotulo_de_base(texto):
    """Serve pra linha inteira (na classificacao) e pra label so (na extracao)."""
    return any(rotulo.search(texto) for rotulo in ROTULOS_BASE)


def classificar_linhas(linhas):
    """
    Rotula cada linha da pagina em CABECALHO, VERBA, BASE ou LIXO.
    Ainda nao extrai valor nenhum, so classifica.

    Percorre a pagina em tres regioes, na ordem em que aparecem:
      1. antes da tabela  -> CABECALHO
      2. dentro da tabela -> VERBA
      3. depois do Total  -> BASE ou LIXO

    Devolve uma lista de tuplas (tipo, linha).
    """
    classificadas = []
    dentro_da_tabela = False
    tabela_terminou = False

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue

        if tabela_terminou:
            """
            Depois do Total vem as bases, e depois delas o rodape (assinatura).
            So e BASE quem tem rotulo de base; o resto e lixo.
            """
            tipo = BASE if eh_rotulo_de_base(linha) else LIXO

        elif dentro_da_tabela:
            if eh_fim_da_tabela(linha):
                # A linha que fecha a tabela ja e a primeira linha de base.
                tabela_terminou = True
                dentro_da_tabela = False
                tipo = BASE
            elif PADRAO_VALOR.search(linha):
                """
                Dentro da tabela, o que define verba e ter valor. Prefiro isso
                a exigir o codigo na frente porque o contrato aceita verba sem
                codigo, e ai a linha continua sendo verba.
                """
                tipo = VERBA
            else:
                tipo = LIXO

        else:
            tipo = CABECALHO
            if eh_inicio_tabela(linha):
                # A propria linha do cabecalho da tabela ainda e CABECALHO;
                # a tabela comeca na linha seguinte.
                dentro_da_tabela = True

        classificadas.append((tipo, linha))

    return classificadas


def separar_valores_do_fim(texto):
    """
    Corta os valores monetarios grudados no fim da linha.

    Devolve (texto_sem_os_valores, [valores]). Usa fullmatch em cada token, e
    nao busca solta, pra nao confundir o "100%" de "Horas Extras 100%" com
    valor: sem virgula decimal, ele nao casa.
    """
    tokens = texto.split()
    valores = []

    while tokens and PADRAO_VALOR.fullmatch(tokens[-1]):
        valores.insert(0, tokens.pop())

    return " ".join(tokens), valores


def extrair_verba(linha):
    """
    Quebra uma linha VERBA em code, label, reference e value.

    A tabela e "Cod. Descricao Unidade Proventos Descontos", e cada verba usa
    ou Proventos ou Descontos, nunca os dois. Entao o que sobra no fim da linha
    e: dois valores (Unidade + o valor) ou um so (apenas o valor).
    """
    inicio, valores = separar_valores_do_fim(linha)

    casamento = PADRAO_CODIGO.match(inicio)
    if casamento:
        code = casamento.group(1)
        label = inicio[casamento.end():].strip()
    else:
        code = ""
        label = inicio.strip()

    if len(valores) >= 2:
        reference = valores[-2]
        value = valores[-1]
    elif valores:
        reference = ""
        value = valores[0]
    else:
        reference = ""
        value = ""

    return {
        "code": code,
        "label": label,
        "reference": reference,
        "value": value,
    }


def extrair_bases_da_linha(linha):
    """
    Quebra uma linha BASE em uma ou mais duplas (label, value).

    Uma linha da regiao de bases pode carregar dois rotulos:

        Base I.N.S.S. : 1.967,07 F.G.T.S. do Mes : 157,37

    O ":" e o que separa. Com N dois-pontos, cada pedaco do meio comeca com o
    valor do rotulo anterior e termina com o rotulo seguinte.

    "Total" e "Liquido" vem sem ":", ai o rotulo e o texto e os valores estao
    no fim da linha.
    """
    if ":" not in linha:
        label, valores = separar_valores_do_fim(linha)

        if not valores:
            return [(label, "")]

        # Uma entrada por valor impresso. O "Total" traz dois (a soma dos
        # proventos e a dos descontos) e nenhum dos dois pode se perder.
        return [(label, valor) for valor in valores]

    pares = []
    partes = linha.split(":")
    label = partes[0].strip()

    for parte in partes[1:]:
        parte = parte.strip()
        casamento = PADRAO_VALOR.match(parte)

        if casamento:
            valor = casamento.group(0)
            proximo_label = parte[casamento.end():].strip()
        else:
            # Rotulo impresso sem valor, tipo "Base I.R.R.F. 13o.:".
            valor = ""
            proximo_label = parte

        pares.append((label, valor))
        label = proximo_label

    if label:
        pares.append((label, ""))

    return pares


def separar_folhas(linhas):
    """
    Divide a pagina nas folhas que ela contem. Devolve [(rotulo, linhas)].

    Uma pagina pode trazer a folha do mes e a de acerto, uma embaixo da outra,
    com a mesma competencia e cada uma com sua tabela e seus totais. Tratar as
    duas como uma so misturaria verbas de folhas diferentes na mesma linha da
    planilha - e, como varias verbas se repetem entre elas, a segunda folha
    seria descartada na transposicao.

    Documento que nao rotula folha nenhuma volta como uma folha unica, sem
    rotulo, que e exatamente o comportamento de antes.
    """
    inicios = [
        numero for numero, linha in enumerate(linhas)
        if PADRAO_FOLHA.search(linha)
    ]

    if not inicios:
        return [("", linhas)]

    folhas = []

    for posicao, inicio in enumerate(inicios):
        # Cada folha vai do proprio rotulo ate o rotulo da seguinte; a ultima
        # leva o rodape junto, que vira LIXO na classificacao.
        fim = inicios[posicao + 1] if posicao + 1 < len(inicios) else len(linhas)
        rotulo = PADRAO_FOLHA.search(linhas[inicio]).group(1)
        folhas.append((rotulo, linhas[inicio:fim]))

    return folhas


def montar_json_pagina(classificadas, numero_pagina, year, month, folha=""):
    """
    Monta o {"page", "folha", "year", "month", "fields", "bases"} do contrato.

    Nas bases, so entra quem tem rotulo de base de verdade: a linha do
    "Dep. I.R.R.F." (numero de dependentes) vem colada na do "Base FGTS" e
    precisa ser descartada rotulo por rotulo, nao linha por linha.
    """
    fields = []
    bases = []

    for tipo, linha in classificadas:
        if tipo == VERBA:
            fields.append(extrair_verba(linha))

        elif tipo == BASE:
            for label, value in extrair_bases_da_linha(linha):
                if eh_rotulo_de_base(label):
                    bases.append({"label": label, "value": value})

    return {
        "page": numero_pagina,
        # "" quando o documento nao separa folhas: uma folha por pagina.
        "folha": folha,
        "year": year,
        "month": month,
        "fields": fields,
        "bases": bases,
    }


def processar_pagina(texto_bruto, numero_pagina):
    """
    Trata UMA pagina de ponta a ponta, sem depender das outras.

    Devolve uma LISTA, com uma entrada por folha da pagina: a unidade do
    documento e a folha, e nao a pagina - cada folha tem competencia, tabela e
    totais proprios. Numa pagina com uma folha so, que e o caso comum, a lista
    vem com um item.

    Pagina sem tabela volta com fields e bases vazios em vez de sumir da
    saida.
    """
    linhas = texto_bruto.split("\n")
    paginas = []

    for rotulo, linhas_da_folha in separar_folhas(linhas):
        year, month = extrair_periodo(linhas_da_folha)
        classificadas = classificar_linhas(linhas_da_folha)
        paginas.append(
            montar_json_pagina(
                classificadas, numero_pagina, year, month, rotulo
            )
        )

    return paginas


def competencia_da_pagina(pagina):
    """Devolve "MM/AAAA", ou "??" quando a pagina nao trouxe periodo."""
    if not pagina["year"] or not pagina["month"]:
        return "??"

    return f"{pagina['month']}/{pagina['year']}"


def conferir_competencias_consecutivas(pages):
    """
    Diz se as competencias andam de mes em mes, sem pular nem repetir.

    Compara em meses absolutos (ano * 12 + mes) porque a sequencia atravessa
    a virada de ano: 12/2019 -> 01/2020 e consecutivo, e comparar so o numero
    do mes acharia que voltou pra tras.

    Repetir a competencia nao e buraco: duas folhas da mesma competencia (a do
    mes e a de acerto) sao duas entradas com o mesmo mes de proposito, e so
    quem pula ou volta no tempo e problema.
    """
    indices = [
        int(p["year"]) * 12 + int(p["month"])
        for p in pages
        if p["year"] and p["month"]
    ]

    if len(indices) < 2:
        return True, []

    buracos = [(a, b) for a, b in pairwise(indices) if b - a not in (0, 1)]

    return not buracos, buracos


def processar_holerite(caminho_pdf):
    logger.debug("iniciando a leitura de %s...", caminho_pdf)

    # Uma string por pagina. Quem decide se ela veio da camada de texto ou do
    # OCR e o modulo ocr; daqui pra baixo as duas origens sao a mesma coisa.
    textos = extrair_textos(caminho_pdf)

    logger.debug("O PDF tem %s paginas.", len(textos))

    pages = []

    for numero, texto_bruto in enumerate(textos, start=1):
        # Uma pagina pode render mais de uma folha, e cada folha e uma entrada
        # da saida.
        folhas = processar_pagina(texto_bruto, numero)
        pages.extend(folhas)

        for pagina in folhas:
            logger.debug(
                "Pagina %s%s: competencia %s, %s fields, %s bases",
                numero,
                f" folha {pagina['folha']}" if pagina["folha"] else "",
                competencia_da_pagina(pagina),
                len(pagina["fields"]),
                len(pagina["bases"]),
            )

            if not pagina["fields"]:
                logger.debug(
                    "Pagina %s: sem tabela de verbas, entra na saida vazia",
                    numero,
                )

    competencias = [competencia_da_pagina(p) for p in pages]
    consecutivas, buracos = conferir_competencias_consecutivas(pages)

    logger.debug("Competencias: %s", " -> ".join(competencias))

    if consecutivas:
        logger.debug("Competencias consecutivas: sim")
    else:
        logger.debug("Competencias nao consecutivas, buracos: %s", buracos)

    return {"pages": pages}


# Teste:
if __name__ == "__main__":
    """
    So na execucao direta: liga o DEBUG deste modulo pra continuar vendo o
    passo a passo. Nao da pra usar basicConfig(level=DEBUG) porque isso liga o
    DEBUG do logger raiz, e ai o pdfminer despeja megabytes de log do parser.
    Rodando pela API, quem manda no nivel de log e o servidor.
    """
    logging.basicConfig(format="%(message)s")
    logger.setLevel(logging.DEBUG)

    caminho_teste = "../exemplos/payroll-03.pdf"
    saida = processar_holerite(caminho_teste)
