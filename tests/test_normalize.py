"""
Testa normalizar() de normalize.py com exemplos reais de dict cru
devolvidos por capture_pciconcursos.py (slug "pregoeiro", concursos de
SP, captura completa feita no Passo 2).
Roda com: python -m pytest tests/test_normalize.py -v
"""

import datetime

import normalize


def _concurso_bruto_de_teste(**sobrescrever):
    # exemplo real: capture_pciconcursos.capturar(), slug "pregoeiro",
    # Prefeitura de Pontes Gestal
    base = {
        "orgao": "Prefeitura de Pontes Gestal",
        "uf": "SP",
        "vagas_e_salario": "13 vagas até R$ 11.181,50",
        "cargo": "Vários Cargos",
        "nivel": "Fundamental / Médio / Técnico / Superior",
        "data_bruta": "24/07/2025",
        "link_edital": (
            "https://www.pciconcursos.com.br/noticias/"
            "prefeitura-de-pontes-gestal-sp-publica-concurso-publico-com-salarios-de-ate-11-1-mil"
        ),
        "slug_origem": "pregoeiro",
    }
    base.update(sobrescrever)
    return base


def test_extrai_cidade_de_prefeitura_de_x():
    resultado = normalize.normalizar(_concurso_bruto_de_teste())
    assert resultado["cidade"] == "Pontes Gestal"


def test_camara_de_x_tambem_extrai_cidade():
    # exemplo real: slug "pregoeiro", Camara de Bofete
    bruto = _concurso_bruto_de_teste(orgao="Câmara de Bofete")
    resultado = normalize.normalizar(bruto)
    assert resultado["cidade"] == "Bofete"


def test_orgao_fora_do_padrao_deixa_cidade_none():
    # exemplo real: slug "pregoeiro", "FSA - Fundacao Santo Andre" nao
    # segue o padrao "Prefeitura/Camara de X", entao nao arrisca um parsing.
    bruto = _concurso_bruto_de_teste(orgao="FSA - Fundação Santo André")
    resultado = normalize.normalizar(bruto)
    assert resultado["cidade"] is None


def test_extrai_vagas_e_salario_do_texto_bruto():
    resultado = normalize.normalizar(_concurso_bruto_de_teste())
    assert resultado["vagas"] == 13
    assert resultado["salario_ate"] == 11181.50


def test_vaga_no_singular_extrai_contagem_um():
    # exemplo real: slug "pregoeiro", Camara de Bofete
    bruto = _concurso_bruto_de_teste(vagas_e_salario="1 vaga até R$ 5532,96")
    resultado = normalize.normalizar(bruto)
    assert resultado["vagas"] == 1
    assert resultado["salario_ate"] == 5532.96


def test_sem_contagem_numerica_de_vagas_fica_none():
    # exemplo real: slug "pregoeiro", FSA - Fundacao Santo Andre
    bruto = _concurso_bruto_de_teste(vagas_e_salario="Vagas até R$ 4402,50")
    resultado = normalize.normalizar(bruto)
    assert resultado["vagas"] is None
    assert resultado["salario_ate"] == 4402.50


def test_preserva_campos_repassados_direto():
    resultado = normalize.normalizar(_concurso_bruto_de_teste())
    assert resultado["orgao"] == "Prefeitura de Pontes Gestal"
    assert resultado["uf"] == "SP"
    assert resultado["cargo"] == "Vários Cargos"
    assert resultado["nivel"] == "Fundamental / Médio / Técnico / Superior"
    assert resultado["link_edital"].startswith("https://www.pciconcursos.com.br/noticias/")
    assert resultado["slug_origem"] == "pregoeiro"


def test_data_prazo_e_data_incerta_vem_do_parsear_data_bruta():
    resultado = normalize.normalizar(_concurso_bruto_de_teste())
    assert resultado["data_prazo"] == datetime.date(2025, 7, 24)
    assert resultado["data_incerta"] is False
