# Script para checar se os PDFs possuem texto ou não

# Objetivo: descobrir quais PDFs de exemplo têm camada de texto e quais
# são imagem (escaneada ou fotografada). Os que não têm texto embutido
# precisam passar por OCR no pipeline.

# Resultados:
# ayroll-01.pdf        5 pág,  5 com texto  → TEXTO
# payroll-02.pdf        5 pág,  5 com texto  → TEXTO
# payroll-03.pdf        5 pág,  5 com texto  → TEXTO
# payroll-04.pdf        5 pág,  5 com texto  → TEXTO
# time-card-01.pdf      5 pág,  5 com texto  → TEXTO
# time-card-02.pdf      5 pág,  0 com texto  → OCR
# time-card-03.pdf      5 pág,  0 com texto  → OCR
# time-card-04.pdf      5 pág,  0 com texto  → OCR

# Todo o OCR está no cartão de ponto. Os holerites são 100% texto.


from pathlib import Path

import pdfplumber

for pdf_path in sorted(Path("exemplos").glob("*.pdf")):
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)

        com_texto = 0
        for page in pdf.pages:
            texto = page.extract_text() or ""
            if page.extract_text():
                com_texto += 1

        if com_texto == total:
            status = "TEXTO"
        elif com_texto == 0:
            status = "OCR"
        else:
            status = "MISTO"

        print(f"{pdf_path.name:20} {total:2} pág, {com_texto:2} com texto  → {status}")