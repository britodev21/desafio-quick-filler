import json
import logging
import re

from backend.ocr import extrair_textos

logger = logging.getLogger(__name__)

"""
Comeco de um dia novo. Sao duas formas porque os sistemas imprimem o cartao
de dois jeitos, e as duas aparecem nos documentos reais:

  "1 - DOM"        dia do mes + sigla da semana, com traco
  "01 SAB"         o mesmo, separado por espaco
  "11TER"          o mesmo, sem separador nenhum
  "16/12/2019 SEG" a data completa ja na linha

O separador do formato curto e opcional (\\s*-?\\s*) de proposito: mudar de
"1 - DOM" pra "01 SAB" e so o sistema que imprime, e o OCR ainda pode comer o
espaco e devolver "11TER" grudado. Exigir o traco descartava o dia inteiro.

O "?" entra nos dois lados porque e a marca de caractere que o OCR nao leu:
"?? TER" e um dia real do documento, com o numero ilegivel, e vale mais
listado com a data incerta do que sumindo da planilha.

O fim da sigla e marcado com (?=\\s|$), e nao com \\b: a semana ilegivel sai
"???", e "?" nao e caractere de palavra, entao \\b nao enxerga fronteira
nenhuma depois dela - e a linha "?? ??? Sem Registro", um dia inteiro, caia
fora justamente por estar ilegivel.
"""
PADRAO_DIA_DATA = re.compile(
    r"^([\d?]{2}/[\d?]{2}/[\d?]{4})\s*[^\w\s]{0,2}\s*([A-Z?]{3})(?=\s|$)"
)
PADRAO_DIA_CURTO = re.compile(r"^([\d?]{1,2})\s*-?\s*([A-Z?]{3})(?=\s|$)")

"""
Nome da coluna que traz a jornada contratada, e nao uma batida.

Quando ela existe, o primeiro horario da linha e a jornada ("08:00") e precisa
sair; quando nao existe, esse mesmo primeiro horario e a entrada do dia. Quem
decide e o cabecalho da tabela, nao o formato da linha - por isso o nome vive
aqui e a decisao acontece em processar_pagina.
"""
COLUNA_JORNADA = "Jornada"

# Linha de continuacao sempre COMECA com um horario ("14:35 18:36 ...").
PADRAO_CONTINUACAO = re.compile(r"^\d{1,2}:\d{2}\b")

# Token que e um horario inteiro ("09:03"). Serve tambem pra Jornada e Qtde,
# por isso quem separa batida de nao-batida e a POSICAO, nao o formato.
PADRAO_TOKEN_HORARIO = re.compile(r"^\d{1,2}:\d{2}$")

"""
"Mes/Ano : 7 / 2012" no topo de cada pagina. Cada pagina e um mes.

O \\w no lugar do "e" cobre o "Mes" e o "Mês" sem depender do acento, igual o
PADRAO_PERIODO do holerite faz com "Periodo". Sem isso a competencia se perde
e a data do dia sai "17/??/????" numa pagina que traz o mes escrito.
"""
PADRAO_MES_ANO = re.compile(r"M\ws/Ano\s*:\s*(\d{1,2})\s*/\s*(\d{4})")

"""
Traco solto entre dois horarios ("12:00 - 18:15").

Parte dos modelos liga entrada e saida com traco em vez de espaco. Ele nao e
batida nem abre a coluna de ocorrencia: e so pontuacao, e precisa ser pulado
pra que a saida do dia nao fique pra tras. Sao tres grafias porque o OCR
devolve tanto o hifen quanto os travessoes.
"""
SEPARADORES_DE_HORARIO = ("-", "—", "–")

DIA_NOVO = "DIA_NOVO"
CONTINUACAO = "CONTINUACAO"
LIXO = "LIXO"


def casar_dia(linha):
    """
    Reconhece o cabecalho de dia da linha, em qualquer uma das formas.

    Devolve (data_completa, dia, fim_do_prefixo) ou None quando a linha nao
    abre dia. data_completa vem None no formato curto, em que a linha so traz
    o numero do dia e o mes/ano fica no topo da pagina.

    Tenta a data completa primeiro: "16/12/2019 SEG" tambem comeca com dois
    digitos, e o formato curto morderia so o "16" se viesse antes.

    O dia sai como string, e nao int, pelo mesmo motivo que o normalizar_hhmm
    usa zfill: "??" e um dia legitimo, com o numero ilegivel, e int("??")
    estouraria.
    """
    casamento = PADRAO_DIA_DATA.match(linha)

    if casamento:
        return casamento.group(1), casamento.group(1), casamento.end()

    casamento = PADRAO_DIA_CURTO.match(linha)

    if casamento:
        return None, casamento.group(1), casamento.end()

    return None


def classificar_linhas(linhas):
    """
    Rotula cada linha da tabela em DIA_NOVO, CONTINUACAO ou LIXO.
    Ainda nao extrai horario nenhum, so classifica.

    Devolve uma lista de tuplas (tipo, linha).
    """
    classificadas = []
    ultimo_dia = None

    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue

        casamento = casar_dia(linha)

        if casamento:
            _data, dia, _fim = casamento

            """
            Pegadinha do PDF: as vezes ele repete o cabecalho do dia numa linha
            que na verdade e continuacao (ex: "17 - TER" aparece duas vezes
            seguidas). Se o numero e o mesmo do dia anterior, nao e dia novo.

            Dia ilegivel nunca entra nessa regra: dois "??" seguidos sao dois
            dias diferentes que o OCR nao leu (num dos exemplos, 12 e 13), e
            trata-los como repeticao fundiria os dois numa linha so.
            """
            if dia == ultimo_dia and "?" not in dia:
                classificadas.append((CONTINUACAO, linha))
            else:
                ultimo_dia = dia
                classificadas.append((DIA_NOVO, linha))

        elif PADRAO_CONTINUACAO.match(linha):
            classificadas.append((CONTINUACAO, linha))

        else:
            # Nao abre dia e nao comeca com horario: assinatura, numero de
            # processo, rodape.
            classificadas.append((LIXO, linha))

    return classificadas


def extrair_batidas(linha, tem_jornada):
    """
    Devolve so as batidas de uma linha da tabela, como lista de "HH:MM".

    Descarta:
      - o prefixo do dia ("17 - TER", "16/12/2019 SEG");
      - a coluna Jornada, quando a tabela tem essa coluna;
      - a coluna Ocorrencia e a Qtde que vem depois dela.

    tem_jornada vem do cabecalho da pagina. Nao da pra decidir isso olhando a
    linha: "1 - DOM 08:00 09:03" e "17 SEG 12:00 - 18:15" tem a mesma cara, e
    o primeiro horario e jornada num caso e entrada no outro. Descartar sempre
    comeria a entrada de todo dia das tabelas sem Jornada.
    """
    casamento = casar_dia(linha)

    if casamento:
        _data, _dia, fim = casamento
        resto = linha[fim:].strip()
    else:
        resto = linha

    horarios = []
    for token in resto.split():
        if PADRAO_TOKEN_HORARIO.match(token):
            horarios.append(token)
        elif token in SEPARADORES_DE_HORARIO:
            # Pontuacao entre entrada e saida, nao fim da regiao de batidas.
            continue
        else:
            """
            O primeiro token que nao e horario abre a coluna Ocorrencia
            ("HE-BCO DE HORAS", "HE-REMUNERADA", "HE COMPENSADA"). Dali pra
            frente sobra so ocorrencia + Qtde, e nenhum dos dois e batida.

            O traco solto ja saiu no ramo de cima; "HE-BCO" continua parando
            aqui, porque o traco dele vem grudado na palavra.
            """
            break

    if casamento and tem_jornada and horarios:
        # Vale tanto pra DIA_NOVO quanto pra continuacao que repete o
        # cabecalho (dias 17 e 27): o 08:00 dali e Jornada.
        horarios = horarios[1:]

    return horarios


def agrupar_batidas_por_dia(classificadas, tem_jornada):
    """
    Junta cada DIA_NOVO com as CONTINUACAO que vem depois dele.
    Devolve lista de dicts: {"dia": str, "data": str|None, "batidas": [...]}.
    """
    dias = []

    for tipo, linha in classificadas:
        if tipo == LIXO:
            continue

        if tipo == DIA_NOVO:
            data, dia, _fim = casar_dia(linha)
            dias.append({"dia": dia, "data": data, "batidas": []})

        if not dias:
            # Continuacao solta antes de qualquer dia: nao tem onde encaixar.
            continue

        dias[-1]["batidas"].extend(extrair_batidas(linha, tem_jornada))

    return dias


def normalizar_hhmm(horario):
    """
    Normaliza o horario pra HH:MM com zero a esquerda ("9:03" -> "09:03").

    Usa zfill em vez de int() de proposito: se um dia vier "?:25" de um
    caractere ilegivel, sai "0?:25", que e o formato de incerteza do contrato,
    em vez de estourar.
    """
    hora, _, minuto = horario.partition(":")
    return f"{hora.zfill(2)}:{minuto}"


def montar_punches(batidas):
    """
    Vira a lista de "HH:MM" em punches do contrato, alternando IN e OUT a
    partir da primeira batida do dia.
    """
    punches = []

    for posicao, horario in enumerate(batidas):
        punches.append({
            "kind": "IN" if posicao % 2 == 0 else "OUT",
            "time_raw": horario,
            "time_hhmm": normalizar_hhmm(horario),
        })

    return punches


def montar_json_pagina(resultado):
    """
    Monta o {"page": N, "days": [...]} de uma pagina ja processada.

    Quando a linha traz so "1 - DOM", a data completa nao existe nela: o
    mes/ano fica no cabecalho da pagina e o date_raw e montado juntando os
    dois, com zero a esquerda no dia. Quando a linha ja vem com a data inteira
    ("16/12/2019 SEG"), ela e usada como esta - o cabecalho nao acrescenta
    nada, e remontar so criaria chance de divergir do documento.

    O zfill no lugar de :02 e o mesmo motivo do normalizar_hhmm: dia ilegivel
    chega como "??" e precisa sair "??", nao estourar.
    """
    days = []

    for registro in resultado["dias"]:
        if registro["data"]:
            date_raw = registro["data"]
        else:
            date_raw = f"{registro['dia'].zfill(2)}/{resultado['mes_ano']}"

        days.append({
            "date_raw": date_raw,
            "punches": montar_punches(registro["batidas"]),
        })

    return {"page": resultado["pagina"], "days": days}


def encontrar_inicio_tabela(linhas):
    """
    Devolve o indice do cabecalho da tabela, ou None se a pagina nao tiver.

    Varre as linhas procurando as palavras Entrada e Saida, assim que
    encontra, significa que tambem encontra o final do cabecalho.
    """
    for i, linha in enumerate(linhas):
        if "Entrada" in linha and "Saida" in linha:
            return i

    return None


def extrair_mes_ano(linhas):
    """Le o "Mes/Ano : 7 / 2012" do topo da pagina. So pra rotular a saida."""
    for linha in linhas:
        casamento = PADRAO_MES_ANO.search(linha)
        if casamento:
            return f"{int(casamento.group(1)):02}/{casamento.group(2)}"

    return "??/????"


def processar_pagina(texto_bruto):
    """
    Trata UMA pagina de ponta a ponta, sem depender das outras.

    Cada pagina do PDF e um mes fechado e recomeca a contagem no dia 1, entao
    achar o cabecalho, classificar e agrupar tem que acontecer dentro dela.

    Devolve None quando a pagina nao tem tabela.
    """
    linhas = texto_bruto.split("\n")
    indice_inicio_tabela = encontrar_inicio_tabela(linhas)

    if indice_inicio_tabela is None:
        return None

    # A coluna Jornada existe em parte dos modelos e muda o que e a primeira
    # batida do dia, entao a resposta sai do cabecalho desta pagina.
    tem_jornada = COLUNA_JORNADA in linhas[indice_inicio_tabela]

    linhas_tabela = linhas[indice_inicio_tabela + 1:]
    classificadas = classificar_linhas(linhas_tabela)

    contagem = {DIA_NOVO: 0, CONTINUACAO: 0, LIXO: 0}
    for tipo, _linha in classificadas:
        contagem[tipo] += 1

    dias = agrupar_batidas_por_dia(classificadas, tem_jornada)

    return {
        "mes_ano": extrair_mes_ano(linhas[:indice_inicio_tabela]),
        "linha_cabecalho": indice_inicio_tabela,
        "linhas_brutas": len(linhas_tabela),
        "contagem": contagem,
        "dias": dias,
        "total_batidas": sum(len(d["batidas"]) for d in dias),
    }


def processar_cartao_ponto(caminho_pdf):
    logger.debug("iniciando a leitura do PDF...")

    # Uma string por pagina. Quem decide se ela veio da camada de texto ou do
    # OCR e o modulo ocr; daqui pra baixo as duas origens sao a mesma coisa.
    textos = extrair_textos(caminho_pdf)

    logger.debug("O PDF tem %s paginas.", len(textos))

    paginas = []
    pages = []

    for numero, texto_bruto in enumerate(textos, start=1):
        resultado = processar_pagina(texto_bruto)

        if resultado is None:
            """
            Pagina sem tabela nao pode sumir da saida: o contrato pede uma
            entrada por pagina do PDF, vazia quando nao tem dado.
            """
            logger.debug(
                "Pagina %s: nao achei o cabecalho da tabela.", numero
            )
            pages.append({"page": numero, "days": []})
            continue

        resultado["pagina"] = numero
        paginas.append(resultado)
        pages.append(montar_json_pagina(resultado))

        impares = [
            d["dia"] for d in resultado["dias"] if len(d["batidas"]) % 2 != 0
        ]

        logger.debug(
            "Pagina %s (mes %s): %s dias, %s batidas",
            numero,
            resultado["mes_ano"],
            len(resultado["dias"]),
            resultado["total_batidas"],
        )
        logger.debug(
            "Pagina %s: cabecalho na linha %s, %s linhas de tabela "
            "(%s dia novo / %s continuacao / %s lixo)",
            numero,
            resultado["linha_cabecalho"],
            resultado["linhas_brutas"],
            resultado["contagem"][DIA_NOVO],
            resultado["contagem"][CONTINUACAO],
            resultado["contagem"][LIXO],
        )
        logger.debug(
            "Pagina %s: dias com numero impar de batidas: %s",
            numero,
            impares or "nenhum",
        )

    total_dias = sum(len(p["dias"]) for p in paginas)
    total_batidas = sum(p["total_batidas"] for p in paginas)

    logger.debug(
        "Total do arquivo: %s paginas com tabela, %s dias, %s batidas",
        len(paginas),
        total_dias,
        total_batidas,
    )

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

    caminho_teste = "../exemplos/time-card-01.pdf"
    saida = processar_cartao_ponto(caminho_teste)

    print("\n--- JSON da pagina 1 ---")
    print(json.dumps(saida["pages"][0], indent=2, ensure_ascii=False))
