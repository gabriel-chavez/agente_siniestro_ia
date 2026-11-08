"""Las capabilities del agente de siniestros: tools + instrucciones.

El docstring y los tipos de cada tool son lo único que el modelo lee para decidir cuándo usarla.
Las operaciones sobre SQLite y los PDFs viven en siniestros.py; aquí solo se exponen como tools.
"""

from functools import cache

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pydantic_ai.capabilities import Capability
from pypdf import PdfReader

import siniestros
from config import DATOS, settings
from siniestros import DenunciaNueva, Estado, EstadoInicial, Ramo

# ═══ Registro y seguimiento: las tools que escriben ══════════════════════════════════
registro = Capability(
    id="registro_siniestros",
    description="Registra denuncias de siniestros y actualiza su estado en la base local SQLite",
    instructions=[
        "Usa registrar_siniestro SOLO después de mostrar el resumen de la denuncia y recibir "
        "una confirmación explícita del usuario.",
        "Nunca digas que una denuncia quedó registrada si la tool devolvió un error.",
        "Si la tool avisa de un posible duplicado, informa al usuario y pide permiso antes de "
        "repetir la llamada con confirmar_duplicado=True.",
        "Cambia el estado solo cuando un usuario autorizado lo pida expresamente y explique el motivo; "
        "la tool exige el usuario responsable y una observación.",
    ],
)


@registro.tool_plain
def registrar_siniestro(
    denuncia: DenunciaNueva,
    estado_inicial: EstadoInicial = "REGISTRADO",
    confirmar_duplicado: bool = False,
) -> dict:
    """Registra una denuncia de siniestro y devuelve su número único.

    Antes de llamarla, muestra el resumen al usuario y espera su confirmación.
    Si faltan datos obligatorios, la tool no guarda nada y devuelve la lista de faltantes:
    pídelos o registra la denuncia como PENDIENTE_DE_INFORMACION.

    Args:
        denuncia: datos extraídos de la conversación (ramo, fecha, lugar, hechos, asegurado, etc.)
        estado_inicial: REGISTRADO si la información mínima está completa; PENDIENTE_DE_INFORMACION si faltan datos
        confirmar_duplicado: True solo si el usuario confirmó que, pese a la coincidencia, es otra denuncia
    """
    return siniestros.registrar(denuncia, estado_inicial, confirmar_duplicado)


@registro.tool_plain
def cambiar_estado(numero_siniestro: str, estado_nuevo: Estado, usuario: str, observacion: str) -> dict:
    """Cambia el estado de una denuncia y deja el cambio en el historial.

    Args:
        numero_siniestro: número devuelto al registrar, por ejemplo 'SIN-2026-0001'
        estado_nuevo: nuevo estado del siniestro
        usuario: nombre o identificador del responsable autorizado del cambio
        observacion: motivo o detalle del cambio (obligatorio)
    """
    return siniestros.cambiar_estado(numero_siniestro, estado_nuevo, usuario, observacion)


# ═══ Consulta: las tools que leen ════════════════════════════════════════════════════
consulta = Capability(
    id="consulta_siniestros",
    description="Consulta denuncias de siniestros, sus datos, su historial y sus requisitos documentales",
    instructions=(
        "Usa buscar_siniestros para localizar denuncias y detalle_siniestro para ver una en concreto. "
        "No inventes números, estados ni datos: si la tool no encuentra nada, dilo. "
        "En los listados muestra solo la información necesaria y no reveles datos de otros asegurados."
    ),
)


@consulta.tool_plain
def buscar_siniestros(
    numero_siniestro: str | None = None,
    numero_poliza: str | None = None,
    documento: str | None = None,
    nombre: str | None = None,
    fecha_siniestro: str | None = None,
    ramo: Ramo | None = None,
    tipo_seguro: str | None = None,
    estado: Estado | None = None,
) -> dict:
    """Busca denuncias registradas. Devuelve una lista resumida.

    Usa al menos un criterio. Si hay varios resultados, muéstralos y pregunta cuál desea consultar.

    Args:
        numero_siniestro: número de siniestro o parte de él, por ejemplo 'SIN-2026-0001'
        numero_poliza: número de póliza o certificado
        documento: documento de identidad del asegurado o del denunciante
        nombre: nombre del asegurado o del denunciante
        fecha_siniestro: fecha del siniestro en formato AAAA-MM-DD
        ramo: ramo del seguro
        tipo_seguro: nombre o parte del tipo de seguro
        estado: estado actual de la denuncia
    """
    return siniestros.buscar(
        numero_siniestro=numero_siniestro,
        numero_poliza=numero_poliza,
        documento=documento,
        nombre=nombre,
        fecha_siniestro=fecha_siniestro,
        ramo=ramo,
        tipo_seguro=tipo_seguro,
        estado=estado,
    )


@consulta.tool_plain
def detalle_siniestro(numero_siniestro: str) -> dict:
    """Todos los datos de una denuncia y su historial de estados.

    Args:
        numero_siniestro: número exacto, por ejemplo 'SIN-2026-0001'
    """
    return siniestros.detalle(numero_siniestro)


@consulta.tool_plain
def revisar_denuncia(denuncia: DenunciaNueva) -> dict:
    """Revisa una denuncia antes de registrarla: datos obligatorios, complementarios y documentos.

    Úsala cuando ya tengas varios datos y quieras saber qué preguntar a continuación.
    No guarda nada en la base.

    Args:
        denuncia: datos reunidos hasta el momento en la conversación
    """
    return siniestros.faltantes(denuncia)


@consulta.tool_plain
def requisitos_documentales(ramo: Ramo) -> dict:
    """Documentos que se acostumbra pedir para denunciar un siniestro de un ramo.

    Args:
        ramo: ramo del seguro
    """
    return {
        "ramo": ramo,
        "documentos": siniestros.documentacion_para(ramo),
        "fuente": "instructivo interno de requisitos por ramo",
    }


# ═══ S2 · RAG: buscar en los PDFs de procedimientos y generar documentos de apoyo ════
DOCUMENTOS = DATOS / "documentos"  # manuales, requisitos y formularios ficticios


def embeddings_de(textos: list[str]) -> list[list[float]]:
    """Convierte cada texto en un vector: textos de significado parecido dan vectores cercanos."""
    # Gemini también ofrece una API compatible con la de OpenAI; la usamos para los embeddings
    cliente = OpenAI(
        api_key=settings.gemini_api_key_local.get_secret_value(),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    respuesta = cliente.embeddings.create(model="gemini-embedding-001", input=textos)
    return [item.embedding for item in respuesta.data]


@cache  # se indexa la primera vez que alguien busca, y una sola vez mientras el programa corre
def indice():
    # Base vectorial en memoria (se pierde al terminar); "cosine" mide la cercanía por el ángulo
    coleccion = chromadb.EphemeralClient().get_or_create_collection(
        "documentos", configuration={"hnsw": {"space": "cosine"}}
    )
    for pdf in sorted(DOCUMENTOS.glob("*.pdf")):
        texto = "\n".join(pagina.extract_text() for pagina in PdfReader(pdf).pages)
        # Trozos de ~300 caracteres que se solapan 50, para no cortar una idea por la mitad
        trozos = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50).split_text(texto)
        coleccion.upsert(
            ids=[f"{pdf.stem}-{i}" for i in range(len(trozos))],  # el id dice de qué PDF sale: sirve para citar
            documents=trozos,
            embeddings=embeddings_de(trozos),
        )
    return coleccion


def buscar_documentos_en_pdfs(pregunta: str, k: int = 3) -> list[dict]:
    """Los k trozos más parecidos a la pregunta, con su fuente y su similitud (1 = idéntico)."""
    r = indice().query(query_embeddings=embeddings_de([pregunta]), n_results=k)
    return [
        {"fuente": fuente, "similitud": round(1 - distancia, 2), "texto": texto}
        for fuente, distancia, texto in zip(r["ids"][0], r["distances"][0], r["documents"][0])
    ]


documentos = Capability(
    id="documentos_siniestros",
    description="Manuales y requisitos de siniestros en PDF, y generación de guías y comprobantes",
    # Citar la fuente y admitir cuando no hay datos: así se ve qué sale de los documentos y qué no
    instructions=(
        "Para preguntas sobre procedimientos, requisitos o formularios usa buscar_documentos y cita "
        "la fuente entre corchetes, por ejemplo [manual_denuncia_siniestros-1]. "
        "Si no hay información suficiente, di que no lo encuentras, no lo inventes. "
        "Puedes generar una guía con generar_guia_denuncia y un comprobante con generar_comprobante. "
        "Presenta esos PDFs como documentos de apoyo, nunca como una aprobación del siniestro."
    ),
)


@documentos.tool_plain
def buscar_documentos(pregunta: str) -> list[dict]:
    """Busca en los PDFs de procedimientos los fragmentos que responden a la pregunta."""
    resultados = buscar_documentos_en_pdfs(pregunta, k=3)
    for r in resultados:  # en la terminal (o en los Logs de Render) se ve qué recuperó
        print(f"  📄 {r['fuente']} (similitud {r['similitud']})", flush=True)
    return resultados


@documentos.tool_plain
def generar_comprobante(numero_siniestro: str) -> dict:
    """Genera el PDF del comprobante de recepción de una denuncia ya registrada.

    Args:
        numero_siniestro: número exacto devuelto al registrar, por ejemplo 'SIN-2026-0001'
    """
    return siniestros.generar_comprobante(numero_siniestro)


@documentos.tool_plain
def generar_guia_denuncia(ramo: Ramo) -> dict:
    """Genera un PDF con los pasos y documentos para denunciar un siniestro de un ramo.

    Args:
        ramo: ramo del seguro
    """
    return siniestros.generar_guia(ramo)
