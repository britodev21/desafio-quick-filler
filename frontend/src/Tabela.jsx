import { contarDestaques, editarCelula, montarTabela } from './regrasTabela'

/*
 * Tabela editável. Não guarda estado: monta as linhas a partir do value a
 * cada render e devolve um value novo pelo aoEditar. Assim a transcrição em
 * memória continua sendo a única fonte da verdade, e os avisos são sempre
 * derivados do que está na tela naquele momento.
 */
function Tabela({ tipo, value, aoEditar }) {
  const tabela = montarTabela(tipo, value)
  const { colunas, linhas } = tabela
  const destaques = contarDestaques(linhas)

  function mudar(linha, indiceColuna, novoValor) {
    aoEditar(editarCelula(tipo, value, tabela, linha, indiceColuna, novoValor))
  }

  return (
    <div className="tabela-area">
      <div className="resumo">
        <span>
          {linhas.length} {linhas.length === 1 ? 'linha' : 'linhas'} ·{' '}
          {colunas.length} colunas
        </span>

        {destaques.vermelho > 0 && (
          <span className="etiqueta vermelho">
            {destaques.vermelho} fora de sequência
          </span>
        )}

        {destaques.amarelo > 0 && (
          <span className="etiqueta amarelo">
            {destaques.amarelo} a conferir
          </span>
        )}

        {destaques.vermelho === 0 && destaques.amarelo === 0 && (
          <span className="etiqueta">nenhum aviso</span>
        )}
      </div>

      <div className="rolagem">
        <table className="tabela">
          <thead>
            <tr>
              {colunas.map((coluna) => (
                <th key={coluna} scope="col">
                  {coluna}
                </th>
              ))}
              <th scope="col" className="coluna-aviso">
                Aviso
              </th>
            </tr>
          </thead>

          <tbody>
            {linhas.map((linha) => (
              <tr key={linha.chave} className={linha.destaque ?? undefined}>
                {linha.celulas.map((celula, indiceColuna) => (
                  <td key={colunas[indiceColuna]}>
                    <input
                      value={celula}
                      // A célula diz o que é e de qual linha, pra quem navega
                      // por teclado ou leitor de tela não se perder.
                      aria-label={`${colunas[indiceColuna]}, linha ${linha.celulas[0]}`}
                      onChange={(evento) =>
                        mudar(linha, indiceColuna, evento.target.value)
                      }
                    />
                  </td>
                ))}

                {/*
                  A cor sozinha não comunica: quem não distingue as cores, ou
                  usa leitor de tela, precisa do motivo escrito.
                */}
                <td className="coluna-aviso">{linha.motivos.join(' · ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default Tabela
