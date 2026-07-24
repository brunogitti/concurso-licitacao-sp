"""
Este modulo decide se um concurso ja normalizado ainda vale a pena
alertar: descarta os que estao com a data muito antiga ou que o proprio
texto indica terem sido cancelados. Nao sabe capturar nem normalizar, so
avalia um dict ja no schema comum de normalize.py.

Nao existe mais aqui o filtro por cargo em texto livre que o Radar
NexLicit tem (com --testar-termo pra calibrar termos amplos tipo
"administracao"): o cargo ja vem pre-filtrado pelo slug usado em
capture_pciconcursos.py (ver keywords.yaml -> slugs_cargo), entao nao ha
termo pra calibrar aqui.
"""

import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

PADRAO_DATA_COM_ANO = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Rodei o --bootstrap contra os 215 concursos reais de SP/MG/PR (Passo 3)
# e todos tinham data_prazo no passado - inclusive o mais recente, de
# "ontem", cujo titulo era "Prefeitura de Cajuru abre concurso publico".
# Isso confirma que data_bruta e majoritariamente a data em que a NOTICIA
# foi publicada no PCI Concursos, nao o prazo de inscricao. Por isso o
# corte aqui nao e "a data ja passou" (isso descartaria praticamente tudo,
# ja que qualquer noticia de ontem "ja passou") e sim "faz mais de
# DIAS_JANELA_VALIDADE dias que a ultima novidade sobre esse concurso foi
# publicada" - ainda descarta lixo antigo (ex: datas de 2011, 2015) sem
# jogar fora um concurso que acabou de ser divulgado.
DIAS_JANELA_VALIDADE = 90

# Termos observados de verdade nos dados reais capturados no Passo 2 (226
# concursos de SP/MG/PR) que indicam que o concurso nao vale mais alerta.
# "prorrogado" e "retificado" tambem aparecem bastante nos dados reais,
# mas NAO entram aqui: os dois significam que o concurso continua ativo
# (prazo estendido ou edital corrigido), o oposto de encerrado. So
# "cancel" (cancela/cancelado/cancelamento) apareceu associado a um
# encerramento de verdade na amostra real (Prefeitura de Coracao de Jesus
# - MG, "cancela provas de alguns cargos do concurso"). Se uma captura
# futura revelar outro termo real (ex: "suspenso"), adicionar aqui -
# nao adivinhar antes de ver o dado.
TERMOS_DE_ENCERRAMENTO = ["cancel"]

# Campos do concurso normalizado (ver normalize.py) onde faz sentido
# procurar por TERMOS_DE_ENCERRAMENTO. link_edital entra porque e a URL
# da propria noticia sobre aquele concurso (ex: ".../prefeitura-x-cancela-concurso"),
# nao um texto solto que poderia falar de outro certame.
CAMPOS_COM_TEXTO_DE_STATUS = ("cargo", "nivel", "link_edital", "orgao")


def parsear_data_bruta(data_bruta):
    """Extrai a data mais relevante de data_bruta. Devolve (data: date|None, data_incerta: bool).

    Os formatos reais observados na captura do Passo 2 sao: "DD/MM/AAAA"
    simples, "Prorrogado ate DD/MM/AAAA", "Reaberto ate DD/MM/AAAA",
    "Conferir periodo por cargo DD/MM/AAAA" e "Apenas dia DD/MM/AAAA".
    Tambem trata intervalos tipo "DD/MM a DD/MM/AAAA" (formato citado mas
    nao visto na amostra atual): pega a ultima data completa (com ano)
    encontrada no texto, que e a mais provavel de ser o fim do prazo.

    Quando nao ha nenhuma data completa (dia/mes/ano) reconhecivel no
    texto, ou a data encontrada nao existe no calendario (ex: 31/02),
    devolve (None, True) - melhor marcar como incerta do que adivinhar
    um valor errado.
    """
    if not data_bruta:
        return None, True

    correspondencias = PADRAO_DATA_COM_ANO.findall(data_bruta)
    if not correspondencias:
        return None, True

    dia, mes, ano = correspondencias[-1]
    try:
        data = date(int(ano), int(mes), int(dia))
    except ValueError:
        logger.warning("Data invalida em data_bruta=%r, marcando como incerta.", data_bruta)
        return None, True

    return data, False


def concurso_esta_valido(concurso):
    """Devolve False se a data esta velha demais (> DIAS_JANELA_VALIDADE dias) ou o texto indica encerramento obvio.

    Concurso com data_incerta=True passa direto no criterio de data (nao
    descarta por precaucao: e melhor mandar um alerta a mais do que
    perder uma oportunidade real por erro de parsing de data).
    """
    if not concurso.get("data_incerta", True):
        data_prazo = concurso.get("data_prazo")
        if data_prazo is not None:
            dias_desde_a_data = (date.today() - data_prazo).days
            if dias_desde_a_data > DIAS_JANELA_VALIDADE:
                return False

    texto = " ".join(
        str(concurso.get(campo) or "") for campo in CAMPOS_COM_TEXTO_DE_STATUS
    ).lower()
    if any(termo in texto for termo in TERMOS_DE_ENCERRAMENTO):
        return False

    return True
