/*
 * Regras da tabela editável. São as mesmas do backend/planilha.py: as colunas,
 * a ordem das linhas e a derivação dos avisos precisam bater com a planilha
 * que a rota de download gera, senão a tela mostra uma coisa e o arquivo
 * baixado mostra outra.
 *
 * Nada aqui toca em React: são funções puras que recebem o value e devolvem
 * um value novo. O estado vive no componente.
 */

const MILISSEGUNDOS_POR_DIA = 86400000

// ---------------------------------------------------------------- leitura

/*
 * "01/07/2012" -> número do dia desde a época. Devolve null quando não dá pra
 * ler, que é o caso de uma data com "?" de caractere ilegível.
 *
 * Conta em UTC de propósito: com data local, um dia de mudança de horário de
 * verão tem 23 ou 25 horas e a diferença entre dias vizinhos deixaria de ser
 * exatamente 1.
 */
export function numeroDoDia(dataBruta) {
  const casamento = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String(dataBruta ?? '').trim())
  if (!casamento) return null

  const [, dia, mes, ano] = casamento.map(Number)
  const instante = Date.UTC(ano, mes - 1, dia)

  // Rejeita 31/02 e afins, que o Date.UTC aceita virando 02/03.
  const conferencia = new Date(instante)
  if (
    conferencia.getUTCDate() !== dia ||
    conferencia.getUTCMonth() !== mes - 1 ||
    conferencia.getUTCFullYear() !== ano
  ) {
    return null
  }

  return instante / MILISSEGUNDOS_POR_DIA
}

/*
 * Competência em meses absolutos (ano * 12 + mês), pra dezembro -> janeiro
 * contar como consecutivo. null quando não dá pra ler.
 */
export function numeroDaCompetencia(mes, ano) {
  const mesLimpo = String(mes ?? '').trim()
  const anoLimpo = String(ano ?? '').trim()

  if (!/^\d{1,2}$/.test(mesLimpo) || !/^\d{4}$/.test(anoLimpo)) return null

  return Number(anoLimpo) * 12 + Number(mesLimpo)
}

function temIncerteza(celulas) {
  return celulas.some((celula) => String(celula ?? '').includes('?'))
}

function vazia(celula) {
  return String(celula ?? '').trim() === ''
}

// ------------------------------------------------------- cartão de ponto

function tabelaCartaoPonto(value) {
  const dias = []

  value.pages.forEach((pagina, iPagina) => {
    pagina.days.forEach((dia, iDia) => {
      dias.push({ iPagina, iDia, dia })
    })
  })

  // Tantos pares quantos o dia com mais batidas exigir. Arredonda pra cima:
  // um dia com 1 batida ainda ocupa um par inteiro, com a saída vazia.
  const maximo = dias.reduce((maior, { dia }) => Math.max(maior, dia.punches.length), 0)
  const pares = Math.ceil(maximo / 2)

  const colunas = ['Data']
  for (let numero = 1; numero <= pares; numero += 1) {
    colunas.push(`Entrada ${numero}`, `Saída ${numero}`)
  }

  let ultimoDia = null

  const linhas = dias.map(({ iPagina, iDia, dia }) => {
    const celulas = [dia.date_raw ?? '']
    for (let i = 0; i < pares * 2; i += 1) {
      celulas.push(dia.punches[i]?.time_hhmm ?? '')
    }

    /*
     * Avisos derivados do que está na tela, não de campo do JSON. Conta só as
     * batidas preenchidas: uma célula vazia criada pra edição não pode virar
     * "batida ímpar".
     */
    const preenchidas = celulas.slice(1).filter((celula) => !vazia(celula))
    const impar = preenchidas.length % 2 !== 0
    const incerto = temIncerteza(celulas)

    const numero = numeroDoDia(celulas[0])
    let naoSequencial = false

    // Data ilegível não quebra a cadeia: a próxima legível é comparada com a
    // última legível, não com ela.
    if (numero !== null && ultimoDia !== null) {
      naoSequencial = numero - ultimoDia !== 1
    }
    if (numero !== null) ultimoDia = numero

    const motivos = []
    if (naoSequencial) motivos.push('Data não sequencial')
    if (impar) motivos.push('Batidas ímpares')
    if (incerto) motivos.push('Leitura incerta')

    return {
      chave: `${iPagina}-${iDia}`,
      caminho: { iPagina, iDia },
      celulas,
      destaque: naoSequencial ? 'vermelho' : impar || incerto ? 'amarelo' : null,
      motivos,
    }
  })

  return { colunas, linhas }
}

function comDia(value, iPagina, iDia, alterar) {
  return {
    ...value,
    pages: value.pages.map((pagina, i) =>
      i !== iPagina
        ? pagina
        : {
            ...pagina,
            days: pagina.days.map((dia, j) => (j !== iDia ? dia : alterar(dia))),
          },
    ),
  }
}

function editarCartaoPonto(value, tabela, linha, indiceColuna, novoValor) {
  const { iPagina, iDia } = linha.caminho

  return comDia(value, iPagina, iDia, (dia) => {
    if (indiceColuna === 0) return { ...dia, date_raw: novoValor }

    const iBatida = indiceColuna - 1
    const punches = [...dia.punches]

    /*
     * Preenche os buracos até a coluna editada. É o que deixa completar a
     * saída que faltava num dia de batida ímpar: a célula está vazia porque a
     * batida não existe no JSON, e digitar nela cria a batida.
     */
    while (punches.length <= iBatida) {
      punches.push({
        kind: punches.length % 2 === 0 ? 'IN' : 'OUT',
        time_raw: '',
        time_hhmm: '',
      })
    }

    /*
     * Só o time_hhmm muda. O time_raw guarda o que estava impresso no PDF, e
     * é a divergência entre os dois que deixa auditar a correção depois.
     */
    punches[iBatida] = { ...punches[iBatida], time_hhmm: novoValor }

    return { ...dia, punches }
  })
}

// -------------------------------------------------------------- holerite

const COLUNAS_FIXAS_HOLERITE = ['Pág.', 'Mês', 'Ano']

export function colunasDeVerbas(value) {
  const vistas = new Set()
  const verbas = []

  value.pages.forEach((pagina) => {
    pagina.fields.forEach(({ label }) => {
      if (vistas.has(label)) return
      vistas.add(label)
      verbas.push(label)
    })
  })

  return verbas
}

function tabelaHolerite(value) {
  const verbas = colunasDeVerbas(value)
  const colunas = [...COLUNAS_FIXAS_HOLERITE, ...verbas]

  let ultimaCompetencia = null

  const linhas = value.pages.map((pagina, iPagina) => {
    const porVerba = new Map()
    pagina.fields.forEach((field) => {
      // Primeira aparição vence, igual à planilha.
      if (!porVerba.has(field.label)) porVerba.set(field.label, field.value)
    })

    const celulas = [
      pagina.page ?? '',
      pagina.month ?? '',
      pagina.year ?? '',
      ...verbas.map((verba) => porVerba.get(verba) ?? ''),
    ]

    const semVerba = celulas.slice(COLUNAS_FIXAS_HOLERITE.length).every(vazia)
    const incerto = temIncerteza(celulas)

    const competencia = numeroDaCompetencia(celulas[1], celulas[2])
    let naoSequencial = false

    if (competencia !== null && ultimaCompetencia !== null) {
      naoSequencial = competencia - ultimaCompetencia !== 1
    }
    if (competencia !== null) ultimaCompetencia = competencia

    const motivos = []
    if (naoSequencial) motivos.push('Mês não sequencial')
    if (semVerba) motivos.push('Página vazia')
    if (incerto) motivos.push('Leitura incerta')

    return {
      chave: String(iPagina),
      caminho: { iPagina },
      celulas,
      destaque: naoSequencial ? 'vermelho' : semVerba || incerto ? 'amarelo' : null,
      motivos,
    }
  })

  return { colunas, linhas }
}

function comPagina(value, iPagina, alterar) {
  return {
    ...value,
    pages: value.pages.map((pagina, i) => (i !== iPagina ? pagina : alterar(pagina))),
  }
}

function editarHolerite(value, tabela, linha, indiceColuna, novoValor) {
  const { iPagina } = linha.caminho

  return comPagina(value, iPagina, (pagina) => {
    if (indiceColuna === 0) {
      // page é número no contrato; só converte quando o que foi digitado é
      // mesmo um número, senão guarda o texto e o erro fica visível.
      const numero = Number(novoValor)
      const ehNumero = novoValor.trim() !== '' && Number.isFinite(numero)
      return { ...pagina, page: ehNumero ? numero : novoValor }
    }

    // month e year ficam string, como o contrato pede: virar número comeria o
    // zero à esquerda de "01".
    if (indiceColuna === 1) return { ...pagina, month: novoValor }
    if (indiceColuna === 2) return { ...pagina, year: novoValor }

    const label = tabela.colunas[indiceColuna]
    const indice = pagina.fields.findIndex((field) => field.label === label)

    if (indice >= 0) {
      const fields = [...pagina.fields]
      fields[indice] = { ...fields[indice], value: novoValor }
      return { ...pagina, fields }
    }

    // Célula vazia numa verba que não existe nesta página: só cria a verba se
    // o usuário digitou alguma coisa.
    if (novoValor.trim() === '') return pagina

    return {
      ...pagina,
      fields: [...pagina.fields, { code: '', label, reference: '', value: novoValor }],
    }
  })
}

// ---------------------------------------------------------------- fachada

export function montarTabela(tipo, value) {
  return tipo === 'holerite' ? tabelaHolerite(value) : tabelaCartaoPonto(value)
}

export function editarCelula(tipo, value, tabela, linha, indiceColuna, novoValor) {
  return tipo === 'holerite'
    ? editarHolerite(value, tabela, linha, indiceColuna, novoValor)
    : editarCartaoPonto(value, tabela, linha, indiceColuna, novoValor)
}

export function contarDestaques(linhas) {
  return {
    vermelho: linhas.filter((linha) => linha.destaque === 'vermelho').length,
    amarelo: linhas.filter((linha) => linha.destaque === 'amarelo').length,
  }
}
