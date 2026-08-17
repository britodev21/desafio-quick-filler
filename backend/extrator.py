import re

import pdfplumber

# "1 - DOM", "9 - FER", "31 - TER" -> comeco de um dia novo.
PADRAO_DIA = re.compile(r"^(\d{1,2})\s*-\s*([A-Z]{3})\b")

# Linha de continuacao sempre COMECA com um horario ("14:35 18:36 ...").
PADRAO_CONTINUACAO = re.compile(r"^\d{1,2}:\d{2}\b")

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

    print("\n--- Classificacao linha por linha ---")
    for tipo, linha in classificadas:
        print(f"[{tipo:11}] {linha}")

    print("\n--- Contagem ---")
    print(f"Dias novos  : {contagem[DIA_NOVO]}")
    print(f"Continuacoes: {contagem[CONTINUACAO]}")
    print(f"Lixo        : {contagem[LIXO]}")
    print(f"Total       : {len(classificadas)}")

    return classificadas


# Teste:
if __name__ == "__main__":
    caminho_teste = "../exemplos/time-card-01.pdf"
    processar_cartao_ponto(caminho_teste)
