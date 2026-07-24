"""
Testa so que o esqueleto do projeto importa sem erro de sintaxe.
Roda com: python -m pytest tests/test_scaffold.py -v

Sera substituido por testes reais (um arquivo tests/test_<modulo>.py por
modulo, com helper local "_<coisa>_de_teste()", igual a convencao do Radar
NexLicit) conforme cada camada for implementada.
"""

import capture_api
import capture_noticias
import capture_pciconcursos
import normalize
import filtro
import banco
import enviar_resumo
import main


def test_modulos_do_scaffold_importam_sem_erro():
    assert capture_pciconcursos and capture_api and capture_noticias and normalize
    assert filtro and banco and enviar_resumo and main
