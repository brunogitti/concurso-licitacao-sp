"""
Testa extrair_uf_do_titulo, contem_cargo_monitorado e buscar_texto_completo
de capture_noticias.py. Os 3 casos reais que motivaram essa fonte de
captura (Meridiano, Potirendaba, Passos - concursos "Varios Cargos" com um
cargo de licitacao no meio de uma lista longa, nao indexados em
/vagas/{slug}) usam fixtures de HTML real baixado do PCI Concursos
(tests/fixtures/), nao dependem de rede.
Roda com: python -m pytest tests/test_capture_noticias.py -v
"""

from pathlib import Path

import capture_noticias

CAMINHO_FIXTURES = Path(__file__).parent / "fixtures"


class _RespostaFalsa:
    """Substitui requests.Response nos testes: so precisa de .text e .raise_for_status()."""

    def __init__(self, texto):
        self.text = texto

    def raise_for_status(self):
        pass


def _ler_fixture(nome_arquivo):
    return (CAMINHO_FIXTURES / nome_arquivo).read_text(encoding="utf-8")


def test_extrair_uf_do_titulo_pega_a_uf_logo_apos_o_orgao():
    # exemplo real: /noticias/sudeste/
    assert capture_noticias.extrair_uf_do_titulo("Câmara de Passos - MG abre concurso público com salários de até R$ 5.485,48") == "MG"


def test_extrair_uf_do_titulo_sem_espaco_antes_do_traco():
    # exemplo real: sigla colada no nome (sem espaco antes do "-")
    assert capture_noticias.extrair_uf_do_titulo("TCE-SP abre concurso com vagas para Auditor de Controle Externo") == "SP"


def test_extrair_uf_do_titulo_sem_padrao_devolve_none():
    # exemplo real: titulos de universidade (USP/UNESP/UERJ/UFMG) nao tem
    # " - UF" no titulo, e sao ~7% dos titulos da regiao Sudeste - devem
    # ser descartados, nao adivinhados.
    titulo = "USP abre vaga em concurso público para Professor Titular na Escola de Enfermagem"
    assert capture_noticias.extrair_uf_do_titulo(titulo) is None


def test_contem_cargo_monitorado_ignora_acento_e_maiusculas():
    encontrados = capture_noticias.contem_cargo_monitorado(
        "Vaga para AGENTE DE CONTRATACAO no municipio", ["Agente de Contratação"]
    )
    assert encontrados == ["Agente de Contratação"]


def test_contem_cargo_monitorado_nao_bate_termo_ausente():
    encontrados = capture_noticias.contem_cargo_monitorado(
        "Vagas para Motorista e Pedreiro", ["Pregoeiro", "Agente de Contratação"]
    )
    assert encontrados == []


def test_contem_cargo_monitorado_respeita_fronteira_de_palavra():
    # "Pregoeiro" nao deveria bater por acidente dentro de uma palavra maior
    encontrados = capture_noticias.contem_cargo_monitorado("ExPregoeiroAntigo", ["Pregoeiro"])
    assert encontrados == []


def test_buscar_texto_completo_extrai_o_corpo_do_artigo(monkeypatch):
    html = _ler_fixture("noticia_meridiano.html")
    monkeypatch.setattr(capture_noticias.requests, "get", lambda *args, **kwargs: _RespostaFalsa(html))

    texto = capture_noticias.buscar_texto_completo("https://www.pciconcursos.com.br/noticias/exemplo")

    assert "Meridiano" in texto
    assert "Agente de Contratação" in texto


def test_caso_real_meridiano_agente_de_contratacao_e_detectado(monkeypatch):
    # Caso 1 dos 3 que motivaram capture_noticias.py: concurso da
    # Prefeitura de Meridiano - SP com ~20 cargos, "Agente de Contratação"
    # no meio da lista, nao indexado em /vagas/agente-de-contratacao (nao
    # esta no banco capturado pelo Passo 2/3).
    html = _ler_fixture("noticia_meridiano.html")
    monkeypatch.setattr(capture_noticias.requests, "get", lambda *args, **kwargs: _RespostaFalsa(html))
    termos_reais = capture_noticias._carregar_config()["termos_busca_texto"]

    texto = capture_noticias.buscar_texto_completo("https://www.pciconcursos.com.br/noticias/exemplo")
    encontrados = capture_noticias.contem_cargo_monitorado(texto, termos_reais)

    assert "Agente de Contratação" in encontrados


def test_caso_real_potirendaba_assistente_de_licitacao_e_detectado(monkeypatch):
    # Caso 2: Prefeitura de Potirendaba - SP, ~35 cargos, "Assistente de
    # Licitação" no meio da lista.
    html = _ler_fixture("noticia_potirendaba.html")
    monkeypatch.setattr(capture_noticias.requests, "get", lambda *args, **kwargs: _RespostaFalsa(html))
    termos_reais = capture_noticias._carregar_config()["termos_busca_texto"]

    texto = capture_noticias.buscar_texto_completo("https://www.pciconcursos.com.br/noticias/exemplo")
    encontrados = capture_noticias.contem_cargo_monitorado(texto, termos_reais)

    assert "Assistente de Licitação" in encontrados


def test_caso_real_passos_oficial_de_compras_e_licitacao_e_detectado(monkeypatch):
    # Caso 3: Camara de Passos - MG, 10 cargos, "Oficial de Compras e
    # Licitação" no topo da lista mas o edital inteiro e "Varios Cargos".
    html = _ler_fixture("noticia_passos.html")
    monkeypatch.setattr(capture_noticias.requests, "get", lambda *args, **kwargs: _RespostaFalsa(html))
    termos_reais = capture_noticias._carregar_config()["termos_busca_texto"]

    texto = capture_noticias.buscar_texto_completo("https://www.pciconcursos.com.br/noticias/exemplo")
    encontrados = capture_noticias.contem_cargo_monitorado(texto, termos_reais)

    assert "Oficial de Compras e Licitação" in encontrados
