/*
 * Visualizador do PDF original, pra conferir a transcrição contra o
 * documento sem trocar de janela.
 *
 * Usa o leitor de PDF do próprio navegador num iframe, em vez de trazer uma
 * biblioteca de renderização: o que a tela precisa é mostrar o documento, e o
 * leitor nativo já vem com zoom, busca e paginação prontos.
 */
function Documento({ id }) {
  const endereco = `/api/transcricoes/${id}/documento`

  return (
    <div className="documento-area">
      <div className="documento-topo">
        <span className="detalhe">PDF original</span>

        {/*
          Escape para quando o navegador não abre PDF embutido - alguns
          bloqueiam por configuração, e aí o iframe fica em branco sem avisar
          ninguém. O link sempre funciona.
        */}
        <a href={endereco} target="_blank" rel="noreferrer">
          Abrir em nova aba
        </a>
      </div>

      <iframe
        className="documento-visor"
        src={endereco}
        title="PDF original da transcrição"
      />
    </div>
  )
}

export default Documento
