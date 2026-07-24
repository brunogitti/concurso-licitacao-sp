"""
Este modulo monta e envia o resumo diario por e-mail via Gmail SMTP. Nao
sabe capturar, normalizar nem filtrar; so sabe montar o HTML a partir de
uma lista de concursos ja no schema comum (normalize.py) e mandar.
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from html import escape

from dotenv import load_dotenv

import banco

logger = logging.getLogger(__name__)

load_dotenv()

SERVIDOR_SMTP = "smtp.gmail.com"
PORTA_SMTP = 587
TIMEOUT_SEGUNDOS = 30

# Ordem de exibicao dos blocos por UF no e-mail. UFs fora dessa lista (nao
# deveria acontecer, ja que capture_pciconcursos.py so traz
# estados_monitorados) entram depois, em ordem alfabetica.
ORDEM_UF = ["SP", "MG", "PR"]


def _formatar_salario(salario_ate):
    """Formata um float pro padrao brasileiro (ex: 11181.5 -> "R$ 11.181,50")."""
    if salario_ate is None:
        return "não informado"
    texto = f"{salario_ate:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_prazo(concurso):
    """Formata a data extraida em normalize.py, ou avisa quando ela e incerta."""
    if concurso.get("data_incerta") or not concurso.get("data_prazo"):
        return "verificar no edital"
    return concurso["data_prazo"].strftime("%d/%m/%Y")


def _html_de_um_concurso(concurso):
    """Monta o bloco HTML de um concurso. Estilo sempre inline, porque muito cliente de e-mail ignora <style>."""
    orgao = escape(concurso.get("orgao") or "Órgão não identificado")
    cidade = concurso.get("cidade")
    uf = escape(concurso.get("uf") or "")
    local = f"{escape(cidade)}/{uf}" if cidade else uf
    cargo = escape(concurso.get("cargo") or "Cargo não especificado")
    vagas = concurso.get("vagas")
    vagas_texto = f"{vagas} vaga(s)" if vagas else "vagas não especificadas"
    salario = escape(_formatar_salario(concurso.get("salario_ate")))
    prazo = escape(_formatar_prazo(concurso))
    link = escape(concurso.get("link_edital") or "#")

    return (
        '<div style="margin-bottom:14px; padding:12px; border:1px solid #ddd; border-radius:6px;">'
        f'<div style="font-weight:bold; font-size:15px;">{orgao}'
        f' <span style="font-weight:normal; color:#555;">({local})</span></div>'
        f"<div>Cargo: {cargo}</div>"
        f"<div>{vagas_texto} — salário até {salario}</div>"
        f"<div>Data/prazo: {prazo}</div>"
        f'<div><a href="{link}" style="color:#205c98;">Ver notícia completa</a></div>'
        "</div>"
    )


def montar_corpo_html(concursos):
    """Monta o HTML do resumo diario a partir da lista de concursos normalizados e nao alertados.

    Agrupa por UF, na ordem SP -> MG -> PR. Lista vazia nao vira um
    e-mail vazio: monta um corpo simples avisando que nao houve concurso
    novo hoje, pra confirmar que o cron esta rodando de verdade mesmo em
    dias parados.
    """
    if not concursos:
        return (
            '<div style="font-family:Arial, sans-serif; padding:16px;">'
            "<h2>Concurso Licitação SP</h2>"
            "<p>Nenhum concurso novo na área de licitação/compras hoje.</p>"
            "</div>"
        )

    por_uf = {}
    for concurso in concursos:
        por_uf.setdefault(concurso.get("uf") or "?", []).append(concurso)

    ufs_ordenadas = [uf for uf in ORDEM_UF if uf in por_uf]
    ufs_ordenadas += sorted(uf for uf in por_uf if uf not in ORDEM_UF)

    blocos_uf = []
    for uf in ufs_ordenadas:
        itens_html = "".join(_html_de_um_concurso(c) for c in por_uf[uf])
        blocos_uf.append(
            f'<h3 style="border-bottom:2px solid #205c98; padding-bottom:4px;">'
            f"{escape(uf)} ({len(por_uf[uf])})</h3>{itens_html}"
        )

    return (
        '<div style="font-family:Arial, sans-serif; padding:16px; max-width:640px;">'
        f"<h2>Concurso Licitação SP — {len(concursos)} concurso(s) novo(s)</h2>"
        + "".join(blocos_uf)
        + "</div>"
    )


def enviar_email(destinatario, assunto, corpo_html):
    """Envia um e-mail HTML via SMTP do Gmail.

    Devolve True se enviou, False se falhou. Nunca deixa o erro subir:
    um problema de e-mail (senha errada no .env, Gmail fora do ar) nao
    pode travar o resto do processo, entao aqui a gente so registra um
    ERROR no log e devolve False.
    """
    usuario = os.getenv("GMAIL_USER")
    senha = os.getenv("GMAIL_APP_PASSWORD")
    if not usuario or not senha:
        logger.error("GMAIL_USER ou GMAIL_APP_PASSWORD nao configurados no .env, e-mail nao enviado.")
        return False

    mensagem = EmailMessage()
    mensagem["Subject"] = assunto
    mensagem["From"] = usuario
    mensagem["To"] = destinatario
    mensagem.set_content("Este e-mail requer um cliente que exiba HTML.")
    mensagem.add_alternative(corpo_html, subtype="html")

    try:
        with smtplib.SMTP(SERVIDOR_SMTP, PORTA_SMTP, timeout=TIMEOUT_SEGUNDOS) as servidor:
            servidor.starttls()
            servidor.login(usuario, senha)
            servidor.send_message(mensagem)
    except smtplib.SMTPAuthenticationError as erro:
        logger.error("Falha de autenticacao no Gmail: %s", erro)
        return False
    except (smtplib.SMTPException, OSError) as erro:
        logger.error("Falha ao enviar e-mail: %s", erro)
        return False

    logger.info("E-mail enviado para %s", destinatario)
    return True


def enviar_resumo_diario(conexao, destinatario):
    """Busca os concursos com ja_alertado=0, monta e envia o resumo, e marca como alertados so os enviados com sucesso."""
    concursos_pendentes = banco.buscar_nao_alertados(conexao)
    corpo_html = montar_corpo_html(concursos_pendentes)
    assunto = (
        f"Concurso Licitação SP: {len(concursos_pendentes)} concurso(s) novo(s)"
        if concursos_pendentes
        else "Concurso Licitação SP: nenhuma novidade hoje"
    )

    enviado = enviar_email(destinatario, assunto, corpo_html)
    if enviado and concursos_pendentes:
        ids_concursos = [concurso["id"] for concurso in concursos_pendentes]
        banco.marcar_como_alertados(conexao, ids_concursos)

    return enviado
