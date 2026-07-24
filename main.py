"""
Ponto de entrada do concurso-licitacao-sp. Junta as camadas do projeto:
captura (capture_pciconcursos), normalizacao (normalize), filtro +
deduplicacao (filtro + banco) e entrega (enviar_resumo). E o script que o
GitHub Actions roda todo dia as 7h (ver .github/workflows/monitorar.yml).

Isso existe porque capture_pciconcursos.py traz o historico completo de
cada slug (as vezes ate 2011), nao so editais novos. Sem rodar o
--bootstrap uma vez, manualmente, antes de ligar o cron de verdade, a
primeira execucao automatica encontraria anos de concursos antigos como
"novos" e mandaria um resumo gigante e inutil. Depois do bootstrap, so
concurso com link_edital que ainda nao existe no banco conta como novo.
"""

import argparse
import logging

import banco
import capture_noticias
import capture_pciconcursos
import enviar_resumo
import filtro
import normalize

logger = logging.getLogger(__name__)


def configurar_logging():
    """Configura o formato padrao de log do projeto (uma vez, no inicio da execucao)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def capturar_todas_as_fontes():
    """Roda as duas fontes de captura e junta o resultado bruto (schema de capture_pciconcursos.py).

    capture_pciconcursos.py cobre /vagas/{slug}; capture_noticias.py cobre
    a lacuna dos concursos "Varios Cargos" nao indexados por cargo (ver
    docstring de capture_noticias.py). Falha na segunda fonte (rede,
    keywords.yaml sem termos_busca_texto, etc) e logada e a captura segue
    so com a primeira, nunca derruba o processo inteiro.
    """
    concursos = capture_pciconcursos.capturar()

    try:
        concursos = concursos + capture_noticias.capturar()
    except Exception as erro:  # noqa: BLE001 - falha na 2a fonte nao pode derrubar a 1a
        logger.error("Falha na captura por texto completo (capture_noticias), seguindo so com capture_pciconcursos: %s", erro)

    return concursos


def bootstrap():
    """Roda a captura inteira (as duas fontes) e salva tudo no banco ja marcado como alertado (ja_alertado=1), sem enviar e-mail.

    Uso: python main.py --bootstrap. Ver docstring do modulo pra entender
    por que esse passo existe antes de ligar o cron de verdade.
    """
    concursos_brutos = capturar_todas_as_fontes()
    concursos_normalizados = [normalize.normalizar(concurso) for concurso in concursos_brutos]

    conexao = banco.conectar()
    try:
        salvos = banco.salvar_concursos_novos(conexao, concursos_normalizados, ja_alertado=1)
    finally:
        conexao.close()

    print(f"Bootstrap concluido: {salvos} concurso(s) salvo(s) como ponto zero (nenhum e-mail enviado).")
    return salvos


def capturar_normalizar_e_filtrar():
    """Roda captura (as duas fontes) + normalizacao + filtro. Devolve so os concursos validos (schema comum de normalize.py).

    O filtro por UF (estados_monitorados) ja aconteceu dentro das duas
    funcoes de captura (ver keywords.yaml); aqui so falta aplicar
    filtro.concurso_esta_valido (data dentro da janela + sem texto de
    cancelamento).
    """
    concursos_brutos = capturar_todas_as_fontes()
    concursos_normalizados = [normalize.normalizar(concurso) for concurso in concursos_brutos]
    return [c for c in concursos_normalizados if filtro.concurso_esta_valido(c)]


def rodar_fluxo_diario(destinatario):
    """Fluxo normal: captura -> normaliza -> filtra -> salva os novos no banco -> envia o resumo do dia.

    destinatario pode ser None: nesse caso captura e salva normalmente,
    so nao manda e-mail nenhum (util pra rodar localmente sem gastar
    envio).
    """
    concursos_validos = capturar_normalizar_e_filtrar()

    conexao = banco.conectar()
    try:
        salvos = banco.salvar_concursos_novos(conexao, concursos_validos)
        logger.info("%d concurso(s) novo(s) salvo(s) no banco.", salvos)

        if destinatario:
            enviar_resumo.enviar_resumo_diario(conexao, destinatario)
    finally:
        conexao.close()


def enviar_resumo_de_teste(destinatario):
    """Modo --forcar-teste: le TODOS os concursos ja no banco (ignora ja_alertado), filtra os validos, monta e tenta enviar o e-mail.

    Nunca chama banco.marcar_como_alertados: serve pra ver como o
    e-mail fica sem "gastar" o dedup real do fluxo diario. Imprime o
    corpo HTML no terminal antes de tentar enviar, pra dar pra conferir
    mesmo se o envio de verdade falhar (ex: sem GMAIL_APP_PASSWORD
    configurado ainda).
    """
    conexao = banco.conectar()
    try:
        todos_do_banco = banco.buscar_todos(conexao)
    finally:
        conexao.close()

    concursos_validos = [c for c in todos_do_banco if filtro.concurso_esta_valido(c)]
    corpo_html = enviar_resumo.montar_corpo_html(concursos_validos)

    print(f"--- Modo de teste: {len(concursos_validos)} concurso(s) valido(s) de {len(todos_do_banco)} no banco ---")
    print(corpo_html)

    assunto = f"[TESTE] Concurso Licitação SP: {len(concursos_validos)} concurso(s) válido(s)"
    enviado = enviar_resumo.enviar_email(destinatario, assunto, corpo_html)
    print(f"Envio de teste: {'sucesso' if enviado else 'falhou (ver log acima) - nada foi marcado no banco'}")
    return corpo_html


def main():
    """Le os argumentos da linha de comando e decide qual modo rodar: --bootstrap, --forcar-teste ou o fluxo diario normal."""
    configurar_logging()

    parser = argparse.ArgumentParser(
        description="Monitor de concursos publicos de SP/MG/PR na area de licitacao/compras."
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help=(
            "Roda a captura inteira e salva tudo como ja alertado, sem enviar e-mail. "
            "Rodar uma vez, manualmente, antes de ligar o cron do GitHub Actions."
        ),
    )
    parser.add_argument(
        "--enviar-email",
        metavar="DESTINATARIO",
        default=None,
        help="Endereco que recebe o resumo diario. Sem essa opcao, o fluxo normal captura e salva mas nao envia nada.",
    )
    parser.add_argument(
        "--forcar-teste",
        action="store_true",
        help=(
            "Ignora ja_alertado e manda um resumo com os concursos validos que ja estao no banco, "
            "sem marcar nada como alertado. Precisa de --enviar-email. Serve pra conferir como o "
            "e-mail fica sem gastar o dedup real."
        ),
    )
    argumentos = parser.parse_args()

    if argumentos.forcar_teste and not argumentos.enviar_email:
        parser.error("--forcar-teste precisa de --enviar-email DESTINATARIO")

    if argumentos.bootstrap:
        bootstrap()
        return

    if argumentos.forcar_teste:
        enviar_resumo_de_teste(argumentos.enviar_email)
        return

    rodar_fluxo_diario(argumentos.enviar_email)


if __name__ == "__main__":
    main()
