"""
Este modulo cobre uma lacuna do capture_pciconcursos.py: concursos
"Varios Cargos" que citam um cargo de licitacao no meio de uma lista
longa e por isso nao ficam indexados em /vagas/{slug} (o PCI Concursos
parece so taguear um subconjunto dos cargos de cada edital, nao todos -
confirmado contra os casos reais de Meridiano, Potirendaba e Passos, que
citam "Agente de Contratacao"/"Assistente de Licitacao"/"Oficial de
Compras e Licitacao" no meio de 10 a 30 cargos e nao apareciam no banco
capturado pelo Passo 2).

A estrategia aqui e diferente: varrer as noticias das regioes Sudeste
(SP/RJ/MG/ES) e Sul (PR/RS/SC) e procurar as frases exatas de
keywords.yaml -> termos_busca_texto no texto completo de cada noticia,
independente de indexacao por cargo.

/noticias/sudeste/ e /noticias/sul/ nao mostram data de publicacao (a
listagem agrupa por orgao em ordem alfabetica, nao por data) e listam o
historico inteiro da regiao, nao so noticias recentes. Por isso so
processamos noticias com link_edital que ainda nao existe no banco (via
banco.concurso_ja_existe) ANTES de buscar o texto completo - a listagem
em si (2 requisicoes) roda toda vez, mas o texto completo (uma
requisicao por noticia) so pras genuinamente novas. Isso e uma excecao a
regra geral do projeto de "captura nao sabe de banco": aqui o dedup
precoce existe de proposito, pra nao gastar centenas de requisicoes
reprocessando noticias antigas a cada execucao.
"""

import logging
import re
import unicodedata

import requests
import yaml
from bs4 import BeautifulSoup

import banco

logger = logging.getLogger(__name__)

URLS_REGIOES = [
    "https://www.pciconcursos.com.br/noticias/sudeste/",
    "https://www.pciconcursos.com.br/noticias/sul/",
]
CAMINHO_KEYWORDS_PADRAO = "keywords.yaml"
TIMEOUT_SEGUNDOS = 20
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; concurso-licitacao-sp/1.0)"}

# Titulo real de noticia e "{ORGAO} - {UF} {resto da frase}" (ex: "Camara
# de Passos - MG abre concurso publico...") ou "{ORGAO}-{UF} {resto}"
# (ex: "TCE-SP abre concurso..."), a UF nunca fica sozinha no final. Pega
# o primeiro "- XX" (2 maiusculas) do titulo, que e sempre o marcador de
# estado logo apos o nome do orgao.
PADRAO_UF_NO_TITULO = re.compile(r"-\s*([A-Z]{2})\b")


def _normalizar_texto(texto):
    """minusculo + sem acento, pra "Licitação" bater com "licitacao"."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower()


def _carregar_config(caminho=CAMINHO_KEYWORDS_PADRAO):
    with open(caminho, encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)


def listar_noticias_recentes(url_regiao):
    """Baixa /noticias/sudeste/ ou /noticias/sul/ e devolve a lista de noticias listadas (titulo, link).

    Essa pagina nao mostra data de publicacao (agrupa por orgao em ordem
    alfabetica, nao por data), entao nao ha "data" pra devolver aqui - a
    unica forma confiavel de saber o que e novo e checar existencia no
    banco (ver capturar()).
    """
    resposta = requests.get(url_regiao, headers=CABECALHOS, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "lxml")

    noticias = []
    for link in soup.select("#pagina ul.concursos.link-d a[href]"):
        noticias.append({"titulo": link.get_text(strip=True), "link": link["href"]})
    return noticias


def buscar_texto_completo(url_noticia):
    """Baixa uma noticia individual e devolve o texto completo do corpo (article#noticia)."""
    resposta = requests.get(url_noticia, headers=CABECALHOS, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    soup = BeautifulSoup(resposta.text, "lxml")

    artigo = soup.select_one("article#noticia") or soup.select_one("article")
    if not artigo:
        logger.warning("Nao encontrei o corpo da noticia em %s, pulando.", url_noticia)
        return ""
    return artigo.get_text(separator="\n", strip=True)


def contem_cargo_monitorado(texto, termos_busca_texto):
    """Devolve a lista de termos_busca_texto que aparecem no texto (case-insensitive, sem acento)."""
    texto_normalizado = _normalizar_texto(texto or "")
    encontrados = []
    for termo in termos_busca_texto:
        padrao = r"\b" + re.escape(_normalizar_texto(termo)) + r"\b"
        if re.search(padrao, texto_normalizado):
            encontrados.append(termo)
    return encontrados


def extrair_uf_do_titulo(titulo):
    """Extrai a UF do titulo (ex: "Camara de Passos - MG abre..." -> "MG"). Devolve None se nao identificar com confianca."""
    correspondencia = PADRAO_UF_NO_TITULO.search(titulo or "")
    return correspondencia.group(1) if correspondencia else None


def _extrair_orgao_do_titulo(titulo, correspondencia_uf):
    """Usa a posicao do match de UF pra pegar so a parte do titulo antes dela (o nome do orgao)."""
    return titulo[: correspondencia_uf.start()].strip(" -")


def capturar():
    """Varre /noticias/sudeste/ e /noticias/sul/ atras de concurso com cargo de licitacao nao indexado em /vagas/{slug}.

    So busca o texto completo de noticias com link_edital que ainda nao
    existe no banco e cuja UF esteja em estados_monitorados (evita
    requisicao cara em noticia ja vista ou fora do escopo). Erro de rede
    numa regiao ou numa noticia individual e logado e a captura segue
    pras demais, igual capture_pciconcursos.py.
    """
    config = _carregar_config()
    termos_busca_texto = config["termos_busca_texto"]
    estados_monitorados = config["estados_monitorados"]

    conexao = banco.conectar()
    try:
        noticias = []
        for url_regiao in URLS_REGIOES:
            try:
                noticias.extend(listar_noticias_recentes(url_regiao))
            except requests.RequestException as erro:
                logger.error("Falha de rede ao listar noticias de %s: %s", url_regiao, erro)

        concursos = []
        for noticia in noticias:
            link = noticia["link"]
            titulo = noticia["titulo"]

            correspondencia_uf = PADRAO_UF_NO_TITULO.search(titulo)
            if not correspondencia_uf:
                continue
            uf = correspondencia_uf.group(1)
            if uf not in estados_monitorados:
                continue

            if banco.concurso_ja_existe(conexao, link):
                continue

            try:
                texto_completo = buscar_texto_completo(link)
            except requests.RequestException as erro:
                logger.error("Falha de rede ao buscar o texto de %s: %s", link, erro)
                continue

            termos_encontrados = contem_cargo_monitorado(texto_completo, termos_busca_texto)
            if not termos_encontrados:
                continue

            concursos.append(
                {
                    "orgao": _extrair_orgao_do_titulo(titulo, correspondencia_uf),
                    "uf": uf,
                    "vagas_e_salario": "",
                    "cargo": ", ".join(termos_encontrados),
                    "nivel": "",
                    "data_bruta": "",
                    "link_edital": link,
                    "slug_origem": None,
                    "fonte_deteccao": "texto_completo",
                }
            )
    finally:
        conexao.close()

    logger.info(
        "capture_noticias: %d concurso(s) com cargo de licitacao encontrado no texto completo.", len(concursos)
    )
    return concursos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    resultado = capturar()
    print(f"Total: {len(resultado)} concurso(s) encontrados via texto completo.")
    for concurso in resultado:
        print(concurso)
