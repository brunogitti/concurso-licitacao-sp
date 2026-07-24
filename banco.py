"""
Este modulo so fala com o banco SQLite (concursos.db): cria a tabela se
nao existir e insere concursos novos sem duplicar (chave natural
link_edital, ja que nao existe um ID oficial unico como o
numero_controle_pncp do PNCP). Nao sabe nada sobre scraping, normalizacao
nem palavra-chave.

O schema abaixo bate com o dict que normalize.normalizar() devolve (nao
com o rascunho do Passo 1, escrito antes de conhecer os dados reais do
PCI Concursos): sem "situacao"/"inscricoes_ate" (nao existem como campos
estruturados na fonte), com "vagas"/"salario_ate"/"nivel"/"data_prazo"/
"data_incerta"/"slug_origem" no lugar.
"""

import sqlite3
from datetime import date, datetime, timezone

CAMINHO_BANCO_PADRAO = "concursos.db"

SCHEMA_CONCURSOS = """
CREATE TABLE IF NOT EXISTS concursos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orgao TEXT,
    cidade TEXT,
    uf TEXT NOT NULL,
    cargo TEXT,
    vagas INTEGER,
    salario_ate REAL,
    nivel TEXT,
    data_prazo TEXT,
    data_incerta INTEGER NOT NULL DEFAULT 0,
    link_edital TEXT UNIQUE,
    slug_origem TEXT,
    fonte TEXT NOT NULL DEFAULT 'pciconcursos',
    data_captura TEXT NOT NULL,
    ja_alertado INTEGER NOT NULL DEFAULT 0
)
"""


def conectar(caminho=CAMINHO_BANCO_PADRAO):
    """Abre a conexao com o SQLite e garante que a tabela concursos existe (CREATE TABLE IF NOT EXISTS)."""
    conexao = sqlite3.connect(caminho)
    conexao.execute(SCHEMA_CONCURSOS)
    conexao.commit()
    return conexao


def concurso_ja_existe(conexao, link_edital):
    """Devolve True se ja existe uma linha com esse link_edital no banco."""
    # TODO (Passo 4/5): SELECT 1 FROM concursos WHERE link_edital = ?.


def salvar_concursos_novos(conexao, concursos_filtrados, ja_alertado=0):
    """Insere os concursos que ainda nao existem no banco. Devolve quantos foram inseridos de verdade.

    Espera dicts no schema comum de normalize.normalizar() (orgao,
    cidade, uf, cargo, vagas, salario_ate, nivel, data_prazo,
    data_incerta, link_edital, slug_origem). link_edital e UNIQUE na
    tabela, entao INSERT OR IGNORE cuida do dedup sozinho: concurso que
    ja existe simplesmente nao gera uma linha nova (nao sobrescreve, nao
    da erro).

    ja_alertado controla o valor gravado: 0 no fluxo diario normal (ainda
    nao foi mandado por e-mail), 1 no --bootstrap (marca tudo como ja
    visto de proposito, pra nao alertar o historico inteiro na primeira
    execucao do cron).
    """
    agora = datetime.now(timezone.utc).isoformat()
    inseridos = 0

    for concurso in concursos_filtrados:
        data_prazo = concurso.get("data_prazo")
        cursor = conexao.execute(
            """
            INSERT OR IGNORE INTO concursos
                (orgao, cidade, uf, cargo, vagas, salario_ate, nivel,
                 data_prazo, data_incerta, link_edital, slug_origem,
                 data_captura, ja_alertado)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                concurso.get("orgao"),
                concurso.get("cidade"),
                concurso.get("uf"),
                concurso.get("cargo"),
                concurso.get("vagas"),
                concurso.get("salario_ate"),
                concurso.get("nivel"),
                data_prazo.isoformat() if data_prazo else None,
                int(bool(concurso.get("data_incerta"))),
                concurso.get("link_edital"),
                concurso.get("slug_origem"),
                agora,
                ja_alertado,
            ),
        )
        inseridos += cursor.rowcount

    conexao.commit()
    return inseridos


def _linha_para_concurso(linha):
    """Traduz uma linha do banco (sqlite3.Row) de volta pro schema comum de normalize.py."""
    concurso = dict(linha)
    if concurso.get("data_prazo"):
        concurso["data_prazo"] = date.fromisoformat(concurso["data_prazo"])
    concurso["data_incerta"] = bool(concurso.get("data_incerta"))
    return concurso


def buscar_nao_alertados(conexao):
    """Devolve os concursos com ja_alertado = 0, prontos para entrar no resumo do dia."""
    conexao.row_factory = sqlite3.Row
    linhas = conexao.execute("SELECT * FROM concursos WHERE ja_alertado = 0").fetchall()
    return [_linha_para_concurso(linha) for linha in linhas]


def buscar_todos(conexao):
    """Devolve todos os concursos do banco, independente de ja_alertado.

    Usado pelo modo --forcar-teste do main.py, pra gerar um resumo de
    exemplo sem depender do estado real de dedup (sem "gastar" o
    ja_alertado de verdade).
    """
    conexao.row_factory = sqlite3.Row
    linhas = conexao.execute("SELECT * FROM concursos").fetchall()
    return [_linha_para_concurso(linha) for linha in linhas]


def marcar_como_alertados(conexao, ids_concursos):
    """Depois que o e-mail sai com sucesso, marca esses concursos como ja_alertado = 1."""
    if not ids_concursos:
        return
    marcadores = ",".join("?" for _ in ids_concursos)
    conexao.execute(
        f"UPDATE concursos SET ja_alertado = 1 WHERE id IN ({marcadores})",
        list(ids_concursos),
    )
    conexao.commit()
