"""
Este modulo traduz o dict cru de capture_pciconcursos.py pro schema comum
usado no resto do projeto: orgao, cidade, uf, cargo, vagas, salario_ate,
nivel, data_prazo, data_incerta, link_edital, slug_origem. Nao sabe fazer
scraping nem decidir se um concurso ainda vale a pena alertar (isso e
trabalho de filtro.py); so sabe traduzir formato.
"""

import re

import filtro

# Reconhece "Prefeitura de X", "Prefeitura Municipal de X", "Camara de X"
# e "Camara Municipal de X". Qualquer outro formato de orgao (ex: "FSA -
# Fundacao Santo Andre") nao bate aqui de proposito: e melhor devolver
# cidade=None do que arriscar um parsing errado.
PADRAO_ORGAO_CIDADE = re.compile(r"^(?:Prefeitura|C[aâ]mara)(?: Municipal)? de (.+)$", re.IGNORECASE)

PADRAO_VAGAS = re.compile(r"(\d+)\s*vagas?", re.IGNORECASE)
PADRAO_SALARIO = re.compile(r"R\$\s*([\d.,]+)")


def extrair_cidade(orgao):
    """Tenta extrair a cidade do nome do orgao (ex: "Prefeitura de Holambra" -> "Holambra")."""
    if not orgao:
        return None
    correspondencia = PADRAO_ORGAO_CIDADE.match(orgao.strip())
    return correspondencia.group(1).strip() if correspondencia else None


def extrair_vagas_e_salario(vagas_e_salario_bruto):
    """Separa o texto "N vaga(s) ate R$ VALOR" em (vagas: int|None, salario_ate: float|None).

    "vagas" fica None quando o texto nao tem contagem numerica (ex:
    "Vagas ate R$ 4402,50", sem dizer quantas). "salario_ate" converte o
    formato brasileiro (ponto de milhar, virgula decimal) pra float.
    """
    texto = vagas_e_salario_bruto or ""

    vagas = None
    correspondencia_vagas = PADRAO_VAGAS.search(texto)
    if correspondencia_vagas:
        vagas = int(correspondencia_vagas.group(1))

    salario_ate = None
    correspondencia_salario = PADRAO_SALARIO.search(texto)
    if correspondencia_salario:
        valor_bruto = correspondencia_salario.group(1).replace(".", "").replace(",", ".")
        try:
            salario_ate = float(valor_bruto)
        except ValueError:
            salario_ate = None

    return vagas, salario_ate


def normalizar(concurso_bruto):
    """Traduz um dict cru de capture_pciconcursos.py pro schema comum do projeto."""
    vagas, salario_ate = extrair_vagas_e_salario(concurso_bruto.get("vagas_e_salario"))
    data_prazo, data_incerta = filtro.parsear_data_bruta(concurso_bruto.get("data_bruta", ""))

    return {
        "orgao": concurso_bruto.get("orgao"),
        "cidade": extrair_cidade(concurso_bruto.get("orgao")),
        "uf": concurso_bruto.get("uf"),
        "cargo": concurso_bruto.get("cargo"),
        "vagas": vagas,
        "salario_ate": salario_ate,
        "nivel": concurso_bruto.get("nivel"),
        "data_prazo": data_prazo,
        "data_incerta": data_incerta,
        "link_edital": concurso_bruto.get("link_edital"),
        "slug_origem": concurso_bruto.get("slug_origem"),
    }
