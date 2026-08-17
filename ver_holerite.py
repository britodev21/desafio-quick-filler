import pdfplumber

with pdfplumber.open("exemplos/payroll-04.pdf") as pdf:
    print(pdf.pages[0].extract_text())
