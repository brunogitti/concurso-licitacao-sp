"""
Testa montar_corpo_html, enviar_email e enviar_resumo_diario de
enviar_resumo.py. Chamada externa real (SMTP) e sempre trocada por mock
via monkeypatch, nunca bate no Gmail de verdade.
Roda com: python -m pytest tests/test_enviar_resumo.py -v
"""

import smtplib
from datetime import date

import banco
import enviar_resumo


def _concurso_de_teste(**sobrescrever):
    base = {
        "id": 1,
        "orgao": "Prefeitura de Exemplo",
        "cidade": "Exemplo",
        "uf": "SP",
        "cargo": "Pregoeiro",
        "vagas": 1,
        "salario_ate": 5532.96,
        "nivel": "Superior",
        "data_prazo": date(2026, 7, 23),
        "data_incerta": False,
        "link_edital": "https://www.pciconcursos.com.br/noticias/exemplo",
        "slug_origem": "pregoeiro",
    }
    base.update(sobrescrever)
    return base


def test_corpo_html_lista_vazia_avisa_que_nao_teve_novidade():
    corpo = enviar_resumo.montar_corpo_html([])
    assert "Nenhum concurso novo" in corpo


def test_corpo_html_agrupa_por_uf_na_ordem_sp_mg_pr():
    concursos = [
        _concurso_de_teste(uf="PR", orgao="Prefeitura PR"),
        _concurso_de_teste(uf="SP", orgao="Prefeitura SP"),
        _concurso_de_teste(uf="MG", orgao="Prefeitura MG"),
    ]
    corpo = enviar_resumo.montar_corpo_html(concursos)
    posicao_sp = corpo.index("Prefeitura SP")
    posicao_mg = corpo.index("Prefeitura MG")
    posicao_pr = corpo.index("Prefeitura PR")
    assert posicao_sp < posicao_mg < posicao_pr


def test_corpo_html_escapa_texto_do_orgao():
    concursos = [_concurso_de_teste(orgao="Prefeitura & Cia <script>")]
    corpo = enviar_resumo.montar_corpo_html(concursos)
    assert "<script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_corpo_html_mostra_link_do_edital():
    concursos = [_concurso_de_teste(link_edital="https://www.pciconcursos.com.br/noticias/exemplo")]
    corpo = enviar_resumo.montar_corpo_html(concursos)
    assert "https://www.pciconcursos.com.br/noticias/exemplo" in corpo


def test_sem_credenciais_no_env_nao_tenta_enviar(monkeypatch):
    monkeypatch.delenv("GMAIL_USER", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    assert enviar_resumo.enviar_email("destino@exemplo.com", "assunto", "<p>corpo</p>") is False


class _SmtpFalso:
    def __init__(self, servidor, porta, timeout=None):
        self.servidor = servidor
        self.porta = porta

    def starttls(self):
        pass

    def login(self, usuario, senha):
        pass

    def send_message(self, mensagem):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_envio_com_sucesso_devolve_true(monkeypatch):
    monkeypatch.setenv("GMAIL_USER", "bot@exemplo.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "senha-de-app")
    monkeypatch.setattr(smtplib, "SMTP", _SmtpFalso)

    resultado = enviar_resumo.enviar_email("destino@exemplo.com", "assunto", "<p>corpo</p>")

    assert resultado is True


def test_falha_de_autenticacao_devolve_false_sem_travar(monkeypatch):
    class _SmtpComFalhaDeLogin(_SmtpFalso):
        def login(self, usuario, senha):
            raise smtplib.SMTPAuthenticationError(535, b"credenciais invalidas")

    monkeypatch.setenv("GMAIL_USER", "bot@exemplo.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "senha-errada")
    monkeypatch.setattr(smtplib, "SMTP", _SmtpComFalhaDeLogin)

    resultado = enviar_resumo.enviar_email("destino@exemplo.com", "assunto", "<p>corpo</p>")

    assert resultado is False


def test_enviar_resumo_diario_marca_como_alertado_so_se_enviou(tmp_path, monkeypatch):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])  # ja_alertado=0 por padrao

    monkeypatch.setattr(enviar_resumo, "enviar_email", lambda *args, **kwargs: True)
    enviado = enviar_resumo.enviar_resumo_diario(conexao, "destino@exemplo.com")

    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()

    assert enviado is True
    assert ja_alertado == 1


def test_enviar_resumo_diario_nao_marca_quando_envio_falha(tmp_path, monkeypatch):
    conexao = banco.conectar(str(tmp_path / "teste.db"))
    banco.salvar_concursos_novos(conexao, [_concurso_de_teste()])

    monkeypatch.setattr(enviar_resumo, "enviar_email", lambda *args, **kwargs: False)
    enviado = enviar_resumo.enviar_resumo_diario(conexao, "destino@exemplo.com")

    ja_alertado = conexao.execute("SELECT ja_alertado FROM concursos").fetchone()[0]
    conexao.close()

    assert enviado is False
    assert ja_alertado == 0
