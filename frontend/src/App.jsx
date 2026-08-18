import { useEffect, useRef, useState } from 'react'
import Tabela from './Tabela'
import './App.css'

const TIPOS = [
  { valor: 'cartao-ponto', rotulo: 'Cartão de ponto' },
  { valor: 'holerite', rotulo: 'Holerite' },
]

const INTERVALO_POLLING = 2000

function App() {
  const [arquivo, setArquivo] = useState(null)
  const [tipo, setTipo] = useState('cartao-ponto')
  const [id, setId] = useState(null)
  const [transcricao, setTranscricao] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState(null)
  const [segundos, setSegundos] = useState(0)

  const campoArquivo = useRef(null)

  const status = transcricao?.status ?? null
  const processando = Boolean(id) && status !== 'concluido' && status !== 'erro'

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
        if (!cancelado) setTranscricao(dados)
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
  }

  function recomecar() {
    setArquivo(null)
    setId(null)
    setTranscricao(null)
    setErro(null)
    setSegundos(0)

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
        </section>
      )}
    </main>
  )
}

export default App
