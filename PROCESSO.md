# Processo

## Stack

- Frontend em React (pela experiencia possuida)
- Backend em Python (melhor para analise de dados)


## Ferramentas usadas

- Claude Code (Integrado na IDE): planejamento, decisões de arquitetura, dúvidas conceituais
- Claude (chat): planejamento, arquitetura e dúvidas
- FastAPI
- uvicorn
- python-multipart
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

### Dia 2 — 12/08

**O que fiz**
- Rotas criadas com  o fastapi
- uvicorn fica ligado atendendo requisições
- Importei o python-multipart permite que o fastapi aceite upload de arquivos
- Usei pip freeze para instalar requeriments.txt. A plataforma de deploy nao tem nada instalado, ela lê o arquivo e vai sabe quais as dependencias instalar
- /healthz criado para confirmar que o sistema está vivo, health check que o render usa
- Utilizei o /docs para testar es requisições e ver como a API me respondia

**Decisões**
- Deploy antes da extração porque: Problema de deploy com apenas as 5 rotas no sistema fica fácil de achar, onde ficaria mais complicado se eu fizesse apenas no dia 7, como está planejado no documento progresso-visual-desafio-quick-filler.html, documento criado apenas para melhor organização pessoal.
- Guardar em memória em vez de banco porque: Criar banco para esse projeto seria apenas gastar tempo. O projeto não é uma corrida contra o tempo mas o banco tambem não é um obrigatoriedade, sendo assim, buscando focar no que é mais importante, decidi deixar tudo em memória
- 

**O que ficou faltando**
- PUT ainda não guarda a correção
- Campo `tipo` aceita qualquer texto
- Rota de planilha aceita qualquer formato
- Nada processa de verdade — falta o BackgroundTasks

**Onde travei**
- Troquei o value de str pra dict e fui testar se a API recusava o formato errado. Deu 200 e achei que a validação estava quebrada. Reiniciei o servidor, conferi o código, não achei nada. Aí percebi que o problema era o meu teste: eu estava mandando um objeto com texto dentro, e achando que estava mandando texto. Quando mandei texto de verdade, deu 422. A validação sempre funcionou

### Dia 3 — 17/08

**O que fiz**
- Classificação das linhas do cartão de ponto em três tipos: início de dia, continuação e lixo
- Extração das batidas, descartando a coluna Jornada e a coluna Qtde
- Agrupamento das batidas por dia

**Decisão: dia repetido (17 e 27)**
- Dois dias repetem o número na linha de continuação em vez de omitir. Juntei as duas linhas num registro só. Isso contraria o "um item por linha" literal do contrato, mas se caso separarmos, o sistema dispara alarme falso de não-sequencial, e acaba representando o mesmo fato de duas formas dependendo de como o sistema imprimiu

**Decisão: como separar batida de não-batida**
- Todos os horários da linha têm o mesmo formato (HH:MM) — Jornada, batidas e Qtde. A distinção é por posição, não por formato.
- Escolhi posição em vez de coordenada porque é mais rapido de escrever e funciona no documento que tenho. Caso contrátrio,exigiria aprender a trabalhar com coordenadas de PDF, que eu não conheço, e com o prazo preferi a solução que eu conseguia validar hoje.
- Limitação conhecida: qualquer mudança na ordem das colunas quebra a leitura, porque a regra é posicional. Se algum dia, um PDF vier sem a coluna de jornada, teremos um descarte da primeira batida no ponto, resultando num dia com numero impar de batidas, por isso exite um detector de batidas.

**Uso de IA**
- Pedi ao agente a classificação das linhas. Ele entregou isso e mais uma decisão que eu não pedi: o tratamento do dia repetido. Percebi ao revisar e decidi manter porque: O dia 17 tem 4 batidas na realidade. Juntar produz isso. Separar produziria dois registros de 2, que não corresponde ao que aconteceu. Nenhum dado se perde, todas as batidas continuam lá, só agrupadas. Os avisos continuam funcionando. Se sobrar batida ímpar depois de juntar, o alerta dispara igual. Separar criaria data duplicada e alarme falso de "data não sequencial".
- Ele também apontou um risco no dia 30 (um horário de batida com o mesmo valor de um horário de outra coluna). Conferi e não procede, a separação é por posição, não por valor, então valores iguais não se confundem.

**Processamento das 5 páginas**
- Cada página do PDF é um mês fechado e recomeça a contagem no dia 1.Por isso tratei cada página de forma independente: encontra o próprio cabeçalho, classifica as próprias linhas, agrupa os próprios dias.
- Se eu classificasse as 5 juntas, a regra do "dia igual ao anterior é continuação" quebraria na virada de mês.

**O que a página 4 revelou**
- Dia 29/10 tem batida ímpar: entrada sem saída. É dado real do PDF, não falha do extrator. Único caso em 153 dias.
- Uma linha com ocorrência e sem nenhum horário de batida caiu em LIXO (por isso a página 4 tem 4 lixos e as outras 3). Inofensivo para o contrato atual, que não pede as ocorrências.

**JSON no formato do contrato**
- `date_raw` é montado (dia da linha + mês/ano do cabeçalho da página), não literal — a data completa nunca aparece numa linha só. Risco: se a validação comparar `date_raw` com o texto cru, não bate. Não há alternativa que preserve o mês.
- `time_raw` e `time_hhmm` saíram idênticos nos 369 punches: este PDF já imprime com zero à esquerda. Normalizei com `zfill` em vez de `int()` pra que um caractere ilegível (`?:25`) vire `0?:25` em vez de estourar.
- 29/10 ficou com um punch só, `IN`. Deixei o dado como está — o contrato não tem campo pra isso, é aviso derivado.
- O agente mudou por conta própria: página sem tabela agora entra como `{"page": N, "days": []}` em vez de sumir. Conferi e mantive, porque perder página em silêncio é erro listado no INSTRUCOES.md.

**Como validei**
- Contei os dias novos: 31 num mês de 31 dias.
- Defini critérios de acerto antes de rodar: dia 1 → 0 batidas, dia 2 → 4, dia 17 → 4. Os três passaram.
- Nenhum dia saiu com número ímpar de batidas, que é o esperado já que batida vem em par entrada/saída.
- Os dias de cada página batem com o calendário real de 2012: jul 31, ago 31, set 30, out 31, nov 30. Total de 153 dias.
- O dia da semana da primeira linha de cada página também confere com 2012 (1/jul domingo, 1/set sábado, 1/out segunda). É uma checagem independente do meu código: se alguma linha tivesse se perdido ou duplicado, o dia da semana não bateria.
- 153 dias e 369 punches, os mesmos números da etapa anterior — nada se perdeu na conversão pro formato do contrato.
- Datas fechando nas bordas de cada página: 01/07 a 31/07, 01/08 a 31/08, etc.


## Cite 3 decisões em que havia mais de uma resposta razoável. Por que escolheu essa?



## O que na sua solução quebra primeiro em produção?



## Onde você não confia no que entregou?