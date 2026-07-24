"""
Testa parsear_data_bruta e concurso_esta_valido de filtro.py, usando
exemplos reais de data_bruta observados numa captura completa dos 11
slugs de keywords.yaml no Passo 2 (226 concursos de SP/MG/PR).
Roda com: python -m pytest tests/test_filtro.py -v
"""

from datetime import date

import filtro


def test_data_simples_sem_rotulo():
    # exemplo real: slug "pregoeiro", Camara de Bofete
    data, incerta = filtro.parsear_data_bruta("20/11/2025")
    assert data == date(2025, 11, 20)
    assert incerta is False


def test_prorrogado_ate_extrai_a_data_apos_o_rotulo():
    # exemplo real: slug "pregoeiro", Prefeitura de Nova Campina
    data, incerta = filtro.parsear_data_bruta("Prorrogado até 13/03/2020")
    assert data == date(2020, 3, 13)
    assert incerta is False


def test_reaberto_ate_extrai_a_data_apos_o_rotulo():
    # exemplo real observado na mesma captura
    data, incerta = filtro.parsear_data_bruta("Reaberto até 19/10/2011")
    assert data == date(2011, 10, 19)
    assert incerta is False


def test_conferir_periodo_por_cargo_extrai_a_data_apos_o_rotulo():
    # exemplo real observado na mesma captura
    data, incerta = filtro.parsear_data_bruta("Conferir período por cargo 05/04/2024")
    assert data == date(2024, 4, 5)
    assert incerta is False


def test_apenas_dia_extrai_a_data_apos_o_rotulo():
    # exemplo real observado na mesma captura
    data, incerta = filtro.parsear_data_bruta("Apenas dia 05/01/2018")
    assert data == date(2018, 1, 5)
    assert incerta is False


def test_intervalo_de_datas_pega_a_ultima_data_completa():
    # formato de intervalo (fim de prazo) citado como real mas nao visto
    # nesta captura especifica; pega a data mais a direita, que e o fim
    # do intervalo.
    data, incerta = filtro.parsear_data_bruta("17/09 a 16/10/2026")
    assert data == date(2026, 10, 16)
    assert incerta is False


def test_texto_sem_data_reconhecivel_fica_incerto():
    data, incerta = filtro.parsear_data_bruta("")
    assert data is None
    assert incerta is True


def test_data_invalida_fica_incerta_em_vez_de_estourar_erro():
    data, incerta = filtro.parsear_data_bruta("31/02/2024")
    assert data is None
    assert incerta is True


def _concurso_de_teste(**sobrescrever):
    base = {
        "orgao": "Prefeitura de Exemplo",
        "cidade": "Exemplo",
        "uf": "SP",
        "cargo": "Pregoeiro",
        "vagas": 1,
        "salario_ate": 5000.0,
        "nivel": "Superior",
        "data_prazo": None,
        "data_incerta": True,
        "link_edital": "https://www.pciconcursos.com.br/noticias/exemplo",
        "slug_origem": "pregoeiro",
    }
    base.update(sobrescrever)
    return base


def test_concurso_com_data_muito_antiga_e_invalido():
    # exemplo real: "Reaberto ate 19/10/2011", bem alem da janela de validade
    concurso = _concurso_de_teste(data_prazo=date(2011, 10, 19), data_incerta=False)
    assert filtro.concurso_esta_valido(concurso) is False


def test_concurso_com_prazo_no_futuro_e_valido():
    concurso = _concurso_de_teste(data_prazo=date(date.today().year + 1, 1, 1), data_incerta=False)
    assert filtro.concurso_esta_valido(concurso) is True


def test_concurso_com_data_de_ontem_permanece_valido():
    # caso real que motivou a janela de dias: o --bootstrap do Passo 3
    # encontrou concursos genuinamente abertos ("Prefeitura de Cajuru
    # abre concurso publico") com data_bruta de ontem. Descartar so
    # porque "ja passou" jogaria fora concurso que acabou de abrir, ja
    # que data_bruta normalmente e a data da noticia, nao o prazo final.
    ontem = date.fromordinal(date.today().toordinal() - 1)
    concurso = _concurso_de_teste(data_prazo=ontem, data_incerta=False)
    assert filtro.concurso_esta_valido(concurso) is True


def test_concurso_com_data_alem_da_janela_de_dias_e_invalido():
    alem_da_janela = date.fromordinal(date.today().toordinal() - filtro.DIAS_JANELA_VALIDADE - 1)
    concurso = _concurso_de_teste(data_prazo=alem_da_janela, data_incerta=False)
    assert filtro.concurso_esta_valido(concurso) is False


def test_concurso_dentro_da_janela_de_dias_e_valido():
    dentro_da_janela = date.fromordinal(date.today().toordinal() - filtro.DIAS_JANELA_VALIDADE + 1)
    concurso = _concurso_de_teste(data_prazo=dentro_da_janela, data_incerta=False)
    assert filtro.concurso_esta_valido(concurso) is True


def test_concurso_com_data_incerta_passa_mesmo_sem_data():
    concurso = _concurso_de_teste(data_prazo=None, data_incerta=True)
    assert filtro.concurso_esta_valido(concurso) is True


def test_concurso_com_texto_de_cancelamento_e_invalido():
    # caso isolado (data no futuro de proposito) pra provar que o check
    # de texto funciona sozinho, independente do check de data. O termo
    # "cancel" foi observado de verdade num link_edital real da captura
    # do Passo 2 (Prefeitura de Coracao de Jesus - MG, "cancela provas de
    # alguns cargos do concurso" - esse caso real ja tinha data de 2015,
    # entao ja seria descartado so pela data; aqui isolamos o texto).
    concurso = _concurso_de_teste(
        data_prazo=date(date.today().year + 1, 1, 1),
        data_incerta=False,
        link_edital=(
            "https://www.pciconcursos.com.br/noticias/"
            "prefeitura-de-coracao-de-jesus-mg-cancela-provas-de-alguns-cargos-do-concurso"
        ),
    )
    assert filtro.concurso_esta_valido(concurso) is False


def test_concurso_prorrogado_nao_e_tratado_como_cancelamento():
    # "prorrogado" aparece bastante nos dados reais e significa o
    # oposto de cancelado (prazo estendido); confirma que nao dispara o
    # filtro de encerramento.
    concurso = _concurso_de_teste(
        data_prazo=date(date.today().year + 1, 1, 1),
        data_incerta=False,
        link_edital="https://www.pciconcursos.com.br/noticias/prefeitura-de-nova-campina-sp-prorroga-concurso-publico",
    )
    assert filtro.concurso_esta_valido(concurso) is True
