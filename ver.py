import pdfplumber

with pdfplumber.open("exemplos/time-card-01.pdf") as pdf:
    primeira_pagina = pdf.pages[0]
    texto = primeira_pagina.extract_text()
    print(texto)