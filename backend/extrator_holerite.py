import json
import re

import pdfplumber

CABECALHO = "CABECALHO"
VERBA = "VERBA"
BASE = "BASE"
LIXO = "LIXO"

# "Periodo : 10/2019". O \w cobre o "i" acentuado sem depender do encoding.
PADRAO_PERIODO = re.compile(r"Per\wodo\s*:\s*(\d{1,2})/(\d{4})")

# Valor monetario brasileiro: "1.678,61", "76,30", "0,00".
PADRAO_VALOR = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")

"""
Codigo da verba no comeco da linha: "0105", "4039", mas tambem "/314" e "/B02".
Se nao casar, a verba fica com code "" e a label comeca do inicio da linha,
que e o que o contrato pede pra documento sem codigo.
"""
PADRAO_CODIGO = re.compile(r"^([0-9/][0-9A-Za-z]{3})\b")

# Palavras do cabecalho da tabela de verbas. Todas ASCII de proposito, porque
# "Descricao" vem acentuado e nao da pra confiar no acento.
MARCADORES_INICIO_TABELA = ("Cod.", "Proventos", "Descontos")

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
)


def extrair_periodo(linhas):
    """
    Le o "Periodo : 10/2019" e devolve (year, month) como string, month com
    zero a esquerda. Devolve ("", "") se a pagina nao trouxer o periodo.
    """
    for linha in linhas:
        casamento = PADRAO_PERIODO.search(linha)
        if casamento:
            return casamento.group(2), f"{int(casamento.group(1)):02}"

    return "", ""


def eh_inicio_tabela(linha):
    """A linha "Cod. Descricao Unidade Proventos Descontos" abre a tabela."""
    return all(marcador in linha for marcador in MARCADORES_INICIO_TABELA)


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
            if linha.startswith("Total"):
                # O Total fecha a tabela e ja e a primeira linha de base.
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


def montar_json_pagina(classificadas, numero_pagina, year, month):
    """
    Monta o {"page", "year", "month", "fields", "bases"} do contrato.

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
        "year": year,
        "month": month,
        "fields": fields,
        "bases": bases,
    }


def processar_holerite(caminho_pdf, numero_pagina=1):
    print(f"iniciando a leitura de {caminho_pdf}...")

    with pdfplumber.open(caminho_pdf) as pdf:
        print(f"-> O PDF tem {len(pdf.pages)} paginas.")
        texto_bruto = pdf.pages[numero_pagina - 1].extract_text() or ""

    linhas = texto_bruto.split("\n")
    year, month = extrair_periodo(linhas)

    print(f"-> Pagina {numero_pagina}, periodo: year={year!r} month={month!r}")

    classificadas = classificar_linhas(linhas)

    contagem = {CABECALHO: 0, VERBA: 0, BASE: 0, LIXO: 0}
    for tipo, _linha in classificadas:
        contagem[tipo] += 1

    print("\n--- Contagem da classificacao ---")
    print(f"Cabecalho: {contagem[CABECALHO]}")
    print(f"Verbas   : {contagem[VERBA]}")
    print(f"Bases    : {contagem[BASE]}")
    print(f"Lixo     : {contagem[LIXO]}")
    print(f"Total    : {len(classificadas)}")

    pagina = montar_json_pagina(classificadas, numero_pagina, year, month)

    print(f"\n-> fields: {len(pagina['fields'])}, bases: {len(pagina['bases'])}")

    return pagina


# Teste:
if __name__ == "__main__":
    caminho_teste = "../exemplos/payroll-03.pdf"
    saida = processar_holerite(caminho_teste)

    print("\n--- JSON da pagina 1 ---")
    print(json.dumps(saida, indent=2, ensure_ascii=False))
