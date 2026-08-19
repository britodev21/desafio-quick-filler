# Solução
 
Transcrição de cartões de ponto e holerites em PDF para planilhas estruturadas, com revisão manual antes do download.
 
## Como rodar
 
**Local**
 
Precisa de Python 3.13+, Node 22+ e o binário do Tesseract com o pacote de idioma português instalado — o `pip install pytesseract` traz só o wrapper. Sem ele os PDFs com camada de texto continuam funcionando e os escaneados falham.
 
Backend, a partir da raiz do repositório:
 
```bash
python -m venv venv
source venv/bin/activate            # Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```
 
API em `http://127.0.0.1:8000`, com `/healthz` respondendo `{"status":"ok"}`.
 
Frontend, em outro terminal:
 
```bash
cd frontend
npm install
npm run dev
```
 
Interface em `http://localhost:5173`. O Vite encaminha `/api` e `/healthz` para o backend, então nada de CORS precisa ser configurado.
 
Para rodar num processo só, como em produção: `npm run build` dentro de `frontend/` e depois o uvicorn. Com `frontend/dist` presente, o FastAPI serve a interface na própria porta 8000.
 
**Docker**
 
```bash
docker compose up --build
```
 
Aplicação em `http://localhost:8000`, interface e API na mesma porta. A imagem instala o Tesseract e o pacote de português, então o OCR funciona sem configuração nenhuma.
 
A porta do host sai da variável `PORTA`:
 
```bash
PORTA=9000 docker compose up        # PowerShell: $env:PORTA=9000; docker compose up
```
 
**Aplicação publicada**
 
https://desafio-quick-filler.onrender.com/

---
 
## Stack
 
- **Backend**: Python + FastAPI. O gargalo do desafio é extração de documento, não serving HTTP, e o ecossistema de PDF e OCR do Python é mais maduro.
- **Frontend**: React + Vite, buildado como estático e servido pelo próprio FastAPI. Um container só.
- **PDF**: pdfplumber. **OCR**: Tesseract via pytesseract. **Planilha**: openpyxl.
- **Deploy**: Render, via Docker.
---
 
## O que a solução cobre
 
Quatro dos oito PDFs de exemplo processam de ponta a ponta.
 
| Arquivo | Situação |
|---|---|
| `time-card-01` | 153 dias, 369 batidas |
| `time-card-02` | 152 dias, 318 batidas, via OCR |
| `payroll-02` | 10 folhas em 5 páginas, 92 verbas |
| `payroll-03` | 5 competências, 44 verbas |
| `time-card-03` | OCR lê, mas o cabeçalho sai ilegível e os horários vêm com sufixo |
| `time-card-04` | Foto ilegível: o OCR devolve quase só `?` |
| `payroll-01` | Ficha financeira, com vários meses por página e três colunas lado a lado |
| `payroll-04` | OCR lê, mas proventos e descontos ficam em colunas lado a lado |
 
Nenhum dos quatro que faltam falha por ausência de OCR. Em todos o texto sai; o que resta é parsing de layout.
 
---
 
## Arquitetura
 
O OCR fica num módulo separado que é a fonte única de texto. Os extratores recebem uma lista de strings e não sabem se veio da camada nativa do PDF ou do Tesseract. A decisão de usar OCR acontece antes de separar por tipo de documento, então vale para cartão de ponto e holerite igualmente.
 
Um dicionário único valida o tipo recebido e escolhe o extrator, para os dois não ficarem fora de sincronia. As funções geradoras de planilha seguem o mesmo padrão, indexadas por tipo e formato, então a rota de download resolve com uma busca em vez de condicional por formato.
 
O processamento roda em background: o POST devolve o id imediatamente e a extração continua por trás. Processar dentro do request quebraria em produção, quando o proxy da plataforma corta a conexão antes de a extração terminar.
 
---
 
## Armazenamento e retenção
 
As transcrições ficam em memória, num dicionário do processo. Não uso banco: o enunciado diz que é opcional e que só precisa funcionar entre o envio e o download.
 
Os PDFs enviados ficam em `uploads/` e as planilhas geradas em `planilhas/`. Ao iniciar, a aplicação apaga tudo dos dois diretórios: como o dicionário de transcrições nasce vazio a cada início, qualquer arquivo que estivesse lá é órfão sem id que o referencie.
 
Isso resolve a retenção sem quebrar a tela de revisão, onde o PDF precisa estar disponível durante a sessão. No plano gratuito do Render, que dorme por inatividade, vira limpeza automática a cada ciclo.
 
Arquivo travado por outro processo é contado à parte e vira aviso, sem derrubar a subida. Subpastas não são tocadas.
 
---
 
## Extração: cartão de ponto
 
**Classificação das linhas**
 
Cada linha é classificada em início de dia, continuação do dia anterior, ou lixo. A classificação vem antes da extração porque as duas primeiras têm colunas diferentes: a linha de dia traz a Jornada no começo, a de continuação não.
 
**Dia repetido**
 
Dois dias do `time-card-01` repetem o número na linha de continuação em vez de omitir. As duas linhas viram um registro só.
 
Isso contraria o "um item por linha do documento" literal do contrato. Separar criaria data duplicada e alarme falso de "data não sequencial", e representaria o mesmo fato de duas formas dependendo de como o sistema imprimiu.
 
**Separação entre batida e não-batida**
 
Todos os horários da linha têm o mesmo formato `HH:MM`: Jornada, batidas e Qtde. A distinção é por posição, não por formato.
 
Escolhi posição em vez de coordenada por prazo. A alternativa exigiria trabalhar com coordenadas de PDF, que eu não conhecia, e preferi a solução que conseguia validar no mesmo dia.
 
**Processamento por página**
 
Cada página do PDF é um mês fechado e recomeça a contagem no dia 1, então cada página é tratada de forma independente: encontra o próprio cabeçalho, classifica as próprias linhas, agrupa os próprios dias. Classificando as cinco juntas, a regra do "dia igual ao anterior é continuação" quebraria na virada de mês.
 
**Cinco formas de escrever a linha do dia**
 
O reconhecimento aceita `1 - DOM`, `01 SAB`, `11TER` colado, `?? TER` com o dia ilegível, e a data completa `16/12/2019 SEG`.
 
Duas correções vieram do teste. O padrão usava `\b` no fim da sigla, mas `?` não é caractere de palavra, então linhas como `?? ??? Sem Registro` escapavam, justamente os dias ilegíveis, que são os que mais importam sinalizar. E a regra do dia repetido precisou de ajuste: dois `??` seguidos são dias diferentes que o OCR não leu, então dia incerto nunca conta como repetição.
 
**`date_raw` montado**
 
A data completa nunca aparece numa linha só: a linha traz o dia e o mês/ano fica no cabeçalho da página. O `date_raw` junta os dois, com zero à esquerda.
 
Nenhuma das duas informações é inventada, mas é composição e não transcrição literal. Sem isso o `date_raw` teria só o dia, e a detecção de data não sequencial não conseguiria distinguir a virada de mês de um erro de leitura.
 
**Normalização de horário**
 
`time_raw` e `time_hhmm` saem idênticos no `time-card-01`, porque o documento já imprime com zero à esquerda. A normalização usa `zfill` em vez de conversão numérica, para que um caractere ilegível como `?:25` vire `0?:25` em vez de estourar.
 
---
 
## Extração: holerite
 
**O que define uma verba**
 
Ter valor monetário, não ter código na frente. O contrato aceita `code` vazio quando o documento não mostra, então ancorar no código descartaria verbas legítimas.
 
**Rótulos de base ancorados no nome inteiro**
 
A linha `Dep. I.R.R.F. : 0,00 Base FGTS: 1.967,07` traz dois rótulos, e `Dep. I.R.R.F.` é contagem de dependentes, não base. Casar só por `I.R.R.F.` colocaria lixo em `bases`, e errar essa divisão contamina a planilha inteira.
 
**O Total duplicado**
 
A linha `Total` traz dois valores, proventos e descontos, e vira duas entradas com o mesmo label. Considerei renomear para `Total Proventos` e `Total Descontos` para não confundir quem revisa, mas isso desviaria do "label exatamente como impresso". O JSON fica fiel e a distinção é responsabilidade da apresentação, mesma lógica do `_raw` versus normalizado.
 
**Duas folhas na mesma competência**
 
O `payroll-02` traz `MÊS` e `ACERTO` na mesma competência, com as mesmas verbas repetidas entre as folhas. Cada folha vira uma entrada, com o rótulo vindo do próprio documento, e as cinco páginas produzem dez linhas.
 
As alternativas foram descartadas: pôr o nome da folha no label desviaria do "label exatamente como impresso", e processar só a folha MÊS descartaria dado de propósito.
 
Verba repetida dentro da mesma folha vira coluna com sufixo numérico, e o sufixo é removido ao gravar de volta na edição.
 
**Desconto como sinal negativo**
 
No `payroll-02`, desconto é sinal negativo e não coluna separada. O padrão de valor não aceitava o sinal, então a verba virava label sem valor: falha silenciosa, não erro.
 
---
 
## OCR
 
**Detecção**
 
Uma página precisa de OCR quando tem menos de 200 caracteres extraíveis, não quando tem zero. O `payroll-04` tem 83 caracteres por página que são só o carimbo de assinatura eletrônica sobreposto à imagem, e uma checagem de "tem texto?" o classificaria como legível.
 
**Limiar de confiança em 60**
 
Escolhido por medição. A distribuição de confiança do `time-card-02` é bimodal: 83% das palavras entre 90 e 99, e a cauda baixa some rápido. O vale está entre 50 e 69, então 60 corta no ponto mais raro, onde a fronteira é menos arbitrária.
 
Validado contra o que importa: os 40 horários da página têm confiança mínima 88 e mediana 92. Com limiar 60 nenhum horário é marcado à toa, e a marcação cai sobre lixo de OCR. Subir para 75 marcaria valores corretos; subir para 90 marcaria horários bons. Marcar demais é tão nocivo quanto marcar de menos: enche o documento de `?` que o revisor precisa conferir à mão.
 
**Confiança por palavra, `?` por caractere**
 
O Tesseract dá confiança por palavra e o contrato pede `?` por caractere. Quando ele diz "10:35, confiança 42", nada indica qual dígito é o duvidoso.
 
Não marcar nada entregaria palpite com cara de leitura firme, que é o erro que o `?` existe para evitar. Trocar a palavra inteira por `?????` apagaria a estrutura, e sumiria até a informação de que ali havia um horário.
 
A solução troca os caracteres de conteúdo e preserva a pontuação: `10:35` vira `??:??`. Os dois pontos não vêm de reconhecer um glifo duvidoso, vêm da forma do campo, e mantê-los deixa visível o que se perdeu.
 
**Custo**
 
Entre 5 e 30 segundos por página, contra 1 segundo por página no caminho nativo. O render a 300 DPI é o que domina. Reduzir para 200 DPI ou escala de cinza aceleraria, mas muda a qualidade da leitura.
 
---
 
## Planilhas
 
**Cartão de ponto**
 
Uma linha por dia, coluna Data mais os pares Entrada/Saída, com tantos pares quantos o dia com mais batidas exigir.
 
**Holerite**
 
A transposição. No documento as verbas são lista vertical por página; na planilha viram matriz larga, uma coluna por verba distinta na ordem de primeira aparição global no documento.
 
Só `fields` viram coluna. As `bases` ficam fora da planilha, conforme o contrato, e é justamente isso que o enunciado chama de "contaminar a planilha" se uma base entrar em `fields` por engano.
 
**Avisos**
 
Os quatro avisos são derivados na hora de gerar, nunca campos do JSON.
 
Uma data com `?` não vira alerta vermelho, e a próxima data legível é comparada com a última legível, não com a ilegível. O enunciado escreve essa regra para o holerite; estendi por analogia para o cartão de ponto, onde o texto não detalha. O efeito é que `10/07 → 1?/07 → 12/07` marca o `12/07` como não sequencial, porque a comparação vê salto de dois dias. Se o `1?` era 11, a linha foi marcada à toa: é a leitura conservadora, porque marcar a mais é melhor que deixar passar.
 
**Separador do CSV**
 
`;` em vez de `,`. É o que o Excel em português entende como separador de lista. Com vírgula o arquivo abre todo na coluna A, e o BOM resolve o encoding mas não o separador.
 
Como o produto é para RH brasileiro, o CSV precisa abrir corretamente ao ser clicado. O custo é fugir do padrão internacional; um parâmetro opcional na rota resolveria os dois casos, mas não está no contrato. Efeito colateral bom: os valores monetários deixaram de sair entre aspas, porque a vírgula decimal não é mais o delimitador.
 
**Detalhes**
 
Mês e Ano ficam como texto, não número: converter comeria o zero à esquerda de `01`. Célula de verba ausente é nula, não string vazia. Verba repetida na mesma folha mantém o primeiro valor e emite aviso no log, porque a matriz tem uma célula só e em silêncio um valor sumiria.
 
**Estrutura compartilhada**
 
A construção da tabela fica numa estrutura intermediária que o xlsx e o CSV consomem. A igualdade entre os dois formatos passa a ser estrutural: não dá para mudar uma coluna num e esquecer o outro.
 
---
 
## API
 
**Download**
 
A planilha é gerada a partir do `value` atual da transcrição, que é o corrigido se houve PUT. É isso que faz a correção chegar na planilha. O arquivo é gravado com o id no nome, para dois pedidos simultâneos não escreverem o mesmo arquivo.
 
**409 para transcrição ainda não pronta**
 
Não 404 nem 400. A transcrição existe, o problema é o estado: 404 diria que o recurso não existe, e 400 culparia o pedido, que está correto. O mesmo 409 cobre `status: erro`, com a mensagem dizendo qual dos dois casos é. O enunciado não fixa código para essa situação.
 
**Ordem das validações**
 
Id, status, formato. Efeito colateral: pedir um formato inválido de uma transcrição ainda processando devolve 409, não 400, mesmo o formato sendo permanentemente inválido.
 
**PDF original**
 
`GET /api/transcricoes/{id}/documento` serve o PDF com `Content-Disposition: inline`, não `attachment`, senão o navegador baixa em vez de exibir. Recusa id inexistente com 404 e valida que o caminho resolvido está dentro de `uploads/`.
 
---
 
## Interface
 
**Upload e acompanhamento**
 
Depois do POST, a tela consulta o GET a cada 2 segundos até o status virar `concluido` ou `erro`. A primeira consulta sai imediatamente, senão a tela ficaria muda no começo.
 
Além do indicador de carregamento, há um contador de segundos: um spinner sozinho fica idêntico com o backend trabalhando ou travado, e o relógio andando distingue os dois.
 
**Tabela editável**
 
A lógica dos avisos fica em funções puras separadas do componente, espelhando o que o backend faz. As colunas, a ordem, as linhas e os destaques batem exatamente com a planilha gerada: se divergissem, a tela mostraria uma coisa e o arquivo baixado outra.
 
Editar uma batida altera o `time_hhmm` e preserva o `time_raw`. É o par que o contrato descreve: o documento diz uma coisa, o sistema interpretou outra, e a divergência entre os dois é o que permite auditar a correção depois.
 
Digitar numa coluna além das batidas existentes cria a batida. Sem isso, o dia com aviso de batidas ímpares não teria como ser corrigido pela interface, que é justamente o problema que o aviso existe para sinalizar.
 
Além da cor, uma coluna no fim traz o motivo do destaque em texto. Cor sozinha não comunica para quem não distingue cores ou usa leitor de tela, e o enunciado pede o motivo legível.
 
**PDF ao lado**
 
Visualizador nativo do navegador em `<iframe>`, sem biblioteca de renderização: o leitor nativo já traz zoom, busca e paginação. Mais um link para abrir em nova aba, como saída para navegadores que bloqueiam PDF embutido. Layout de duas colunas que empilha em tela estreita.
 
**Salvar e baixar**
 
Quando há edição não salva, o botão de baixar salva antes. Se o PUT falhar, o download é abortado com o erro na tela.
 
A alternativa era desabilitar o download até salvar, mas isso deixa a pessoa travada sem entender o motivo. Salvar antes honra a intenção de "me dê a tabela atual como arquivo", e nunca entrega arquivo desatualizado em silêncio. O estado de pendência fica sempre visível.
 
O download vai por blob em vez de navegação: navegar para a URL funcionaria, porque o backend manda o `Content-Disposition`, mas um erro do backend substituiria a página por um JSON numa aba.
 
**Proxy em vez de CORS**
 
O Vite encaminha `/api` e `/healthz` para o backend em desenvolvimento. Assim as chamadas são relativas e continuam funcionando quando o React é buildado e servido pelo próprio FastAPI.
 
---
 
## Segurança e privacidade
 
- Validação do tipo: 400 se não for `cartao-ponto` ou `holerite`.
- Validação de que o arquivo é PDF de verdade, pelos primeiros bytes, não pela extensão.
- A validação acontece antes da gravação, então upload recusado não deixa arquivo pela metade em disco.
- O nome do arquivo salvo é o uuid gerado pelo sistema, nunca o nome que veio do cliente. Um arquivo chamado `../../algo.pdf` não escapa do diretório.
- Mensagem de erro genérica para o cliente; o traceback completo vai só para o log do servidor. O cliente da API não precisa saber caminho de arquivo, e o documento é de outra pessoa.
- Os extratores usam `logger.debug` no lugar de `print`, com os valores passados como argumento em vez de f-string, para o texto só ser montado quando o debug está ligado. Importado como biblioteca, o extrator não emite nada em stdout nem stderr.
- O nível de log é INFO e não DEBUG: DEBUG no logger raiz ligaria junto o do `pdfminer`, que despeja o log interno do parser.
---
 
## Testes
 
- Paridade entre tela e planilha: escolhi esse caso para garantir que o que aparece na tela seja igual ao que é gerado no arquivo baixado.
- Regras de destaque que o dado real não exercita: escolhi casos sintéticos para testar também as regras de alerta que os documentos reais não acionam.
- Regressão a cada mudança em peça compartilhada: escolhi o payroll-03 para garantir que uma alteração em um padrão compartilhado não quebrasse um documento que já funcionava.
 
**Paridade entre tela e planilha**
 
O front espelha as regras do backend, e isso era só uma promessa em comentário. O teste monta a tabela nas duas implementações sobre o mesmo dado e compara colunas, células e destaques. Sem ele, a tela poderia mostrar uma coisa e o arquivo baixado outra.
 
**Regras de destaque que o dado real não exercita**
 
O `time-card-01` tem datas perfeitamente sequenciais, então só uma das quatro regras disparava. As outras três foram testadas com dados sintéticos, lendo as cores de volta do arquivo salvo em vez de conferir só o código.
 
**Regressão a cada mudança em peça compartilhada**
 
O `payroll-03` roda como regressão sempre que o extrator de holerite muda, porque padrões como o de valor e o de código são usados pelos dois documentos.
 
---
 
## Ambiente
 
**Docker**
 
Dockerfile em dois estágios: Node buildando o frontend, Python servindo o build junto com a API. O Node não fica na imagem final. Tesseract e o pacote de português são instalados no container. O compose sobe um serviço só, com a porta do host configurável por variável de ambiente.
 
**Onde o compose foi validado**
 
O firmware do meu notebook não expõe a opção de virtualização na BIOS, mesmo com o processador reportando VT-x como suportado. Depois de habilitar o WSL 2 pelo DISM o Docker Desktop subiu, mas o build morria por falta de memória, com 4 GB disponíveis.
 
Validei no GitHub Codespaces, que é um ambiente Linux com Docker instalado: `docker compose up --build` sobe, a interface carrega e o ciclo completo funciona dentro do container.
 
**Rodar o OCR fora do Docker**
 
No Windows, o `pip install pytesseract` instala só o wrapper. O binário do Tesseract é instalador separado, e no meu caso ele não conseguiu escrever o `por.traineddata` em Program Files por falta de permissão, deixando o arquivo em `%LOCALAPPDATA%`. O resultado era o Tesseract subir sem achar o idioma português. No Docker nada disso acontece.
 
---
 
## O que ficou de fora
 
- Layouts de holerite do `payroll-01` (ficha financeira) e do `payroll-04` (proventos e descontos lado a lado).
- Layouts de cartão de ponto do `time-card-03` (cabeçalho ilegível após OCR) e do `time-card-04` (foto que o OCR não lê).
- CI com lint e testes.
---
 
## Limitações conhecidas
 
**Ordem das batidas no `time-card-02`**
 
Nesse layout a coluna Intervalo vem depois de Entrada e Saída, então as batidas saem na ordem do papel mas não em ordem cronológica, e o `kind` alternado rotula o início do intervalo como entrada. Mantive a ordem do documento porque é o que o contrato pede explicitamente. Corrigir exigiria interpretar o significado de cada coluna, que é decisão de produto e não de parsing.
 
**Leitura posicional**
 
Qualquer mudança na ordem das colunas quebra a leitura, porque a regra é posicional. Se um PDF vier sem a coluna Jornada, a primeira batida é descartada, e o sintoma é um dia com número ímpar de batidas. Por isso existe o detector de dias ímpares.
 
**`date_raw` composto**
 
Se a validação comparar o `date_raw` com o texto cru da linha, não bate, porque a data completa não está impressa numa linha só.
 
**Downloads simultâneos**
 
Dois downloads do mesmo id e formato ao mesmo tempo escreveriam o mesmo arquivo. Gravar num temporário e renomear resolveria.
 
**Estado do frontend**
 
Estado só em React, sem armazenamento no navegador. Recarregar a página perde o id e a transcrição em andamento. O backend continua processando, mas o front não tem como voltar a ela.

**Diagnóstico de falha confunde OCR ilegível com layout desconhecido**

A decisão de usar OCR é por contagem de caracteres, e a marcação de incerteza
substitui caractere ilegível por `?`, que também conta como caractere. Uma
página de puro ruído produz caracteres suficientes para passar no teste de
"tem texto útil", e o diagnóstico conclui que o problema é layout quando na
verdade o OCR não leu nada. Foi o que aconteceu com o `time-card-04`.
Cruzar a proporção de palavras incertas antes de concluir resolveria.
 
---
 
## O que eu mudaria no formato JSON
 
Acredito que eu não mudaria nada no formato JSON. Vejo que no formato atual o sistema interpreta bem, e não reatiraria e não adicionaria nada no corpo, da forma que está, tem o necessário.