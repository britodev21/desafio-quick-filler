"""
Fonte de texto dos PDFs, com OCR para as paginas que sao imagem.

Este modulo e a unica porta de entrada de texto do pipeline: os extratores
chamam extrair_textos() e recebem uma string por pagina, sem saber se ela veio
da camada de texto do PDF ou do Tesseract. Isso e de proposito - o extrator
resolve layout, nao origem de texto -, e e o que deixa o mesmo extrator servir
um PDF nativo e um escaneado.

Precisa do binario do tesseract instalado, com o pacote de idioma portugues
(tesseract-ocr-por). O Dockerfile ja instala os dois.
"""

import logging

import pdfplumber
import pypdfium2
import pytesseract
from pytesseract import Output

logger = logging.getLogger(__name__)

"""
Minimo de caracteres pra considerar que a pagina tem texto aproveitavel.

Nao e "tem zero caracteres". PDF escaneado que passou por processo judicial
costuma trazer uma tarja de texto real sobreposta a imagem ("Assinado
eletronicamente por: ... - Juntado em: ..."), entao a pagina responde que tem
texto e o documento continua ilegivel. Medido nos exemplos: a tarja do
payroll-04 da 83 caracteres por pagina e a pagina mais pobre com conteudo de
verdade da 885, entao 200 separa os dois casos com folga dos dois lados.
"""
LIMIAR_TEXTO_UTIL = 200

"""
Confianca minima, de 0 a 100, pra aceitar a palavra como lida.

Abaixo disso o texto vai pra saida marcado com "?" em vez de sair como se
fosse leitura firme. Ver marcar_incerteza() pra como a marca e aplicada.
"""
LIMIAR_CONFIANCA = 60

"""
Escala do render. O pdfium desenha a 72 dpi com escala 1, e o Tesseract foi
treinado esperando algo em torno de 300 dpi: abaixo disso ele erra digito
fino (o 8 vira 3, o 5 vira 6) e acima so gasta tempo e memoria sem ganhar
acerto.
"""
ESCALA_RENDER = 300 / 72

IDIOMA = "por"

"""
--psm 6 trata a pagina como um bloco de texto uniforme.

O padrao (--psm 3) roda segmentacao automatica e tenta adivinhar colunas, e
nestes documentos isso e pior: tanto o cartao de ponto quanto o holerite sao
uma tabela larga, e a segmentacao automatica reordena as colunas, entregando
linhas com os horarios fora da ordem em que aparecem no papel. Os dois
extratores leem a linha da esquerda pra direita, entao a ordem importa mais
que a separacao em blocos.
"""
CONFIG_TESSERACT = "--psm 6"

# Chaves do dict que o image_to_data devolve. Nomeadas aqui pra montar a
# linha; o resto das colunas (coordenadas, tamanho) nao e usado.
COLUNAS_LINHA = ("block_num", "par_num", "line_num")


class OCRIndisponivel(RuntimeError):
    """
    O binario do tesseract nao esta instalado ou nao esta no PATH.

    Erro proprio pra quem chama poder distinguir "documento ilegivel" de
    "faltou instalar o programa" - o primeiro e um dado do documento, o
    segundo e um problema de ambiente e tem conserto conhecido.
    """


def precisa_de_ocr(texto):
    """
    Diz se a pagina precisa passar por OCR.

    Recebe o texto que a camada nativa devolveu; menos que o limiar significa
    que o conteudo esta na imagem, e nao no texto.
    """
    return len((texto or "").strip()) < LIMIAR_TEXTO_UTIL


def marcar_incerteza(palavra, confianca):
    """
    Devolve a palavra com "?" no lugar dos caracteres que nao dao pra afirmar.

    Aqui mora a diferenca de granularidade do problema: o Tesseract da
    confianca por PALAVRA, e o contrato pede "?" por CARACTERE. Nao da pra
    inventar a informacao que falta - quando ele diz "10:35, confianca 42",
    nao existe nada na resposta dizendo qual dos digitos e o duvidoso.

    Das saidas possiveis:

      - nao marcar nada: entrega um palpite com cara de leitura firme, que e
        exatamente o erro que o "?" existe pra evitar;
      - trocar a palavra inteira, separador incluido, por "?????": alem de
        incerto, o dado fica irreconhecivel, e some ate a informacao de que
        ali havia um horario;
      - trocar so os caracteres de conteudo, mantendo a pontuacao: "10:35"
        vira "??:??".

    A terceira e a que diz a verdade sem apagar o que ainda se sabe. O ":" e o
    "/" nao vem de reconhecer um glifo duvidoso, e sim da forma do campo, e
    guardar eles mantem visivel o que se perdeu: "??:??" ainda se le como "um
    horario que nao deu pra ler", e e o mesmo formato que o normalizar_hhmm do
    extrator ja antecipa quando comenta o caso do "0?:25".
    """
    if confianca >= LIMIAR_CONFIANCA:
        return palavra

    return "".join("?" if caractere.isalnum() else caractere
                   for caractere in palavra)


def ler_confianca(valor):
    """
    Le a confianca da coluna conf, que vem como str em algumas versoes.

    O -1 marca as entradas que nao sao palavra (bloco, paragrafo, linha) e o
    filtro de texto vazio ja tira essas; um valor ilegivel vira 0, que trata
    como incerto em vez de deixar passar sem marca.
    """
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def montar_linhas(dados):
    """
    Remonta as linhas de texto a partir da tabela de palavras do image_to_data.

    O image_to_data devolve uma palavra por registro, com os numeros do bloco,
    do paragrafo e da linha a que ela pertence. Agrupar por esses tres e o que
    reconstroi a linha do papel - e linha e a unidade que os dois extratores
    consomem, porque os dois comecam com um split("\\n").

    Devolve (linhas, total de palavras, palavras marcadas como incertas).
    """
    linhas = {}
    total = 0
    incertas = 0

    for indice, palavra in enumerate(dados["text"]):
        palavra = palavra.strip()

        if not palavra:
            continue

        confianca = ler_confianca(dados["conf"][indice])
        total += 1

        if confianca < LIMIAR_CONFIANCA:
            incertas += 1

        chave = tuple(dados[coluna][indice] for coluna in COLUNAS_LINHA)
        linhas.setdefault(chave, []).append(
            marcar_incerteza(palavra, confianca)
        )

    """
    Ordena pela chave (bloco, paragrafo, linha) pra sair na ordem do papel: o
    dict guarda a ordem de insercao, que e a ordem em que o Tesseract emitiu
    as palavras, e essa nao e necessariamente de cima pra baixo.
    """
    texto = [
        " ".join(palavras) for _chave, palavras in sorted(linhas.items())
    ]

    return texto, total, incertas


def texto_da_imagem(imagem):
    """
    Roda o Tesseract numa imagem e devolve (texto, total, incertas).

    Usa image_to_data e nao image_to_string porque so o primeiro traz a
    confianca; o texto sai remontado das mesmas palavras que o
    image_to_string devolveria, mas com o "?" ja aplicado onde cabe.
    """
    try:
        dados = pytesseract.image_to_data(
            imagem,
            lang=IDIOMA,
            config=CONFIG_TESSERACT,
            output_type=Output.DICT,
        )
    except pytesseract.TesseractNotFoundError as erro:
        raise OCRIndisponivel(
            "O tesseract nao foi encontrado. Instale o binario "
            "(tesseract-ocr) junto com o idioma portugues "
            "(tesseract-ocr-por)."
        ) from erro

    linhas, total, incertas = montar_linhas(dados)

    return "\n".join(linhas), total, incertas


def renderizar_paginas(caminho_pdf, numeros):
    """
    Desenha as paginas pedidas (indice base 0) e devolve {numero: imagem}.

    So renderiza o que foi pedido: rasterizar pagina e a parte cara do
    processo, e num PDF misto a maioria das paginas costuma ter texto nativo e
    nao precisar de render nenhum.
    """
    imagens = {}
    documento = pypdfium2.PdfDocument(caminho_pdf)

    try:
        for numero in numeros:
            imagens[numero] = documento[numero].render(
                scale=ESCALA_RENDER
            ).to_pil()
    finally:
        documento.close()

    return imagens


def extrair_textos(caminho_pdf):
    """
    Devolve o texto de cada pagina do PDF, uma string por pagina.

    Le a camada de texto nativa primeiro e so manda pro OCR a pagina que nao
    tem texto aproveitavel. Um PDF pode misturar os dois casos, entao a
    decisao e por pagina, nunca pelo arquivo inteiro.

    E a unica funcao que os extratores usam: pra eles o retorno e sempre a
    mesma lista de strings, tenha vindo de onde tiver vindo.
    """
    with pdfplumber.open(caminho_pdf) as pdf:
        textos = [pagina.extract_text() or "" for pagina in pdf.pages]

    pendentes = [
        numero for numero, texto in enumerate(textos) if precisa_de_ocr(texto)
    ]

    if not pendentes:
        logger.debug(
            "%s paginas, todas com texto nativo: OCR nao foi preciso",
            len(textos),
        )
        return textos

    logger.info(
        "%s de %s paginas sem texto aproveitavel: passando por OCR (%s)",
        len(pendentes),
        len(textos),
        IDIOMA,
    )

    imagens = renderizar_paginas(caminho_pdf, pendentes)

    for numero in pendentes:
        texto, total, incertas = texto_da_imagem(imagens[numero])

        """
        A pagina so troca de fonte se o OCR realmente rendeu mais que o que ja
        havia. Sem essa guarda, uma pagina em branco de verdade trocaria a
        tarja de assinatura - que e texto correto, ainda que inutil - por um
        punhado de ruido reconhecido na moldura da imagem.
        """
        if len(texto.strip()) <= len(textos[numero].strip()):
            logger.debug(
                "pagina %s: OCR nao rendeu mais que o texto nativo, mantendo "
                "o original",
                numero + 1,
            )
            continue

        textos[numero] = texto

        proporcao = (incertas / total * 100) if total else 0
        logger.info(
            "pagina %s: OCR leu %s palavras, %s abaixo de %s de confianca "
            "(%.1f%%), marcadas com ?",
            numero + 1,
            total,
            incertas,
            LIMIAR_CONFIANCA,
            proporcao,
        )

    return textos
