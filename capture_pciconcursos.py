"""
Este modulo faz scraping das paginas de vagas por cargo do PCI Concursos
(pciconcursos.com.br/vagas/{slug}). Para cada slug confirmado em
keywords.yaml, busca a pagina e extrai as entradas dos estados
monitorados (keywords.yaml -> estados_monitorados). Nao aplica filtro de
palavra-chave (o cargo ja vem pre-filtrado pelo proprio slug do PCI
Concursos) nem deduplica; so sabe buscar e devolver dados brutos, um dict
por concurso encontrado. normalize.py que traduz isso pro schema comum
depois.

Cada pagina /vagas/{slug} devolve o historico completo do cargo num unico
GET (sem paginacao, testado contra a fonte real: o slug "comprador" sozinho
tem 184 entradas indo ate 2008).

Scraping e fragil por natureza: quando o PCI Concursos mudar a estrutura
da pagina, o parser vai quebrar. Por isso cada slug e tratado
isoladamente: se um falhar (rede ou parsing), loga um erro claro e segue
pro proximo, sem derrubar a captura inteira.
"""

import logging

import requests
import yaml
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL_BASE = "https://www.pciconcursos.com.br/vagas/{slug}/"
CAMINHO_KEYWORDS_PADRAO = "keywords.yaml"
TIMEOUT_SEGUNDOS = 20
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; concurso-licitacao-sp/1.0)"}


def carregar_slugs_e_estados(caminho=CAMINHO_KEYWORDS_PADRAO):
    """Le keywords.yaml e devolve (slugs_cargo, estados_monitorados)."""
    with open(caminho, encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo)
    return config["slugs_cargo"], config["estados_monitorados"]


def buscar_pagina_do_slug(slug, url_base=URL_BASE):
    """Baixa o HTML da pagina /vagas/{slug} do PCI Concursos."""
    url = url_base.format(slug=slug)
    resposta = requests.get(url, headers=CABECALHOS, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    return resposta.text


def extrair_concursos_do_html(html, slug, estados_monitorados):
    """Faz o parsing do HTML de /vagas/{slug} e devolve so as entradas dos estados monitorados.

    Cada concurso vira um dict com os campos como aparecem na pagina:
    orgao, uf, vagas_e_salario, cargo, nivel, data_bruta, link_edital,
    slug_origem. O campo data_bruta pode vir so com a data (ex:
    "19/02/2024") ou com um rotulo na frente (ex: "Prorrogado ate
    19/05/2008"); separar isso e trabalho de normalize.py, nao daqui.
    """
    soup = BeautifulSoup(html, "lxml")
    entradas = soup.select("div#concursos div.ea")
    concursos = []

    for entrada in entradas:
        link = entrada.select_one("div.ca > a")
        uf_tag = entrada.select_one("div.cc")
        cd_tag = entrada.select_one("div.cd")
        ce_tag = entrada.select_one("div.ce")

        if not (link and uf_tag and cd_tag and ce_tag):
            logger.warning("Entrada com estrutura inesperada no slug %s, pulando.", slug)
            continue

        uf = uf_tag.get_text(strip=True)
        if uf not in estados_monitorados:
            continue

        campos_cd = list(cd_tag.stripped_strings)
        if len(campos_cd) < 3:
            logger.warning(
                "div.cd com menos campos que o esperado no slug %s (%s), pulando entrada.",
                slug,
                campos_cd,
            )
            continue

        concursos.append(
            {
                "orgao": link.get_text(strip=True),
                "uf": uf,
                "vagas_e_salario": campos_cd[0],
                "cargo": campos_cd[1],
                "nivel": campos_cd[2],
                "data_bruta": " ".join(ce_tag.stripped_strings),
                "link_edital": link["href"],
                "slug_origem": slug,
            }
        )

    return concursos


def capturar():
    """Funcao publica: le keywords.yaml, busca e extrai os concursos de todos os slugs configurados.

    Cada slug e tratado isoladamente: erro de rede ou de parsing em um
    slug e logado e o restante da captura continua normalmente.
    """
    slugs, estados_monitorados = carregar_slugs_e_estados()
    todos_concursos = []

    for slug in slugs:
        try:
            html = buscar_pagina_do_slug(slug)
            concursos_do_slug = extrair_concursos_do_html(html, slug, estados_monitorados)
            logger.info("Slug %s: %d concurso(s) em %s.", slug, len(concursos_do_slug), estados_monitorados)
            todos_concursos.extend(concursos_do_slug)
        except requests.RequestException as erro:
            logger.error("Falha de rede ao buscar o slug %s: %s", slug, erro)
        except Exception as erro:  # noqa: BLE001 - um slug ruim nao pode derrubar os outros
            logger.error("Falha ao processar o slug %s: %s", slug, erro)

    return todos_concursos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    resultado = capturar()
    print(f"Total: {len(resultado)} concurso(s) encontrados.")
    for concurso in resultado[:5]:
        print(concurso)
