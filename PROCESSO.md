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

- Rotas criadas com o fastapi
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
- Holerite: a transposição. No documento as verbas são lista vertical por        página; na planilha viram matriz larga, uma coluna por verba distinta na ordem de primeira aparição global. Saiu 6 × 14 — 3 fixas mais 11 verbas.
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

**CSV e JSON**
- JSON devolve o próprio `value`, sem transformação.
- CSV usa os mesmos dados do xlsx: mesmas colunas, mesma ordem, mesmas linhas.
  Sem cor, porque CSV não tem formatação.

**Decisão: separador do CSV**
- Usei `;` em vez de `,`. É o que o Excel em português-BR entende como
  separador de lista. Com vírgula o arquivo abre todo na coluna A, e o BOM
  resolve o encoding mas não o separador.
- Como o produto é para RH brasileiro, o CSV precisa abrir corretamente ao ser
  clicado. O custo é fugir do padrão internacional. Um parâmetro opcional na
  rota resolveria os dois casos, mas não está no contrato.
- Efeito colateral bom: os valores monetários deixaram de sair entre aspas,
  porque a vírgula decimal não é mais o delimitador.

**Refatoração**
- O agente extraiu a construção da tabela numa estrutura intermediária que o
  xlsx e o CSV consomem. A igualdade entre os dois formatos passou a ser
  estrutural: não dá pra mudar uma coluna num e esquecer o outro.
- As seis funções geradoras têm a mesma assinatura e ficam num dicionário
  indexado por tipo e formato, então a rota de download resolve com uma busca
  em vez de `if` por formato.

**Como validei**
- Comparação célula a célula entre xlsx e CSV nos dois documentos: 153 × 5 e
  5 × 14, cabeçalhos idênticos, zero linhas divergentes.
- JSON recarregado idêntico ao `value` de origem.
- BOM presente e acentuação sobrevivendo à ida e volta.

**Risco apontado e resolvido**
- Gravar a planilha com nome fixo dava conflito: dois pedidos simultâneos, ou
  o arquivo aberto no Excel, resultavam em erro de permissão. Aconteceu comigo
  durante o teste da geração de CSV.
- Resolvido na rota de download, que grava usando o id da transcrição no nome.
- Continua aberto o caso de dois downloads simultâneos do mesmo id e formato,
  que ainda escreveriam o mesmo arquivo. Gravar num temporário e renomear
  resolveria.

**Rota de download**
- Gera a planilha a partir do `value` atual da transcrição, que é o corrigido
  se houve PUT. É isso que faz a correção chegar na planilha.
- Escolhe o gerador num dicionário indexado por tipo e formato, sem `if` por
  formato.
- Grava com o id no nome do arquivo, para dois pedidos simultâneos não
  escreverem o mesmo arquivo.

**Decisão: 409 para transcrição ainda não pronta**
- Usei 409 e não 404 nem 400. A transcrição existe, o problema é o estado.
  404 diria que o recurso não existe, e 400 culparia o pedido, que está correto.
- O mesmo 409 cobre `status: erro`, com a mensagem dizendo qual dos dois casos é.
- O README não fixa código para essa situação, então é decisão minha.

**Decisão: ordem das validações**
- Valido na ordem id, status, formato. Efeito colateral: pedir um formato
  inválido de uma transcrição ainda processando devolve 409, não 400, mesmo o
  formato sendo permanentemente inválido.
- Se o erro permanente devesse ganhar, é mover um bloco.

**Decisão: separar `planilhas/` de `saidas/`**
- `saidas/` guarda as planilhas geradas dos exemplos, que são entregável e vão
  para o repositório.
- `planilhas/` guarda o que a aplicação gera em execução, a partir de documento
  de terceiro, e fica no `.gitignore`.

**Retenção**
- Os PDFs ficavam em `uploads/` indefinidamente. Como `transcricoes` é memória
  e some no restart, depois de reiniciar sobravam documentos com CPF e salário
  em disco sem nenhum id que os


**Limpeza na subida**
- Ao iniciar, a aplicação apaga tudo de `uploads/` e `planilhas/`. Como
  `transcricoes` nasce vazio a cada início, qualquer arquivo que estivesse lá
  é órfão sem id que o referencie.
- Isso resolve a retenção infinita sem quebrar a tela de revisão: o PDF
  sobrevive durante a sessão e some no restart. No Render free, que dorme por
  inatividade, isso vira limpeza automática a cada ciclo.
- Usei `lifespan` em vez de `@app.on_event("startup")`, que está depreciado
  nesta versão do FastAPI.

**Bug encontrado no teste**
- A primeira versão limpava certo mas não logava nada. O uvicorn configura
  apenas os loggers dele e deixa o raiz em WARNING, então o `logger.info` era
  descartado em silêncio. O requisito de logar estava implementado e
  praticamente inexistente.
- Corrigido com `basicConfig(level=INFO)` no `main.py`. Nível INFO e não DEBUG
  de propósito: DEBUG no raiz ligaria junto o do `pdfminer`, o mesmo despejo de
  megabytes que apareceu quando trocamos os prints dos extratores.

**Detalhes de robustez**
- Arquivo travado por outro processo é contado à parte e vira aviso, sem
  derrubar a subida. Um xlsx aberto no Excel não deve impedir o servidor de
  iniciar.
- Subpastas não são tocadas.

---

## Interface

**Setup**
- React com Vite. Proxy no `vite.config.js` encaminhando `/api` e `/healthz`
  para o backend, em vez de configurar CORS. Assim as chamadas são relativas e
  continuam funcionando quando o React for buildado e servido pelo próprio
  FastAPI.

**Upload e polling**
- Depois do POST, a tela consulta o GET a cada 2 segundos até o status virar
  `concluido` ou `erro`. A primeira consulta sai imediatamente, sem esperar os
  2 segundos, senão a tela ficaria muda no começo.
- Além do spinner, mostro um contador de segundos. Spinner sozinho fica
  idêntico com o backend trabalhando ou travado; o relógio andando distingue
  os dois.
- O efeito depende do `status`, não do objeto da transcrição. Se dependesse do
  objeto, cada resposta criaria um intervalo novo e as consultas dobrariam a
  cada ciclo.

**Tabela editável**
- A lógica dos avisos ficou em funções puras separadas do componente,
  espelhando o que o `planilha.py` faz no backend. Conferi que as colunas, a
  ordem, as linhas e os destaques batem exatamente com a planilha gerada: se
  divergissem, a tela mostraria uma coisa e o arquivo baixado outra.
- Os avisos são derivados na hora de exibir, nunca campos do JSON.

**Decisão: editar preserva o `time_raw`**
- Ao corrigir uma batida, altero o `time_hhmm` e mantenho o `time_raw`. É o par
  que o contrato descreve: o documento diz uma coisa, eu interpretei outra, e a
  divergência entre os dois é o que permite auditar a correção depois.

**Decisão: célula vazia cria a batida**
- Digitar numa coluna além das batidas existentes cria a batida. Sem isso, o
  dia com aviso de batidas ímpares não teria como ser corrigido pela interface,
  que é justamente o problema que o aviso existe para sinalizar. O `kind` sai
  da posição: par é IN, ímpar é OUT.

**Decisão: coluna de aviso por escrito**
- Além da cor, uma coluna no fim com o motivo em texto. Cor sozinha não
  comunica para quem não distingue cores ou usa leitor de tela, e o enunciado
  pede o motivo legível, não só o destaque visual.

**Bug encontrado**
- Nomeei a lógica como `tabela.js` ao lado do componente `Tabela.jsx`. O
  Windows não diferencia maiúsculas, então o import resolveu para o arquivo
  errado e o build quebrou. No Linux resolveria certo, então isso passaria
  despercebido aqui e quebraria só no deploy. Renomeei para `regrasTabela.js`.
- Depois de renomear, o erro persistiu até eu reiniciar o Vite: o cache dele
  ainda segurava o módulo antigo.

**Limitação conhecida**
- Estado só em React, sem armazenamento no navegador. Recarregar a página perde
  o id e a transcrição em andamento. O backend continua processando, mas o
  front não tem como voltar a ela.

**Salvar e baixar**
- Dois botões abaixo da tabela: salvar correções, que manda o PUT com o estado
  atual, e baixar, com escolha entre os três formatos.

**Decisão: download com alterações pendentes**
- Quando há edição não salva, o botão de baixar salva antes. Se o PUT falhar, o
  download é abortado com o erro na tela.
- A alternativa era desabilitar o download até salvar, mas isso deixa a pessoa
  travada sem entender o motivo. Salvar antes honra a intenção de "me dê a
  tabela atual como arquivo", e nunca entrega arquivo desatualizado em silêncio.
- O estado de pendência fica sempre visível na tela.

**Decisão: download por blob em vez de navegação**
- Navegar para a URL funcionaria, porque o backend já manda o
  `Content-Disposition`. Mas um erro do backend substituiria a página por um
  JSON numa aba. Com fetch eu confiro o status antes e só disparo o download em
  caso de sucesso.

**Como validei o ciclo completo**
- Duas edições diferentes: correção de valor (09:03 para 07:45) e criação de
  batida faltante no 29/10.
- As duas chegaram nos três formatos.
- O `time_raw` do PDF sobreviveu à correção, então a divergência com o
  `time_hhmm` continua auditável.
- O destaque amarelo do 29/10 sumiu da planilha depois da correção: o backend
  rederivou o aviso a partir do dado corrigido, igual à tabela na tela. É a
  prova de que os avisos são derivados e não armazenados, de ponta a ponta.

  **Docker**
- Dockerfile em dois estágios: Node buildando o frontend, Python servindo o
  build junto com a API. O Node não fica na imagem final.
- Tesseract e o pacote de português instalados no container desde o começo,
  antes mesmo do código de OCR existir, para não precisar rebuildar depois.
- O compose sobe um serviço só, com a porta do host configurável por variável
  de ambiente.

**Onde validei, e por quê não foi na minha máquina**
- O firmware do meu notebook não expõe a opção de virtualização na BIOS, mesmo
  com o processador reportando VT-x como suportado. Sem isso o Docker Desktop
  não inicia o engine.
- Consegui subir depois de habilitar o WSL 2 pelo DISM, mas o build morria por
  falta de memória: a máquina tem 4 GB e o buildkit era encerrado no meio.
- Validei no GitHub Codespaces, que é um ambiente Linux com Docker instalado.
  `docker compose up --build` sobe, a interface carrega e o ciclo completo
  funciona dentro do container.

  ---

## OCR

**Detecção**
- Uma página precisa de OCR quando tem menos de 200 caracteres extraíveis, não
  quando tem zero. O `payroll-04` tem 83 caracteres por página que são só o
  carimbo de assinatura eletrônica sobreposto à imagem, e uma checagem ingênua
  de "tem texto?" o classificaria como legível.
- Isso corrige o que o `checar.py` do dia 1 me disse. Ele reportou os quatro
  holerites como TEXTO, e o `payroll-04` na verdade é imagem.

**Onde o OCR entra**
- Num módulo separado que é a fonte única de texto. Os extratores receberam
  uma lista de strings e não sabem se veio da camada nativa ou do Tesseract.

**Decisão: limiar de confiança em 60**
- Escolhi medindo, não por convenção. A distribuição de confiança do
  `time-card-02` é bimodal: 83% das palavras entre 90 e 99, e a cauda baixa
  some rápido. O vale está entre 50 e 69, então 60 corta no ponto mais raro.
- Validei contra o que importa: os 40 horários da página têm confiança mínima
  88 e mediana 92. Com limiar 60 nenhum horário é marcado à toa, e a marcação
  cai sobre lixo de OCR.
- Subir para 75 marcaria valores corretos; subir para 90 marcaria horários bons.
  Marcar demais é tão nocivo quanto marcar de menos: enche o documento de `?`
  que o revisor precisa conferir à mão.

**Decisão: confiança por palavra, `?` por caractere**
- O Tesseract dá confiança por palavra e o contrato pede `?` por caractere.
  Quando ele diz "10:35, confiança 42", nada indica qual dígito é o duvidoso.
- Não marcar nada entregaria palpite com cara de leitura firme, que é o erro
  que o `?` existe para evitar. Trocar a palavra inteira por `?????` apagaria
  a estrutura, e sumiria até a informação de que ali havia um horário.
- Escolhi trocar os caracteres de conteúdo e preservar a pontuação: `10:35`
  vira `??:??`. Os dois pontos não vêm de reconhecer um glifo duvidoso, vêm da
  forma do campo, e mantê-los deixa visível o que se perdeu.

**O OCR funcionou, mas não era a última barreira**
- O texto do `time-card-02` sai limpo, e mesmo assim o extrator devolvia zero
  batidas. O layout é outro: onde o `time-card-01` escreve `1 - DOM`, ele
  escreve `01 SAB`, sem o traço.
- Levantando os três arquivos, achei cinco formas de escrever a linha do dia:
  `1 - DOM`, `01 SAB`, `11TER` colado, `?? TER` com o dia ilegível, e a data
  completa `16/12/2019 SEG`.

**Bug encontrado no teste**
- O padrão usava `\b` no fim da sigla, mas `?` não é caractere de palavra,
  então linhas como `?? ??? Sem Registro` escapavam. Justamente os dias
  ilegíveis, que são os que mais importam sinalizar. Trocado por `(?=\s|$)`,
  o que recuperou 6 dias.
- E a regra do dia repetido precisou de ajuste: dois `??` seguidos são dias
  diferentes que o OCR não leu, então dia incerto nunca conta como repetição.

**O que o agente fez além do pedido, e por quê aceitei**
- Pedi só a flexibilização do padrão de dia. Ele também ajustou o descarte da
  coluna Jornada e o tratamento do traço entre horários.
- Aceitei porque a mudança sozinha teria produzido "152 dias, 81 batidas" com
  metade dos dados faltando. O `time-card-02` não tem coluna Jornada, então o
  extrator descartava a entrada real; e o parsing parava no hífen de
  `12:00 - 18:15`, perdendo todas as saídas. Erro apresentado como sucesso é
  pior que a falha honesta anterior.

**Limitação conhecida: ordem das batidas no time-card-02**
- Nesse layout a coluna Intervalo vem depois de Entrada e Saída, então as
  batidas saem na ordem do papel mas não em ordem cronológica. O `kind`
  alternado acaba rotulando o início do intervalo como entrada.
- Mantive a ordem do documento porque é o que o contrato pede explicitamente.
  Corrigir exigiria interpretar o significado de cada coluna, que é decisão de
  produto e não de parsing.

**Custo do OCR**
- Entre 5 e 30 segundos por página, contra 1 segundo por página no caminho
  nativo. O render a 300 DPI é o que domina. Reduzir para 200 DPI ou escala de
  cinza é o caminho para acelerar, mas muda a qualidade da leitura.

  **Teste que passa não é o mesmo que coisa que funciona**
- Ao implementar o PDF ao lado da tabela, a primeira rodada passou em tudo:
  200 na rota, iframe acessível, layout correto nos três tamanhos de tela.
  E o PDF não aparecia: o navegador headless usado no teste não tem
  visualizador de PDF embutido.
- Só ficou visível quando alguém olhou a captura de tela em vez dos números.
  Com o PDF de fato renderizando, apareceu um segundo problema real de layout
  que o teste cego escondia.
- Registro isso porque é o tipo de falha que passaria pela revisão de código
  e pelos testes automatizados ao mesmo tempo.

**Testar a proteção, não só o caminho feliz**
- A rota do documento tem duas barreiras: o id precisa existir no dicionário,
  e o caminho resolvido precisa estar dentro de `uploads/`. Testar só por URL
  não distingue as duas, porque a primeira barreira mascara a segunda.
- Injetei um id que resolve para um PDF real fora de `uploads/`: passou a
  primeira barreira e a segunda recusou. Sem esse teste, remover a proteção de
  caminho num refactor futuro não quebraria nenhum teste existente.

  **PDF ao lado da tabela**
- Rota `GET /api/transcricoes/{id}/documento` serve o PDF original com
  `Content-Disposition: inline`, não `attachment`, senão o navegador baixa em
  vez de exibir.
- Recusa id inexistente com 404 e valida que o caminho resolvido está dentro
  de `uploads/`, contra travessia de diretório.
- No front, `<iframe>` com o leitor nativo do navegador, sem biblioteca de
  renderização: o leitor nativo já traz zoom, busca e paginação. Mais um link
  para abrir em nova aba, como saída para navegadores que bloqueiam PDF
  embutido.
- Layout de duas colunas que empilha em tela estreita.

**payroll-02**
- Generalizou no parsing: as seis diferenças de layout caíram em pontos que o
  extrator já tratava como parâmetro. A mais perigosa era o valor: neste modelo
  desconto é sinal negativo, não coluna separada, e o padrão de valor não
  aceitava o sinal. A verba virava label sem valor, falha silenciosa.
- Não generalizou no modelo: cada página traz duas folhas (MÊS e ACERTO) na
  mesma competência, com as mesmas verbas repetidas. Escolhi uma linha por
  folha, com o rótulo vindo do próprio documento.
- Descartei as alternativas: pôr o nome da folha no label desviaria do "label
  exatamente como impresso", e processar só a folha MÊS descartaria dado de
  propósito.
- Verba repetida dentro da mesma folha vira coluna com sufixo numérico, e o
  sufixo é removido ao gravar de volta na edição.

**Teste de paridade entre tela e planilha**
- O front espelha as regras do backend, e isso era só uma promessa em
  comentário. Escrevi um teste que monta a tabela nas duas implementações sobre
  o mesmo dado e compara colunas, células e destaques.
- Sem ele, a tela poderia mostrar uma coisa e o arquivo baixado outra.

**Rodar o OCR localmente**
- No Windows, o `pip install pytesseract` instala só o wrapper. O binário do
  Tesseract é instalador separado, e o instalador não conseguiu escrever o
  `por.traineddata` em Program Files por falta de permissão, deixando o arquivo
  em `%LOCALAPPDATA%`.
- Resultado: o Tesseract subia mas não achava o idioma português, e a
  transcrição falhava com "Could not initialize tesseract".
- No Docker nada disso acontece: o Dockerfile instala `tesseract-ocr` e
  `tesseract-ocr-por` via apt, e o módulo funciona sem configuração.

## Cite 3 decisões em que havia mais de uma resposta razoável. Por que escolheu essa?

## O que na sua solução quebra primeiro em produção?

## Onde você não confia no que entregou?
