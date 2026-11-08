"""Demo web pública del agente (extra opcional, separado del bot de Telegram).

En tu equipo:  uv run uvicorn web:app --reload   →   http://127.0.0.1:8000

Es una página de chat sencilla y un endpoint público con límites de uso, pensado para
que otras personas prueben el asistente con datos ficticios. No uses datos personales
reales en una demo pública.
"""

import time
from collections import defaultdict, deque
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from pydantic_ai.conversation import Conversation

from asistente import responder

app = FastAPI(title="Agente de siniestros - demo web")

CONVERSACIONES: dict[str, Conversation] = {}  # una por sesión del navegador
USOS: dict[str, deque[float]] = defaultdict(deque)  # mensajes por minuto y por IP
USO_DIA: dict[str, tuple[date, int]] = {}  # mensajes por día y por IP

LIMITE_POR_MINUTO = 8
LIMITE_POR_DIA = 80
LIMITE_GLOBAL_DIA = 300  # tope total: protege la cuota aunque cambien de IP
LIMITE_MENSAJES_SESION = 30
MAX_SESIONES = 500
MAX_IPS = 2000

USO_GLOBAL: dict[str, object] = {"dia": date.today(), "cuenta": 0}


class Pedido(BaseModel):
    """Lo que manda la página. Pydantic valida antes de llamar al modelo."""

    sesion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    mensaje: str = Field(min_length=1, max_length=1000)


class Sesion(BaseModel):
    sesion: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class Respuesta(BaseModel):
    texto: str


def _ip(request: Request) -> str:
    """La IP real, detrás del proxy de Render (X-Forwarded-For) o la del cliente."""
    reenviada = request.headers.get("x-forwarded-for", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else "desconocida"


def _limitar(ip: str) -> None:
    """Límites sencillos en memoria: por minuto, por día y por cantidad de sesiones."""
    ahora = time.monotonic()
    cola = USOS[ip]
    while cola and ahora - cola[0] > 60:
        cola.popleft()
    if len(cola) >= LIMITE_POR_MINUTO:
        raise HTTPException(429, "Demasiados mensajes seguidos. Espera un minuto y vuelve a intentar.")

    hoy = date.today()
    dia, cuenta = USO_DIA.get(ip, (hoy, 0))
    if dia != hoy:
        cuenta = 0
    if cuenta >= LIMITE_POR_DIA:
        raise HTTPException(429, "Esta IP llegó al límite diario de la demo. Vuelve mañana.")

    if USO_GLOBAL["dia"] != hoy:
        USO_GLOBAL["dia"] = hoy
        USO_GLOBAL["cuenta"] = 0
    if int(USO_GLOBAL["cuenta"]) >= LIMITE_GLOBAL_DIA:
        raise HTTPException(429, "La demo alcanzó su límite diario global. Intenta mañana.")

    cola.append(ahora)
    USO_DIA[ip] = (hoy, cuenta + 1)
    USO_GLOBAL["cuenta"] = int(USO_GLOBAL["cuenta"]) + 1

    # La demo es pequeña: si se acumulan muchas IP, se limpia la memoria.
    if len(USOS) > MAX_IPS:
        USOS.clear()
        USO_DIA.clear()


def _conversacion(sesion: str) -> Conversation:
    conversacion = CONVERSACIONES.get(sesion)
    if conversacion is None:
        if len(CONVERSACIONES) >= MAX_SESIONES:
            raise HTTPException(429, "La demo está llena en este momento. Intenta más tarde.")
        conversacion = CONVERSACIONES[sesion] = Conversation()
    if len(conversacion.messages) >= LIMITE_MENSAJES_SESION:
        raise HTTPException(429, "Esta sesión llegó al límite. Pulsa «Reiniciar conversación».")
    return conversacion


@app.get("/salud")
async def salud() -> dict:
    """Para comprobar que el servicio está despierto."""
    return {"ok": True}


@app.post("/demo/chat", response_model=Respuesta)
async def demo_chat(pedido: Pedido, request: Request) -> Respuesta:
    """Responde un mensaje. Es público, pero con límites para cuidar la cuota del modelo."""
    _limitar(_ip(request))
    conversacion = _conversacion(pedido.sesion)
    try:
        texto = await responder(pedido.mensaje, conversacion)
    except Exception as error:  # cuota agotada, modelo caído…
        print("Error en la demo:", repr(error)[:300], flush=True)
        raise HTTPException(503, "El modelo no está disponible en este momento. Intenta de nuevo en un minuto.")
    return Respuesta(texto=texto)


@app.post("/demo/reiniciar")
async def demo_reiniciar(pedido: Sesion) -> dict:
    """Olvida la conversación de esa sesión (no borra las denuncias guardadas)."""
    CONVERSACIONES.pop(pedido.sesion, None)
    return {"ok": True}


HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agente de siniestros · demo</title>
  <style>
    :root { color-scheme: light dark; --fondo: #f4f6f8; --panel: #ffffff; --texto: #1d2733;
            --suave: #5b6b7c; --borde: #d7dee6; --marca: #0b5cad; --burbuja: #eaf2fb; }
    @media (prefers-color-scheme: dark) {
      :root { --fondo: #10151b; --panel: #18212b; --texto: #e6edf3; --suave: #9fb0c0;
              --borde: #2b3947; --marca: #6cb6ff; --burbuja: #223140; }
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
           background: var(--fondo); color: var(--texto); }
    .marco { max-width: 760px; margin: 0 auto; padding: 16px; }
    header { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
    h1 { font-size: 1.25rem; margin: 0; }
    .autor { color: var(--suave); font-size: .85rem; }
    .aviso { border: 1px solid var(--borde); border-left: 4px solid #d69e2e; background: var(--panel);
             padding: 10px 12px; border-radius: 8px; font-size: .85rem; color: var(--suave); margin-bottom: 12px; }
    #log { background: var(--panel); border: 1px solid var(--borde); border-radius: 10px;
           height: 58vh; min-height: 320px; overflow-y: auto; padding: 14px; display: flex;
           flex-direction: column; gap: 10px; }
    .msg { max-width: 88%; padding: 10px 12px; border-radius: 12px; line-height: 1.45;
           white-space: pre-wrap; overflow-wrap: anywhere; font-size: .95rem; }
    .msg p { margin: 0; }
    .bot { align-self: flex-start; background: var(--burbuja); border: 1px solid var(--borde); }
    .yo { align-self: flex-end; background: var(--marca); color: #fff; }
    .error { align-self: center; background: #fde8e8; color: #8a1c1c; border: 1px solid #f5b5b5;
             font-size: .85rem; }
    form { display: flex; gap: 8px; margin-top: 12px; }
    input { flex: 1; padding: 12px; border-radius: 9px; border: 1px solid var(--borde);
            background: var(--panel); color: var(--texto); font-size: 1rem; }
    button { padding: 12px 16px; border: 0; border-radius: 9px; background: var(--marca);
             color: #fff; font-size: .95rem; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    .piedepagina { display: flex; justify-content: space-between; align-items: center; gap: 10px;
                   margin-top: 8px; color: var(--suave); font-size: .8rem; flex-wrap: wrap; }
    .enlace { background: none; color: var(--marca); border: 0; padding: 0; cursor: pointer;
              text-decoration: underline; font-size: .8rem; }
  </style>
</head>
<body>
  <main class="marco">
    <header>
      <h1>Agente de siniestros</h1>
      <span class="autor">Demo de agente denuncia de siniestros bot</span>
    </header>

    <div class="aviso">
      <strong>Demo pública.</strong> Usa solo datos ficticios: no escribas nombres, documentos,
      teléfonos ni información real. El servicio gratuito puede dormir; el primer mensaje puede
      tardar hasta un minuto. Las denuncias registradas se guardan en una base compartida y
      desaparecen cuando el servidor se reinicia.
    </div>

    <div id="log" aria-live="polite"></div>

    <form id="formulario">
      <input id="mensaje" autocomplete="off" maxlength="1000"
             placeholder="Ej.: Quiero denunciar un choque ocurrido ayer en La Paz" required>
      <button id="enviar" type="submit">Enviar</button>
    </form>

    <div class="piedepagina">
      <span id="estado"></span>
      <button class="enlace" id="reiniciar" type="button">Reiniciar conversación</button>
    </div>
  </main>

  <script>
    const CLAVE = "agente_siniestro_sesion";
    const log = document.getElementById("log");
    const formulario = document.getElementById("formulario");
    const entrada = document.getElementById("mensaje");
    const boton = document.getElementById("enviar");
    const estado = document.getElementById("estado");
    const reiniciar = document.getElementById("reiniciar");

    function nuevaSesion() {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
      return String(Date.now()) + "-" + Math.random().toString(16).slice(2);
    }

    let sesion = localStorage.getItem(CLAVE);
    if (!sesion) {
      sesion = nuevaSesion();
      localStorage.setItem(CLAVE, sesion);
    }

    function burbuja(texto, quien) {
      const caja = document.createElement("div");
      caja.className = "msg " + quien;
      const parrafo = document.createElement("p");
      parrafo.textContent = texto;
      caja.appendChild(parrafo);
      log.appendChild(caja);
      log.scrollTop = log.scrollHeight;
    }

    burbuja("Hola. Soy el asistente de siniestros. Cuéntame qué ocurrió, con datos ficticios.", "bot");

    formulario.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const texto = entrada.value.trim();
      if (!texto) return;
      burbuja(texto, "yo");
      entrada.value = "";
      boton.disabled = true;
      estado.textContent = "Pensando...";
      try {
        const respuesta = await fetch("/demo/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sesion: sesion, mensaje: texto })
        });
        const datos = await respuesta.json().catch(() => ({}));
        if (!respuesta.ok) throw new Error(datos.detail || "Error del servidor");
        burbuja(datos.texto, "bot");
      } catch (error) {
        burbuja("No se pudo responder: " + error.message, "error");
      } finally {
        boton.disabled = false;
        estado.textContent = "";
        entrada.focus();
      }
    });

    reiniciar.addEventListener("click", async () => {
      try {
        await fetch("/demo/reiniciar", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sesion: sesion })
        });
      } catch (error) {
        // Si falla, igual empezamos una sesión nueva en el navegador.
      }
      sesion = nuevaSesion();
      localStorage.setItem(CLAVE, sesion);
      log.innerHTML = "";
      burbuja("Listo. Empezamos de nuevo. Cuéntame qué ocurrió, con datos ficticios.", "bot");
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def inicio() -> str:
    """La página de chat."""
    return HTML
