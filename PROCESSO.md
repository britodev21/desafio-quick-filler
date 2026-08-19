# Processo
 
## Ferramentas
 
- **Claude (chat)**: planejamento, ordem de trabalho, decisões de arquitetura e explicação de conceitos.
- **Claude Code na IDE**: escrita de código. Trabalhei pedindo uma etapa por vez e revisando cada entrega antes de seguir, com critério de acerto definido antes de rodar.
---
 
## Onde o agente errou ou foi além do que pedi
 
**Decidiu sem eu pedir: o dia repetido**
 
- Pedi só a classificação das linhas do cartão de ponto. Ele entregou isso e mais uma decisão que eu não tinha pedido: o tratamento dos dias 17 e 27, que repetem o número em vez de omitir na linha de continuação.
- Percebi ao revisar e decidi manter. O dia 17 tem 4 batidas na realidade; juntar produz isso. Separar produziria dois registros de 2, que não corresponde ao que aconteceu. Nenhum dado se perde, todas as batidas continuam lá, só agrupadas. Os avisos continuam funcionando: se sobrar batida ímpar depois de juntar, o alerta dispara igual. E separar criaria data duplicada e alarme falso de "data não sequencial".
**Apontou um risco que não existia**
 
- Ele levantou um risco no dia 30, um horário de batida com o mesmo valor de um horário de outra coluna. Conferi e não procede: a separação é por posição, não por valor, então valores iguais não se confundem.
**Foi além do pedido no OCR, e aceitei**
 
- Pedi só a flexibilização do padrão de dia. Ele também ajustou o descarte da coluna Jornada e o tratamento do traço entre horários.
- Aceitei porque a mudança sozinha teria produzido "152 dias, 81 batidas" com metade dos dados faltando. O `time-card-02` não tem coluna Jornada, então o extrator descartava a entrada real; e o parsing parava no hífen de `12:00 - 18:15`, perdendo todas as saídas. Erro apresentado como sucesso é pior que a falha honesta anterior.
**Alinhou o front sem eu pedir, no payroll-02**
 
- Pedi só o extrator. Ele também ajustou o `regrasTabela.js`, que teria quebrado em três frentes: sem coluna Folha as dez linhas ficariam indistinguíveis, o valor da verba repetida sumiria, e as cinco linhas de ACERTO apareceriam vermelhas como "mês não sequencial", porque a regra exigia diferença de exatamente 1 mês entre linhas.
---
 
## O que escrevi à mão
 
**O PUT guardando a correção**
 
- Foi o primeiro trecho que escrevi sem o agente. Errei duas vezes antes de acertar: primeiro copiei o bloco do POST inteiro, que cria a transcrição do zero quando aqui ela já existe; depois embrulhei o `correcao.value` dentro de outro dicionário, o que teria criado um `value` dentro do `value`.
- Sem essa rota guardando de verdade, a planilha sairia sempre com a transcrição original e a correção da pessoa se perderia.
---
 
## Onde travei
 
**O 422 que não era bug**
 
- Troquei o `value` de `str` para `dict` e fui testar se a API recusava o formato errado. Deu 200 e achei que a validação estava quebrada. Reiniciei o servidor, conferi o código, não achei nada.
- Aí percebi que o problema era o meu teste: eu estava mandando um objeto com texto dentro, e achando que estava mandando texto. Quando mandei texto de verdade, deu 422. A validação sempre funcionou.
---
 
## Como conduzi o trabalho
 
**Investigação antes de escrever extrator**
 
- Escrevi dois scripts descartáveis antes de qualquer código de produto. O `checar.py` me disse quais arquivos dava para ler; o `ver.py` me mostrou o que tinha dentro de um deles.
- Foi assim que descobri as exceções do documento antes de começar: a data sem mês e ano, o dia que ocupa mais de uma linha, o horário fixo que é coluna Jornada e não batida, os dias que repetem o número, e o cabeçalho de sistema misturado no texto.
**Ordem de trabalho: esqueleto antes da extração, texto limpo antes do OCR**
 
- Fiz as cinco rotas e o deploy antes de qualquer extração. Problema de deploy com a aplicação simples é fácil de achar; com tudo pronto, não.
- E escrevi o extrator contra o único cartão de ponto com camada de texto antes de ligar o OCR. Com entrada confiável, qualquer falha só podia vir da minha lógica. Com o extrator validado, erro novo indicava problema de leitura.
**Validação independente do código**
 
- No cartão de ponto: os dias de cada página batem com o calendário real de 2012 (jul 31, ago 31, set 30, out 31, nov 30), e o dia da semana da primeira linha de cada página também confere. Se alguma linha tivesse se perdido ou duplicado, o dia da semana não bateria.
- No holerite: a soma dos 9 valores extraídos dá exatamente `1.967,07 + 859,46`, os dois valores da linha Total impressa, e `1.967,07 − 859,46` dá o Líqüido impresso. Se algum valor tivesse sido lido errado ou trocado com a coluna Unidade, as duas contas não fechariam.
**Teste que passa não é o mesmo que coisa que funciona**
 
- Ao implementar o PDF ao lado da tabela, a primeira rodada passou em tudo: 200 na rota, iframe acessível, layout correto nos três tamanhos de tela. E o PDF não aparecia, porque o navegador headless usado no teste não tem visualizador de PDF embutido.
- Só ficou visível olhando a captura de tela em vez dos números. Com o PDF de fato renderizando, apareceu um segundo problema real de layout que o teste cego escondia.
- Registro isso porque é o tipo de falha que passaria pela revisão de código e pelos testes automatizados ao mesmo tempo.
**Testar a proteção, não só o caminho feliz**
 
- A rota do documento tem duas barreiras: o id precisa existir no dicionário, e o caminho resolvido precisa estar dentro de `uploads/`. Testar só por URL não distingue as duas, porque a primeira mascara a segunda.
- Injetei um id que resolve para um PDF real fora de `uploads/`: passou a primeira barreira e a segunda recusou. Sem esse teste, remover a proteção de caminho num refactor futuro não quebraria nenhum teste existente.
---
 
## Cite 3 decisões em que havia mais de uma resposta razoável. Por que escolheu essa?
 
1. Na extração do time-card-01, dois dias vinham repetindo o número da data em vez de omitir na linha de continuação, porque tinham mais batidas e ocupavam duas linhas. A documentação diz um item por linha do documento, mas escolhi juntar as duas linhas num registro só. Separar criaria dois registros com a mesma data e faria o aviso de data não sequencial disparar num dia que não tem problema.

2. Precisava saber como classificar o que era batida, e quais não eram para montar as colunas da planilha (Entrada 1, Saída 1, Entrada 2, Saída 2). Assim, analisei e apresentei a situação para o chat do Claude, onde ele me apresentou a opção de posição por linha, que eu já imaginava, e por coordenadas. Como não tenho experiencia em coordenadas de pdf, escolhi a opção por linhas, sabendo do risco. Foi mais seguro pra mim e funcionou. O risco é que a leitura por posição quebra se a ordem das colunas mudar, porque ela fixa que o primeiro horário é Jornada e o último é Qtde. A leitura por coordenada se adaptaria, porque localiza as colunas pelo cabeçalho.

3. Encarei um problema na extração do `payroll-2`. Na página 1 , a verba `IMPOSTO DE RENDA` aparece duas vezes com diferentes valores. Isso acontece porque a página tem dois blocos, `MÊS(recebimento mensal)` e `ACERTO(cobrança do mes anterior)`. Uma linha, com dois valores. Também apresentei para o chat do claude essa situação e expliquei que na documentação do projeto, está pedindo a label literal, entao ele me apresentou 3 saídas:

    1 - Duas linhas por página: cada bloco vira sua linha, com o rótulo `MÊS` ou `ACERTO`. Os dois valores cabem.

    2 - Renomear a verba: criar uma coluna `IMPOSTO DE RENDA (ACERTO)`. Cabe também, mas o nome da verba deixa de ser o que está impresso no papel, e o contrato pede o label literal.

    3 - Ignorar o bloco `ACERTO`: mais simples, mas joga dado fora de propósito.

Antes de apresentar para ele, eu não tinha muita certeza do que fazer, mas após apresentar, tive certeza de que a opção 1 se encaixaria melhor, porque é a única que não perde dado e nem mexe no label.
 
## O que na sua solução quebra primeiro em produção?
 
- O dicionário `transcricoes` vive em memória, então não persiste entre reinícios. Quando o processa se reinicia, tudo some. E como o deploy foi feito no Render com plano free, a aplicação dorme por inatividade. Então se o usuário fizer upload para extração de um pdf e sair para ir almoçar, nada fica salvo, e o front não sabe voltar a ela porque tambem nao salva nada.

## Onde você não confia no que entregou?

Quatro dos oito arquivos processam, e os outros quatro têm motivo identificado. Três dos quatro falham por layout que o extrator não reconhece; no `time-card-04` o próprio OCR não consegue ler.

- **`payroll-01`** — Layout. O texto nativo sai perfeito, o OCR nem entra. Mas não é um holerite: é uma ficha financeira plurianual, com vários meses por página. Nenhuma das âncoras que o extrator procura existe nele.

- **`payroll-04`** — Layout. O OCR lê bem, só 3,8% de palavras incertas. Mas o cabeçalho é `Proventos Descontos / Descrição Qtde Valor` e não tem coluna `Cod.`, que é o que o extrator procura.

- **`time-card-03`** — Layout. O OCR lê bem, 9,1% de incertas, as datas e batidas estão todas legíveis. Mas o cabeçalho usa abreviação: `Data Ent1 Sai1 Ent2 Sai2`, e o extrator procura `Entrada` e `Saida` por extenso.

- **`time-card-04`** — OCR. A imagem é degradada e pequena. 96% das palavras da página 1 ficam abaixo do limiar de confiança. Testar resolução maior piorou.

E no `time-card-04` o próprio diagnóstico do script erra: ele reporta que o texto saiu e o problema é layout, mas os caracteres que ele contou são quase todos os `?` da marcação de incerteza. O marcador conta como caractere e engana o teste de "tem texto útil".

O que me deixa desconfiado é que cada documento novo do desafio trouxe um formato diferente, e cada um precisou de ajuste no extrator. Não tenho como saber se um documento real que chegue depois vai cair num dos formatos que eu trato.