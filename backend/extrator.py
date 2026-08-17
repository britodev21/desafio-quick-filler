import re

import pdfplumber

# "1 - DOM", "9 - FER", "31 - TER" -> comeco de um dia novo.
PADRAO_DIA = re.compile(r"^(\d{1,2})\s*-\s*([A-Z]{3})\b")

# Linha de continuacao sempre COMECA com um horario ("14:35 18:36 ...").
PADRAO_CONTINUACAO = re.compile(r"^\d{1,2}:\d{2}\b")

# Token que e um horario inteiro ("09:03"). Serve tambem pra Jornada e Qtde,
# por isso quem separa batida de nao-batida e a POSICAO, nao o formato.
PADRAO_TOKEN_HORARIO = re.compile(r"^\d{1,2}:\d{2}$")

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


def processar_cartao_ponto(caminho_pdf):
    print("iniciando a leitura do PDF...")

    with pdfplumber.open(caminho_pdf) as pdf:
        pagina = pdf.pages[0]
        texto_bruto = pagina.extract_text() or ""
        linhas = texto_bruto.split("\n")

    indice_inicio_tabela = None

    for i, linha in enumerate(linhas):
        if "Entrada" in linha and "Saida" in linha:
            indice_inicio_tabela = i
            print(f"-> Encontrado o cabecalho na linha {i}: {linha}")
            break

        """
        Varre as linhas procurando as palavras Entrada e Saida, assim que
        encontra, significa que tambem encontra o final do cabecalho
        """

    if indice_inicio_tabela is None:
        print("Nao consegui achar o cabecalho da tabela neste PDF.")
        return []

    linhas_tabela = linhas[indice_inicio_tabela + 1:]
    print(f"Total de linhas brutas na tabela: {len(linhas_tabela)}")

    classificadas = classificar_linhas(linhas_tabela)

    contagem = {DIA_NOVO: 0, CONTINUACAO: 0, LIXO: 0}
    for tipo, _linha in classificadas:
        contagem[tipo] += 1

    print("\n--- Contagem da classificacao ---")
    print(f"Dias novos  : {contagem[DIA_NOVO]}")
    print(f"Continuacoes: {contagem[CONTINUACAO]}")
    print(f"Lixo        : {contagem[LIXO]}")
    print(f"Total       : {len(classificadas)}")

    dias = agrupar_batidas_por_dia(classificadas)

    print("\n--- Batidas por dia ---")
    for registro in dias:
        batidas = " ".join(registro["batidas"]) or "(sem batida)"
        print(
            f"Dia {registro['dia']:2} ({registro['semana']}): "
            f"{len(registro['batidas'])} batidas -> {batidas}"
        )

    impares = [d["dia"] for d in dias if len(d["batidas"]) % 2 != 0]
    print(f"\nDias com numero impar de batidas: {impares or 'nenhum'}")

    return dias


# Teste:
if __name__ == "__main__":
    caminho_teste = "../exemplos/time-card-01.pdf"
    processar_cartao_ponto(caminho_teste)
