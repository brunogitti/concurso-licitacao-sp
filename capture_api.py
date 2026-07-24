"""
Este modulo busca concursos de SP na API nao-oficial concursos-api.deno.dev.
Ela nao tem SLA garantido (pode cair ou ficar desatualizada), por isso e
usada em conjunto com o scraping do PCI Concursos (capture_pciconcursos.py),
nunca sozinha: uma fonte cobre a ausencia da outra. So sabe fazer a
chamada HTTP e devolver os dados brutos como a API os entrega.
"""

URL_API = "https://concursos-api.deno.dev/sp"


def buscar_concursos_sp(url=URL_API):
    """Faz GET na API nao-oficial e devolve o JSON bruto (lista de concursos)."""
    # TODO (Passo 3): requisicao HTTP com timeout, tratar resposta nao-200 e JSON invalido.


def capturar():
    """Funcao publica: busca os concursos na API e devolve a lista pronta (ou vazia se a API falhar)."""
    # TODO (Passo 3): chama buscar_concursos_sp, nunca deixa erro da API derrubar o restante do fluxo.
