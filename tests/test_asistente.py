"""Pruebas sin modelo real ni internet: uv run pytest

Un modelo falso (FunctionModel) pide la tool que queremos, y comprobamos lo que hace el código.
Cada prueba usa su propia base SQLite (creada desde datos/siniestros.csv).
"""

import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY_LOCAL", "clave-de-prueba")  # para importar sin .env (no se llama a Gemini)

import httpx  # noqa: E402
import pytest  # noqa: E402
from pydantic import SecretStr  # noqa: E402
from pydantic_ai import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.conversation import Conversation  # noqa: E402
from pydantic_ai.messages import UserPromptPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

import api  # noqa: E402
import asistente  # noqa: E402
import bot  # noqa: E402
import capacidades  # noqa: E402
import siniestros  # noqa: E402
from config import settings  # noqa: E402

COMPLETA = {
    "ramo": "SOAT",
    "tipo_seguro": "SOAT - responsabilidad civil",
    "numero_poliza": "SOAT-2026-9999",
    "fecha_siniestro": "2026-11-05",
    "hora_siniestro": "10:15",
    "lugar_siniestro": "Av. Blanco Galindo, Cochabamba",
    "descripcion_hechos": "Colisión leve en una rotonda; sin personas lesionadas.",
    "nombre_denunciante": "Ana Pérez",
    "documento_denunciante": "5555555 CBBA",
    "telefono_denunciante": "70000000",
    "nombre_asegurado": "Ana Pérez",
    "documento_asegurado": "5555555 CBBA",
    "datos_afectados": [],
    "datos_vehiculo": "Toyota Yaris 2020, placa 1111-AAA",
    "existencia_lesionados": False,
    "existencia_fallecidos": False,
    "danos_materiales": "Rayón en la puerta derecha",
    "documentacion_recibida": ["Cédula de identidad del denunciante"],
    "documentacion_pendiente": [],
    "observaciones": None,
}


@pytest.fixture(autouse=True)
def base_temporal(tmp_path, monkeypatch):
    """Cada prueba usa su propia siniestros.db y su carpeta de PDFs, no las de datos/."""
    monkeypatch.setattr(siniestros, "DB", tmp_path / "siniestros.db")
    monkeypatch.setattr(siniestros, "GENERADOS", tmp_path / "generados")


def pide(tool: str, args: dict) -> FunctionModel:
    """Un modelo falso: la 1.ª vez pide la tool; cuando recibe su resultado, responde texto."""

    def responder(mensajes, info):
        ultimo = mensajes[-1].parts[-1]
        if isinstance(ultimo, ToolReturnPart):
            return ModelResponse(parts=[TextPart(f"Resultado: {ultimo.content}")])
        return ModelResponse(parts=[ToolCallPart(tool, args)])

    return FunctionModel(responder)


def anio_de_hoy() -> int:
    return date.today().year


# ── Consulta ──


def test_buscar_por_documento_devuelve_resumen_y_enmascara():
    resultado = capacidades.buscar_siniestros(documento="6543210")
    assert resultado["total"] == 1
    siniestro = resultado["siniestros"][0]
    assert siniestro["numero_siniestro"] == "SIN-2026-0001"
    assert siniestro["estado"] == "EN_REVISION"
    assert siniestro["documento_asegurado"].startswith("*")  # no se muestra completo en el listado


def test_buscar_por_tipo_seguro():
    resultado = capacidades.buscar_siniestros(tipo_seguro="todo riesgo")
    assert resultado["total"] == 1
    assert resultado["siniestros"][0]["numero_siniestro"] == "SIN-2026-0004"


def test_buscar_sin_criterios_avisa():
    resultado = capacidades.buscar_siniestros()
    assert "error" in resultado


def test_detalle_incluye_historial():
    resultado = capacidades.detalle_siniestro("SIN-2026-0003")
    assert resultado["siniestro"]["nombre_asegurado"] == "Jorge Fernández Roca"
    assert resultado["historial"][0]["estado_nuevo"] == "APROBADO"


def test_detalle_inexistente():
    assert "error" in capacidades.detalle_siniestro("SIN-2026-9999")


def test_requisitos_por_ramo():
    resultado = capacidades.requisitos_documentales("SOAT")
    assert "Certificado de SOAT vigente" in resultado["documentos"]


# ── Registro ──


def test_registrar_denuncia_completa():
    resultado = capacidades.registrar_siniestro(siniestros.DenunciaNueva(**COMPLETA))
    assert resultado["registrado"] is True
    assert resultado["numero_siniestro"].startswith(f"SIN-{anio_de_hoy()}-")
    detalle = capacidades.detalle_siniestro(resultado["numero_siniestro"])
    assert detalle["siniestro"]["estado"] == "REGISTRADO"
    assert detalle["siniestro"]["lugar_siniestro"] == "Av. Blanco Galindo, Cochabamba"
    assert detalle["historial"][0]["estado_nuevo"] == "REGISTRADO"


def test_registrar_sin_datos_obligatorios_no_guarda():
    antes = len(siniestros.buscar(ramo="Seguro de Vida")["siniestros"])
    resultado = capacidades.registrar_siniestro(siniestros.DenunciaNueva(ramo="Seguro de Vida"))
    assert resultado["registrado"] is False
    assert resultado["faltantes"]
    despues = len(siniestros.buscar(ramo="Seguro de Vida")["siniestros"])
    assert antes == despues


def test_registrar_como_pendiente_de_informacion():
    resultado = capacidades.registrar_siniestro(
        siniestros.DenunciaNueva(ramo="Seguro de Vida", descripcion_hechos="Fallecimiento del asegurado"),
        estado_inicial="PENDIENTE_DE_INFORMACION",
    )
    assert resultado["registrado"] is True
    assert resultado["estado"] == "PENDIENTE_DE_INFORMACION"
    assert resultado["faltantes"]  # se informa qué quedó pendiente


def test_avisa_duplicado_y_solo_registra_si_se_confirma():
    denuncia = siniestros.DenunciaNueva(**{**COMPLETA, "fecha_siniestro": "2026-10-12",
                                           "documento_asegurado": "6543210 LP", "numero_poliza": "SOAT-2026-0451"})
    primero = capacidades.registrar_siniestro(denuncia)
    assert primero["registrado"] is False
    assert primero["coincidencias"][0]["numero_siniestro"] == "SIN-2026-0001"

    segundo = capacidades.registrar_siniestro(denuncia, confirmar_duplicado=True)
    assert segundo["registrado"] is True


def test_revisar_denuncia_sin_guardar():
    revision = capacidades.revisar_denuncia(siniestros.DenunciaNueva(ramo="SOAT", descripcion_hechos="Choque"))
    assert revision["listo_para_registrar"] is False
    assert "Número de póliza" in revision["obligatorios_faltantes"]
    assert "Formulario de declaración de siniestro" in revision["documentacion_sugerida"]


# ── Seguimiento ──


def test_cambiar_estado_deja_historial():
    resultado = capacidades.cambiar_estado("SIN-2026-0001", "OBSERVADO", "Ana (analista)", "Falta el parte policial")
    assert resultado["actualizado"] is True
    assert resultado["estado_anterior"] == "EN_REVISION"
    detalle = capacidades.detalle_siniestro("SIN-2026-0001")
    assert detalle["siniestro"]["estado"] == "OBSERVADO"
    ultimo = detalle["historial"][-1]
    assert ultimo["usuario"] == "Ana (analista)"
    assert ultimo["observacion"] == "Falta el parte policial"


def test_cambiar_estado_exige_motivo():
    assert "error" in capacidades.cambiar_estado("SIN-2026-0001", "CERRADO", "Ana", "   ")


def test_cambiar_estado_inexistente():
    assert "error" in capacidades.cambiar_estado("SIN-2026-9999", "CERRADO", "Ana", "Prueba")


# ── PDFs ──


def test_generar_comprobante_pdf(tmp_path):
    resultado = capacidades.generar_comprobante("SIN-2026-0001")
    archivo = siniestros.GENERADOS / resultado["archivo"]
    assert archivo.is_file()
    assert archivo.read_bytes().startswith(b"%PDF")
    assert "no es una aprobación" in resultado["aviso"]


def test_generar_guia_pdf():
    resultado = capacidades.generar_guia_denuncia("Seguro Automotor")
    archivo = siniestros.GENERADOS / resultado["archivo"]
    assert archivo.is_file()
    assert archivo.read_bytes().startswith(b"%PDF")


# ── El agente ──


async def test_el_agente_recuerda_la_conversacion():
    """Dos mensajes seguidos: el segundo run debe ver el primero."""
    vistos = []

    def modelo_falso(mensajes, info):
        textos = [
            parte.content
            for mensaje in mensajes
            for parte in mensaje.parts
            if isinstance(parte, UserPromptPart)
        ]
        vistos.append(" ".join(textos))
        return ModelResponse(parts=[TextPart("Entendido.")])

    with asistente.asistente.override(model=FunctionModel(modelo_falso)):
        conversacion = Conversation()
        await asistente.responder("Quiero denunciar un choque", conversacion)
        await asistente.responder("Fue ayer en La Paz", conversacion)

    assert "choque" in vistos[1]  # el segundo mensaje conserva el contexto del primero
    assert "La Paz" in vistos[1]
    assert len(conversacion.messages) == 4  # 2 del usuario + 2 del asistente


async def test_el_agente_registra_con_la_tool():
    with asistente.asistente.override(model=pide("registrar_siniestro", {"denuncia": COMPLETA})):
        respuesta = await asistente.responder("Registra la denuncia que confirmé.")
    assert "registrado" in respuesta and "SIN-" in respuesta


# ── Telegram y API ──


async def test_chat_ajeno_se_rechaza_sin_llamar_al_modelo(monkeypatch):
    monkeypatch.setattr(settings, "telegram_permitidos", "123")
    respuestas = []

    async def reply_text(texto):
        respuestas.append(texto)

    def modelo_prohibido(mensajes, info):
        raise AssertionError("no debía llamarse al modelo")

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=999), message=SimpleNamespace(text="hola", reply_text=reply_text)
    )
    with asistente.asistente.override(model=FunctionModel(modelo_prohibido)):
        await bot.mensaje(update, None)
    assert "No autorizado" in respuestas[0] and "999" in respuestas[0]


async def test_comando_autor(monkeypatch):
    monkeypatch.setattr(settings, "telegram_permitidos", "123")
    textos = []

    async def reply_text(texto):
        textos.append(texto)

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123), message=SimpleNamespace(reply_text=reply_text)
    )
    await bot.autor(update, None)
    assert asistente.AUTOR in textos[0]
    assert asistente.AUTOR in asistente.INSTRUCCIONES


async def test_comando_comprobante_envia_el_pdf(monkeypatch):
    monkeypatch.setattr(settings, "telegram_permitidos", "123")
    enviados, textos = [], []

    async def reply_document(document, filename):
        enviados.append((document, filename))

    async def reply_text(texto):
        textos.append(texto)

    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=123),
        message=SimpleNamespace(reply_document=reply_document, reply_text=reply_text),
    )
    await bot.comprobante(update, SimpleNamespace(args=["SIN-2026-0001"]))
    assert enviados and enviados[0][0].startswith(b"%PDF")
    assert "no es una aprobación" in textos[0].lower()


def test_permitidos(monkeypatch):
    monkeypatch.setattr(settings, "telegram_permitidos", " 123, 456 ,")
    assert settings.permitidos == {"123", "456"}
    monkeypatch.setattr(settings, "telegram_permitidos", "")
    assert settings.permitidos == set()  # vacío = nadie


async def post_chat(cuerpo: dict, token: str | None = None) -> httpx.Response:
    """Llama a la API en el mismo proceso, sin servidor ni red."""
    cabeceras = {"Authorization": f"Bearer {token}"} if token else {}
    transporte = httpx.ASGITransport(app=api.app)
    async with httpx.AsyncClient(transport=transporte, base_url="http://prueba") as cliente:
        return await cliente.post("/chat", json=cuerpo, headers=cabeceras)


async def test_api_sin_token_valido_no_llama_al_modelo(monkeypatch):
    def modelo_prohibido(mensajes, info):
        raise AssertionError("no debía llamarse al modelo")

    with asistente.asistente.override(model=FunctionModel(modelo_prohibido)):
        monkeypatch.setattr(settings, "api_tokens", SecretStr(""))
        assert (await post_chat({"mensaje": "hola"}, "cualquiera")).status_code == 401  # vacío = nadie
        monkeypatch.setattr(settings, "api_tokens", SecretStr("abc, def"))
        assert (await post_chat({"mensaje": "hola"})).status_code == 401
        assert (await post_chat({"mensaje": "hola"}, "xyz")).status_code == 401
        assert (await post_chat({"mensaje": ""}, "abc")).status_code == 422  # Pydantic valida el pedido


async def test_api_con_token_responde(monkeypatch):
    monkeypatch.setattr(settings, "api_tokens", SecretStr("abc,def"))
    with asistente.asistente.override(model=pide("buscar_siniestros", {"documento": "6543210"})):
        r = await post_chat({"mensaje": "¿Existe una denuncia con documento 6543210?"}, "def")
    assert r.status_code == 200
    assert "SIN-2026-0001" in r.json()["texto"]
