# Solução

## Como rodar

preencher no dia 8. docker compose up e execução local

## Stack

- Backend: Python + FastAPI
- Extração de PDF: pdfplumber
- OCR: (preencher)
- Planilha: openpyxl
- Frontend: React + Vite
- Deploy: Render

Escolhi Python no backend porque o gargalo do desafio é extração de documento,
não serving HTTP.

## Armazenamento e retenção

As transcrições ficam em memória, num dicionário do processo. Não uso banco.

Retenção: os dados existem enquanto o processo estiver de pé e somem quando
ele reinicia. Não há persistência em disco nem cópia.

## Decisões de extração — cartão de ponto


## O que ficou de fora
(preencher no fim. entra cortar por prazo)

## Testes
preencher

## O que eu mudaria no formato JSON
(