"""Tu asistente de siniestros en Telegram.

En tu equipo:  uv run bot.py   (polling: el bot le pregunta a Telegram cada poco si hay mensajes)
En Render, el mismo archivo usa un webhook (Telegram avisa a tu URL cuando llega un mensaje):
se da cuenta solo porque Render define RENDER_EXTERNAL_URL.
"""

import hashlib
import os
import re

from pydantic_ai.conversation import Conversation
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import siniestros
from asistente import AUTOR, responder
from config import settings

TOKEN = settings.telegram_token.get_secret_value()

# Una conversación por chat: así el agente recuerda lo que cada persona ya contó.
# En Render Free se pierde al reiniciar el servicio; las denuncias guardadas quedan en SQLite.
CONVERSACIONES: dict[str, Conversation] = {}


def conversacion_de(chat: str) -> Conversation:
    """La conversación de ese chat, creada la primera vez."""
    return CONVERSACIONES.setdefault(chat, Conversation())


async def inicio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start: lo primero que manda Telegram. Dice el número de chat para añadirlo a la lista."""
    chat = str(update.effective_chat.id)
    if chat in settings.permitidos:
        await update.message.reply_text(
            "¡Hola! Soy el asistente de siniestros. Puedo recibir tu denuncia, consultar una "
            "denuncia registrada y mostrarte su seguimiento. Escríbeme qué ocurrió."
        )
    else:
        await update.message.reply_text(f"Tu número de chat es {chat}. Pídele al dueño del bot que lo añada.")


async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/reiniciar: olvida la conversación de este chat (no borra las denuncias guardadas)."""
    chat = str(update.effective_chat.id)
    CONVERSACIONES.pop(chat, None)
    await update.message.reply_text("Listo. Empezamos de nuevo; las denuncias registradas no se borran.")


async def autor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/autor: quién creó este asistente."""
    chat = str(update.effective_chat.id)
    if chat not in settings.permitidos:
        await update.message.reply_text(f"No autorizado. Tu chat es {chat}: pídele al dueño que lo añada.")
        return
    await update.message.reply_text(
        f"Fui creado por {AUTOR} como parte del proyecto agente_siniestro_ia, "
        "basado en la plantilla del curso de Alex Ojeda Copa."
    )


async def comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/comprobante SIN-2026-0001: envía el PDF del comprobante de recepción."""
    chat = str(update.effective_chat.id)
    if chat not in settings.permitidos:
        await update.message.reply_text(f"No autorizado. Tu chat es {chat}: pídele al dueño que lo añada.")
        return
    numero = " ".join(context.args or []).strip().upper()
    if not re.fullmatch(r"SIN-\d{4}-\d{4}", numero):
        await update.message.reply_text("Uso: /comprobante SIN-2026-0001")
        return
    resultado = siniestros.generar_comprobante(numero)
    if "error" in resultado:
        await update.message.reply_text(resultado["error"])
        return
    archivo = siniestros.GENERADOS / resultado["archivo"]
    await update.message.reply_document(document=archivo.read_bytes(), filename=archivo.name)
    await update.message.reply_text(
        "Comprobante de recepción. No es una aprobación del siniestro: el caso sigue en evaluación."
    )


async def mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = str(update.effective_chat.id)
    if chat not in settings.permitidos:  # se rechaza ANTES de llamar al modelo (y de gastar tu cuota)
        print(f"Chat no autorizado: {chat}", flush=True)
        await update.message.reply_text(f"No autorizado. Tu chat es {chat}: pídele al dueño que lo añada.")
        return
    try:
        respuesta = await responder(update.message.text, conversacion_de(chat))
    except Exception as error:  # cuota agotada (429), una API caída…: se avisa en vez de quedarse callado
        print("Error:", repr(error)[:300], flush=True)  # el detalle, en la terminal o en los Logs de Render
        respuesta = "Algo falló (el modelo o una herramienta). Intenta de nuevo en un minuto."
    await update.message.reply_text(respuesta[:4000])  # Telegram no acepta más de 4096 caracteres

    # Si el agente generó un PDF y lo menciona, se lo enviamos también como archivo.
    for nombre in dict.fromkeys(re.findall(r"[\w.-]+\.pdf", respuesta, flags=re.IGNORECASE)):
        archivo = siniestros.GENERADOS / nombre
        if archivo.is_file():
            await update.message.reply_document(document=archivo.read_bytes(), filename=archivo.name)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Falta TELEGRAM_TOKEN: créalo con @BotFather y ponlo en .env (o en Environment, en Render).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", inicio))
    app.add_handler(CommandHandler("reiniciar", reiniciar))
    app.add_handler(CommandHandler("autor", autor))
    app.add_handler(CommandHandler("comprobante", comprobante))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mensaje))

    permitidos = sorted(settings.permitidos) or "nadie"
    url = os.getenv("RENDER_EXTERNAL_URL")  # solo existe en Render
    if url:
        print(f"Webhook en {url}/telegram · permitidos: {permitidos}", flush=True)
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT", "10000")),  # Render dice en qué puerto escuchar
            url_path="telegram",
            webhook_url=f"{url}/telegram",
            # Telegram manda este secreto en cada aviso: así nadie más puede hacerse pasar por Telegram.
            # Sale de tu token, que solo tú tienes.
            secret_token=hashlib.sha256(TOKEN.encode()).hexdigest()[:32],
        )
    else:
        print(f"Bot en marcha (polling) · permitidos: {permitidos}. Ctrl+C para parar.", flush=True)
        app.run_polling()  # ojo: esto BORRA el webhook de Render (ver README, «Problemas frecuentes»)


if __name__ == "__main__":
    main()
