import { useEffect, useRef, useState } from 'react'
import Tabela from './Tabela'
import './App.css'

const TIPOS = [
  { valor: 'cartao-ponto', rotulo: 'Cartão de ponto' },
  { valor: 'holerite', rotulo: 'Holerite' },
]

const INTERVALO_POLLING = 2000

const FORMATOS = ['xlsx', 'csv', 'json']

/*
 * Tira o nome do arquivo do Content-Disposition que o backend manda, pra o
 * arquivo salvo ter o mesmo nome que teria num download direto.
 */
function nomeDoAnexo(cabecalho) {
  const casamento = /filename="?([^"]+)"?/.exec(cabecalho ?? '')
  return casamento?.[1] ?? null
}

function App() {
  const [arquivo, setArquivo] = useState(null)
  const [tipo, setTipo] = useState('cartao-ponto')
  const [id, setId] = useState(null)
  const [transcricao, setTranscricao] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [segundos, setSegundos] = useState(0)

  const [valueSalvo, setValueSalvo] = useState(null)
  const [salvando, setSalvando] = useState(false)
  const [baixando, setBaixando] = useState(false)
  const [salvou, setSalvou] = useState(false)
  const [formato, setFormato] = useState('xlsx')
  const [erroAcao, setErroAcao] = useState(null)

  const campoArquivo = useRef(null)

  const status = transcricao?.status ?? null
  const processando = Boolean(id) && status !== 'concluido' && status !== 'erro'

  /*
   * Comparação por referência basta: toda edição devolve um objeto novo, e o
   * valueSalvo guarda exatamente a referência que foi enviada no último PUT.
   */
  const pendente = Boolean(transcricao?.value) && transcricao.value !== valueSalvo

  /*
   * Polling: consulta a transcrição a cada 2s até o status parar de mudar.
   *
   * Depende de `status` e não do objeto inteiro: enquanto for "processando" a
   * string não muda, o efeito não reinicia e o intervalo sobrevive entre as
   * consultas. Quando vira "concluido" ou "erro", o efeito roda de novo, a
   * limpeza mata o intervalo antigo e ele retorna cedo sem criar outro.
   */
  useEffect(() => {
    if (!id) return
    if (status === 'concluido' || status === 'erro') return

    let cancelado = false

    async function consultar() {
      try {
        const resposta = await fetch(`/api/transcricoes/${id}`)

        if (!resposta.ok) {
          throw new Error(`A consulta falhou (HTTP ${resposta.status}).`)
        }

        const dados = await resposta.json()
        // O cancelado evita escrever estado depois que o efeito foi limpo,
        // que é o que acontece no duplo-monta do StrictMode.
        if (cancelado) return

        setTranscricao(dados)

        // O que acabou de chegar é, por definição, o que está no servidor:
        // marca como salvo pra não nascer com "alterações pendentes".
        if (dados.status === 'concluido') setValueSalvo(dados.value)
      } catch (causa) {
        if (!cancelado) setErro(causa.message)
      }
    }

    // Consulta já na primeira volta, sem esperar os 2s.
    consultar()
    const relogio = setInterval(consultar, INTERVALO_POLLING)

    return () => {
      cancelado = true
      clearInterval(relogio)
    }
  }, [id, status])

  // Contador de tempo. Um spinner sozinho fica igual estando o backend
  // trabalhando ou travado; o relógio andando mostra qual dos dois é.
  useEffect(() => {
    if (!processando) return

    const relogio = setInterval(() => setSegundos((atual) => atual + 1), 1000)
    return () => clearInterval(relogio)
  }, [processando])

  async function enviar(evento) {
    evento.preventDefault()

    if (!arquivo || enviando) return

    setEnviando(true)
    setErro(null)
    setTranscricao(null)
    setId(null)
    setSegundos(0)

    try {
      const corpo = new FormData()
      corpo.append('arquivo', arquivo)
      corpo.append('tipo', tipo)

      const resposta = await fetch('/api/transcricoes', {
        method: 'POST',
        body: corpo,
      })

      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        // O backend recusa tipo inválido e não-PDF com 400 e um detail
        // legível; mostra ele em vez de um "erro 400" seco.
        throw new Error(dados.detail ?? `O envio falhou (HTTP ${resposta.status}).`)
      }

      setId(dados.id)
    } catch (causa) {
      setErro(causa.message)
    } finally {
      setEnviando(false)
    }
  }

  /*
   * A edição de célula troca o value dentro da transcrição em memória. Só
   * chega aqui depois de "concluido", quando o polling já parou - senão a
   * próxima consulta sobrescreveria a correção com o que veio do servidor.
   */
  function editarValue(novoValue) {
    setTranscricao((atual) => ({ ...atual, value: novoValue }))
    setErroAcao(null)
  }

  /*
   * Devolve true quando o servidor ficou com o value atual. Quem chama usa
   * isso pra decidir se pode seguir - o download depende disso.
   */
  async function salvar() {
    const paraSalvar = transcricao.value

    setSalvando(true)
    setErroAcao(null)

    try {
      const resposta = await fetch(`/api/transcricoes/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value: paraSalvar }),
      })

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}))
        throw new Error(dados.detail ?? `Não foi possível salvar (HTTP ${resposta.status}).`)
      }

      /*
       * Guarda a referência que foi enviada, e não transcricao.value: se a
       * pessoa editou enquanto o PUT estava no ar, o pendente volta a ser
       * verdadeiro sozinho, que é o correto.
       */
      setValueSalvo(paraSalvar)
      setSalvou(true)
      return true
    } catch (causa) {
      setErroAcao(causa.message)
      return false
    } finally {
      setSalvando(false)
    }
  }

  async function baixar() {
    setErroAcao(null)

    /*
     * Salva antes de baixar quando há pendência. Se o PUT falhar, aborta: o
     * backend gera a planilha do value que ele tem, então baixar aqui
     * entregaria um arquivo sem as correções e sem ninguém perceber.
     */
    if (pendente && !(await salvar())) return

    setBaixando(true)

    try {
      const resposta = await fetch(
        `/api/transcricoes/${id}/planilha?formato=${formato}`,
      )

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => ({}))
        throw new Error(dados.detail ?? `O download falhou (HTTP ${resposta.status}).`)
      }

      /*
       * Vai por blob e link com download em vez de navegar pra URL: assim dá
       * pra checar o status antes e um erro do backend não substitui a página
       * por um JSON de erro numa aba.
       */
      const conteudo = await resposta.blob()
      const nome =
        nomeDoAnexo(resposta.headers.get('content-disposition')) ??
        `${transcricao.tipo}.${formato}`

      const endereco = URL.createObjectURL(conteudo)
      const link = document.createElement('a')
      link.href = endereco
      link.download = nome

      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(endereco)
    } catch (causa) {
      setErroAcao(causa.message)
    } finally {
      setBaixando(false)
    }
  }

  function recomecar() {
    setArquivo(null)
    setId(null)
    setTranscricao(null)
    setErro(null)
    setSegundos(0)
    setValueSalvo(null)
    setSalvou(false)
    setErroAcao(null)

    // O input de arquivo é não-controlado: limpar o estado não limpa o campo.
    if (campoArquivo.current) campoArquivo.current.value = ''
  }

  return (
    <main className="pagina">
      <header className="cabecalho">
        <h1>Transcrição de documentos</h1>
        <p>Envie um cartão de ponto ou holerite em PDF.</p>
      </header>

      <form className="formulario" onSubmit={enviar}>
        <div className="campo">
          <label htmlFor="arquivo">Arquivo PDF</label>
          <input
            id="arquivo"
            name="arquivo"
            type="file"
            accept="application/pdf,.pdf"
            ref={campoArquivo}
            disabled={enviando || processando}
            onChange={(evento) => setArquivo(evento.target.files?.[0] ?? null)}
          />
        </div>

        <fieldset className="campo" disabled={enviando || processando}>
          <legend>Tipo de documento</legend>

          {TIPOS.map(({ valor, rotulo }) => (
            <label key={valor} className="opcao">
              <input
                type="radio"
                name="tipo"
                value={valor}
                checked={tipo === valor}
                onChange={(evento) => setTipo(evento.target.value)}
              />
              {rotulo}
            </label>
          ))}
        </fieldset>

        <div className="acoes">
          <button type="submit" disabled={!arquivo || enviando || processando}>
            {enviando ? 'Enviando…' : 'Transcrever'}
          </button>

          {(transcricao || erro) && (
            <button type="button" className="secundario" onClick={recomecar}>
              Novo envio
            </button>
          )}
        </div>
      </form>

      {processando && (
        <div className="aviso processando" role="status" aria-live="polite">
          <span className="girando" aria-hidden="true" />
          <div>
            <strong>Processando o documento…</strong>
            <p className="detalhe">
              Consultando a cada 2 s · {segundos}s decorridos
            </p>
          </div>
        </div>
      )}

      {erro && (
        <div className="aviso falha" role="alert">
          <strong>Não deu certo</strong>
          <p className="detalhe">{erro}</p>
        </div>
      )}

      {status === 'erro' && (
        <div className="aviso falha" role="alert">
          <strong>A transcrição falhou</strong>
          <p className="detalhe">{transcricao.erro}</p>
        </div>
      )}

      {status === 'concluido' && (
        <section className="resultado">
          <h2>Resultado</h2>
          <p className="detalhe">
            {transcricao.tipo} · {transcricao.value.pages.length} páginas ·
            edite qualquer célula para corrigir
          </p>

          <Tabela
            tipo={transcricao.tipo}
            value={transcricao.value}
            aoEditar={editarValue}
          />

          <div className="barra-acoes">
            <button type="button" onClick={salvar} disabled={!pendente || salvando}>
              {salvando ? 'Salvando…' : 'Salvar correções'}
            </button>

            <div className="grupo-download">
              <label className="rotulo-formato" htmlFor="formato">
                Formato
              </label>
              <select
                id="formato"
                value={formato}
                disabled={salvando || baixando}
                onChange={(evento) => setFormato(evento.target.value)}
              >
                {FORMATOS.map((opcao) => (
                  <option key={opcao} value={opcao}>
                    {opcao}
                  </option>
                ))}
              </select>

              <button
                type="button"
                className="secundario"
                onClick={baixar}
                disabled={salvando || baixando}
              >
                {baixando ? 'Baixando…' : 'Baixar'}
              </button>
            </div>

            {/*
              O estado das correções fica sempre visível: pendente avisa que o
              arquivo sairia diferente da tela, e o salvo confirma o PUT. O
              "salvo" some sozinho na próxima edição, porque volta a pendente.
            */}
            {pendente ? (
              <span className="estado pendente">
                Alterações não salvas · o download salva antes
              </span>
            ) : (
              salvou && <span className="estado salvo">Correções salvas</span>
            )}
          </div>

          {erroAcao && (
            <div className="aviso falha" role="alert">
              <strong>Não deu certo</strong>
              <p className="detalhe">{erroAcao}</p>
            </div>
          )}
        </section>
      )}
    </main>
  )
}

export default App
