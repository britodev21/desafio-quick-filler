import json
import logging
import re

import pdfplumber

logger = logging.getLogger(__name__)

# "1 - DOM", "9 - FER", "31 - TER" -> comeco de um dia novo.
PADRAO_DIA = re.compile(r"^(\d{1,2})\s*-\s*([A-Z]{3})\b")

# Linha de continuacao sempre COMECA com um horario ("14:35 18:36 ...").
PADRAO_CONTINUACAO = re.compile(r"^\d{1,2}:\d{2}\b")

# Token que e um horario inteiro ("09:03"). Serve tambem pra Jornada e Qtde,
# por isso quem separa batida de nao-batida e a POSICAO, nao o formato.
PADRAO_TOKEN_HORARIO = re.compile(r"^\d{1,2}:\d{2}$")

# "Mes/Ano : 7 / 2012" no topo de cada pagina. Cada pagina e um mes.
PADRAO_MES_ANO = re.compile(r"Mes/Ano\s*:\s*(\d{1,2})\s*/\s*(\d{4})")

DIA_NOVO = "DIA_NOVO"
CONTINUACAO = "CONTINUACAO"
LIXO = "LIXO"


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

        casamento = PADRAO_DIA.match(linha)

        if casamento:
            dia = int(casamento.group(1))

            """
            Pegadinha do PDF: as vezes ele repete o cabecalho do dia numa linha
            que na verdade e continuacao (ex: "17 - TER" aparece duas vezes
            seguidas). Se o numero e o mesmo do dia anterior, nao e dia novo.
            """
            if dia == ultimo_dia:
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


def extrair_batidas(linha):
    """
    Devolve so as batidas de uma linha da tabela, como lista de "HH:MM".

    Descarta:
      - o prefixo do dia ("17 - TER");
      - a coluna Jornada, que e o primeiro horario depois do dia da semana;
      - a coluna Ocorrencia e a Qtde que vem depois dela.
    """
    tem_cabecalho_do_dia = bool(PADRAO_DIA.match(linha))

    if tem_cabecalho_do_dia:
        resto = PADRAO_DIA.sub("", linha).strip()
    else:
        resto = linha

    horarios = []
    for token in resto.split():
        if PADRAO_TOKEN_HORARIO.match(token):
            horarios.append(token)
        else:
            """
            O primeiro token que nao e horario abre a coluna Ocorrencia
            ("HE-BCO DE HORAS", "HE-REMUNERADA", "HE COMPENSADA"). Dali pra
            frente sobra so ocorrencia + Qtde, e nenhum dos dois e batida.
            """
            break

    if tem_cabecalho_do_dia and horarios:
        # Vale tanto pra DIA_NOVO quanto pra continuacao que repete o
        # cabecalho (dias 17 e 27): o 08:00 dali e Jornada.
        horarios = horarios[1:]

    return horarios


def agrupar_batidas_por_dia(classificadas):
    """
    Junta cada DIA_NOVO com as CONTINUACAO que vem depois dele.
    Devolve lista de dicts: {"dia": int, "semana": str, "batidas": [...]}.
    """
    dias = []

    for tipo, linha in classificadas:
        if tipo == LIXO:
            continue

        if tipo == DIA_NOVO:
            casamento = PADRAO_DIA.match(linha)
            dias.append({
                "dia": int(casamento.group(1)),
                "semana": casamento.group(2),
                "batidas": [],
            })

        if not dias:
            # Continuacao solta antes de qualquer dia: nao tem onde encaixar.
            continue

        dias[-1]["batidas"].extend(extrair_batidas(linha))

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

    A data completa nunca aparece na linha do dia: a linha traz so "1 - DOM" e
    o mes/ano fica no cabecalho da pagina. Por isso date_raw e montado juntando
    os dois, com zero a esquerda no dia.
    """
    days = []

    for registro in resultado["dias"]:
        days.append({
            "date_raw": f"{registro['dia']:02}/{resultado['mes_ano']}",
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

    linhas_tabela = linhas[indice_inicio_tabela + 1:]
    classificadas = classificar_linhas(linhas_tabela)

    contagem = {DIA_NOVO: 0, CONTINUACAO: 0, LIXO: 0}
    for tipo, _linha in classificadas:
        contagem[tipo] += 1

    dias = agrupar_batidas_por_dia(classificadas)

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

    with pdfplumber.open(caminho_pdf) as pdf:
        textos = [pagina.extract_text() or "" for pagina in pdf.pages]

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
