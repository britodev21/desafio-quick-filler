# Processo

## Stack

- Frontend em React (pela experiencia possuida)
- Backend em Python (melhor para analise de dados)


## Ferramentas usadas

- Claude Code (Integrado na IDE): planejamento, decisões de arquitetura, dúvidas conceituais
- Claude (chat): planejamento, arquitetura e dúvidas
- FastAPI
- pdfplumber


### Dia 1 — 11/08

**O que fiz?** 

- Defini a estrutura do repositório (fork, pastas, .gitignore)
- Configurei o ambiente Python (venv)
- Pensei em por onde começar, li o INSTRUCOES.md e os pesos da avaliação, e usei isso pra montar a ordem do trabalho
- Escrevi o checar.py para verificar qual pdf tem textp e qual tem imagem
- Escrevi o ver.py pra saber como o texto sai na prática

    Os dois scripts são investigação, não produto. O checar.py me disse quais arquivos dava pra ler, e o ver.py me mostrou o que tinha dentro de um deles. Foi assim que descobri as exceções do documento antes de escrever qualquer extrator.

**O que Descobri?**

- Rodando o checar.py: Os 4 holerites tem camada de texto. Dos 4 cartões de ponto, somente o time-card-01 possui camada de texto, os outros 3 são imagens. Sendo assim, todo o OCR está concentrado no cartão de ponto
- Rodando o ver.py e identifiquei:
1. A data só tem o dia (`1 - DOM`). O mês e o ano estão no cabeçalho,
   em `Mes/Ano : 7 / 2012`.
2. Um dia pode ocupar mais de uma linha. A linha seguinte vem sem o número
   do dia e é continuação da anterior.
3. Existe um horário fixo (`08:00`) em toda linha que é a coluna Jornada,
   não uma batida. Aparece até em dia sem batida nenhuma.
4. Os dias 17 e 27 repetem o número em duas linhas, ao contrário do dia 2
   que omite.
5. Tem cabeçalho de sistema, número de página e assinatura eletrônica misturados no texto.
Ainda não decidi o que fazer com 1, 2 e 4 — decidir no dia 3.

**Decisão**

- Extrator primeiro com texto limpo, OCR depois. (revisar essa explicação no dia 4)
- A detecção "tem texto ou não" fica no caminho comum, antes de separar por tipo de documento (vale pro holerite também).

