"""
Testa conectar(), salvar_concursos_novos(), buscar_nao_alertados(),
buscar_todos() e marcar_como_alertados() de banco.py contra um SQLite
descartavel (tmp_path do pytest), nunca contra concursos.db de verdade.
Roda com: python -m pytest tests/test_banco.py -v
"""

from datetime import date

import banco


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


def test_conectar_cria_a_tabela_concursos(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    linhas = conexao.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='concursos'"
    ).fetchall()
    conexao.close()
    assert len(linhas) == 1


def test_salvar_concursos_novos_insere_e_conta_certo(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    inseridos = banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])
    conexao.close()
    assert inseridos == 1


def test_salvar_concursos_novos_nao_duplica_pelo_link_edital(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])
    inseridos_de_novo = banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])
    total_no_banco = conexao.execute("SELECT COUNT(*) FROM concursos").fetchone()[0]
    conexao.close()
    assert inseridos_de_novo == 0
    assert total_no_banco == 1


def test_bootstrap_marca_ja_alertado_igual_a_um(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()], ja_alertado=1)
    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()
    assert ja_alertado == 1


def test_fluxo_normal_marca_ja_alertado_igual_a_zero_por_padrao(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])
    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()
    assert ja_alertado == 0


def test_buscar_nao_alertados_devolve_so_os_pendentes(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste(link_edital="https://.../pendente")])
    banco.salvar_concursos_novos(
        conexao, [_concurso_de_teste(link_edital="https://.../ja-alertado")], ja_alertado=1
    )

    pendentes = banco.buscar_nao_alertados(conexao)
    conexao.close()

    assert len(pendentes) == 1
    assert pendentes[0]["link_edital"] == "https://.../pendente"


def test_buscar_nao_alertados_reconstroi_data_prazo_como_date(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste(data_prazo=date(2026, 7, 23), data_incerta=False)])

    pendentes = banco.buscar_nao_alertados(conexao)
    conexao.close()

    assert pendentes[0]["data_prazo"] == date(2026, 7, 23)
    assert pendentes[0]["data_incerta"] is False


def test_buscar_todos_devolve_independente_de_ja_alertado(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste(link_edital="https://.../pendente")])
    banco.salvar_concursos_novos(
        conexao, [_concurso_de_teste(link_edital="https://.../ja-alertado")], ja_alertado=1
    )

    todos = banco.buscar_todos(conexao)
    conexao.close()

    assert len(todos) == 2


def test_marcar_como_alertados_atualiza_o_flag(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])
    id_do_concurso = conexao.execute("SELECT id FROM concursos").fetchone()[0]

    banco.marcar_como_alertados(conexao, [id_do_concurso])
    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()

    assert ja_alertado == 1


def test_marcar_como_alertados_com_lista_vazia_nao_faz_nada(tmp_path):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])

    banco.marcar_como_alertados(conexao, [])
    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()

    assert ja_alertado == 0
