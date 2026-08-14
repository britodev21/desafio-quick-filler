import pdfplumber


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
                print(f"-> Encontrado o cabeçalho na linha {i}: {linha}")
                break

            """
            Varre as linhas procurando as palavras Entrada e Saida, assim que encontra,
            significa que tambem encontra o final do cabeçalho
            """

        if indice_inicio_tabela is not None:
            linhas_tabela = linha[indice_inicio_tabela + 1:]
            print(f"Total de linhas uteis na tabela: {len(linhas_tabela)}.")

    return{}










# Teste:
if __name__ == "__main__":
    caminho_teste = "../exemplos/time-card-01.pdf" 
    processar_cartao_ponto(caminho_teste)
