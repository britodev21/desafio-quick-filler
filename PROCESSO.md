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

**Uso de IA — holerite**
- Ferramenta: Claude Code na IDE. Trabalhei pedindo uma etapa por vez (classificar, depois extrair, depois montar o JSON) e revisando cada entrega antes de seguir.
- Ele antecipou uma armadilha que eu não tinha visto: o `Dep. I.R.R.F.` que não é base e vem colado na linha do `Base FGTS`. Conferi no PDF e procede.
- Ele também testou todas as partições possíveis dos 9 valores e mostrou que existe exatamente uma que fecha os dois totais (6 proventos, 3 descontos). Não uso isso como método de separação, porque só funciona quando os totais estão impressos e a partição é única — mas serve como validação.

**Como validei**
- Contei os dias novos: 31 num mês de 31 dias.
- Defini critérios de acerto antes de rodar: dia 1 → 0 batidas, dia 2 → 4, dia 17 → 4. Os três passaram.
- Nenhum dia saiu com número ímpar de batidas, que é o esperado já que batida vem em par entrada/saída.
- Os dias de cada página batem com o calendário real de 2012: jul 31, ago 31, set 30, out 31, nov 30. Total de 153 dias.
- O dia da semana da primeira linha de cada página também confere com 2012 (1/jul domingo, 1/set sábado, 1/out segunda). É uma checagem independente do meu código: se alguma linha tivesse se perdido ou duplicado, o dia da semana não bateria.
- 153 dias e 369 punches, os mesmos números da etapa anterior — nada se perdeu na conversão pro formato do contrato.
- Datas fechando nas bordas de cada página: 01/07 a 31/07, 01/08 a 31/08, etc.

---

## Holerite

**O que descobri nos 4 arquivos**
- `payroll-03` é o caso canônico: uma competência por página, tabela de verbas com código/descrição/unidade/valor, e as bases numa seçãoseparada abaixo do Total.
- `payroll-02` tem duas folhas na mesma competência (MÊS e ACERTO) e outro cabeçalho de tabela.
- `payroll-01` é ficha financeira, com vários meses por página e três colunas lado a lado (rendimentos, descontos, resultados) achatadas numa linha só.
- `payroll-04` é escaneado. O `checar.py` tinha dito que tinha texto, mas era só o carimbo de assinatura eletrônica sobreposto à imagem.
- Comecei pelo `payroll-03` por ser o mais próximo do que o contrato descreve.

**Decisão: o que define uma verba**
- Escolhi "tem valor monetário" em vez de "tem código na frente". O contrato aceita `code` vazio quando o documento não mostra, então ancorar no código descartaria verbas legítimas.

**Decisão: rótulos de base ancorados no nome inteiro**
- A linha `Dep. I.R.R.F. : 0,00 Base FGTS: 1.967,07` traz dois rótulos, e `Dep. I.R.R.F.` é contagem de dependentes, não base. Casar só por `I.R.R.F.` colocaria lixo em `bases` — e errar essa divisão contamina a planilha.

**Decisão: o Total duplicado**
- A linha `Total` traz dois valores (proventos e descontos) e vira duas entradas com o mesmo label. Considerei renomear para `Total Proventos` e `Total Descontos` para não confundir quem revisa, mas isso desviaria do "label exatamente como impresso", e o JSON é o que a avaliação compara. Mantive o JSON fiel e deixei a distinção para a apresentação — mesma lógica do `_raw` versus normalizado.

**Como validei**
- A soma dos 9 valores extraídos dá exatamente `1.967,07 + 859,46`, os dois valores da linha Total impressa. E `1.967,07 − 859,46` = `1.107,61`, o Líqüido impresso. Se algum valor tivesse sido lido errado ou trocado com a coluna Unidade, as duas contas não fechariam. É verificação independente do código, igual à do calendário no cartão de ponto.

---

## Ligação dos extratores na API

**O que fiz**
- POST grava o PDF em `uploads/{id}.pdf` e dispara o processamento via
  `BackgroundTasks`
- Função de processamento escolhe o extrator pelo `tipo`, guarda o resultado
  em `value` e troca o status para `concluido`
- Em caso de falha, status vira `erro` com mensagem genérica
- Validação do `tipo` (400 se não for `cartao-ponto` ou `holerite`)
- Validação de que o arquivo é PDF de verdade, pelos primeiros bytes (`%PDF`),
  não pela extensão

**Decisões**
- A validação acontece antes da gravação, então upload recusado não deixa
  arquivo pela metade em disco. Importa porque são documentos com CPF e salário.
- O nome do arquivo salvo é o uuid que eu gero, nunca o nome que veio do
  cliente. Um arquivo chamado `../../algo.pdf` não escapa do diretório.
- Mensagem de erro genérica para o cliente; o traceback completo vai só para o
  log do servidor. O cliente da API não precisa saber caminho de arquivo, e o
  documento é de outra pessoa.
- Um dicionário único (`EXTRATORES`) valida o tipo e escolhe o extrator, para
  os dois não ficarem fora de sincronia.

**Buraco encontrado nos testes (ainda aberto)**
- Mandei `payroll-03.pdf` com `tipo=cartao-ponto`: um PDF válido, do tipo
  errado. O resultado foi `status: concluido` com zero dias extraídos — o
  extrator não acha o cabeçalho, devolve todas as páginas vazias, e a API diz
  que deu certo.
- É o "perder linhas em silêncio" na versão pior: some o documento inteiro.
- Decisão pendente: tratar "nenhuma página com dado" como erro. Precisa
  responder antes se um documento legitimamente vazio existe.

**PUT guardando a correção**
- O PUT recebia a correção e devolvia sem guardar. Sem isso, a planilha sairia sempre com a transcrição original e a correção da pessoa se perderia, e "a correção chega na planilha?" é critério explícito da avaliação.
- Adicionei a checagem de id inexistente (404, mesmo padrão do GET) e a linha que substitui o `value` da transcrição pelo que chegou.
- O contrato diz "substitui", não "mescla": o front manda a versão completa corrigida.

**Logs sem PII**
- Os extratores imprimiam batidas, datas e valores no log a cada upload. São dados de pessoas reais, e "sem PII nos logs" é requisito explícito.
- Troquei os `print` dentro das funções por `logger.debug`, usando `%s` em vez de f-string: assim o texto só é montado quando o debug está ligado, em vez de ser montado sempre e descartado.
- Os prints dentro do `if __name__ == "__main__"` ficaram, porque só rodam quando executo o extrator direto para testar — não rodam quando a API importa.
- Delegado ao agente pela agilidade.
- Ao trocar por logger, a primeira versão usou `basicConfig(level=DEBUG)`, que liga o debug no logger raiz — o `pdfminer` entrou junto e a execução direta virou 13,9 MB de log do parser interno. Corrigido configurando o nível apenas no logger do próprio módulo.
- Validei que, importado como biblioteca (o caso da API), o extrator não emite nada em stdout nem stderr, com os resultados intactos.

**Código escrito à mão**
- Este foi o primeiro trecho que escrevi sem o agente. Errei duas vezes antes de acertar: primeiro copiei o bloco do POST inteiro (que cria a transcrição do zero, quando aqui ela já existe), depois embrulhei o `correcao.value` dentro de outro dicionário, o que teria criado um `value` dentro do `value`.

**Como validei**
- Ciclo completo com os dois tipos: 202 → `processando` → `concluido` com
  o JSON cheio
- Tipo inválido → 400. Arquivo de texto renomeado para `.pdf` → 400
- PDF corrompido → `status: erro`, mensagem genérica, `value: null`
- Depois das rejeições, `uploads/` continuava vazio

**Planilhas em xlsx**
- Cartão de ponto: uma linha por dia, coluna Data mais os pares Entrada/Saída, com tantos pares quantos o dia com mais batidas exigir. Saiu 154 × 5.
- Holerite: a transposição. No documento as verbas são lista vertical por página; na planilha viram matriz larga, uma coluna por verba distinta na ordem de primeira aparição global. Saiu 6 × 14 — 3 fixas mais 11 verbas.
- Só `fields` viram coluna. As `bases` ficam fora da planilha, conforme o contrato e é justamente isso que eles chamam de "contaminar a planilha" se uma base entrar em `fields` por engano.
- Os quatro avisos são derivados na hora de gerar, nunca campos do JSON.

**Decisão: data ou competência ilegível**
- Uma data com `?` não vira alerta vermelho, e a próxima data legível é comparada com a última legível, não com a ilegível.
- O README escreve essa regra para o holerite; estendi por analogia para o cartão de ponto, onde o texto não detalha.
- Efeito: `10/07 → 1?/07 → 12/07` marca o `12/07` como não sequencial, porque a comparação vê salto de 2 dias. Se o `1?` era 11, a linha foi marcada à toa. Escolhi a leitura conservadora: marcar a mais é melhor que deixar passar.

**Como validei**
- O `time-card-01` tem datas perfeitamente sequenciais, então só uma das quatro regras disparava com dado real. Testei as outras três com dados sintéticos e li as cores de volta do arquivo salvo, em vez de conferir só o código.
- A regra dezembro → janeiro não precisou de teste sintético: as páginas 3 e 4 do `payroll-03` são 12/2019 → 01/2020 e passaram sem marcação.
- Depois da refatoração que unificou as peças das duas planilhas, rodei a regressão do cartão de ponto: continua 154 × 5 com a mesma única linha amarela.

**Detalhes**
- Mês e Ano ficam como texto, não número: converter comeria o zero à esquerda de `01`. O Excel avisa "número armazenado como texto" nessas colunas.
- Célula de verba ausente é `None`, não string vazia.
- Verba repetida na mesma página mantém o primeiro valor e emite aviso no log, a matriz tem uma célula só, então em silêncio um valor sumiria.




## Cite 3 decisões em que havia mais de uma resposta razoável. Por que escolheu essa?



## O que na sua solução quebra primeiro em produção?



## Onde você não confia no que entregou?