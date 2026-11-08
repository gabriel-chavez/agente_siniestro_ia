"""Datos, base de datos y documentos PDF de las denuncias de siniestros.

Aquí vive el «dominio»: el modelo Pydantic (Denuncia), las operaciones sobre SQLite
y la generación de PDFs. Las tools que ve el modelo están en capacidades.py y solo
llaman a estas funciones. Los datos de práctica son ficticios.
"""

import csv
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from fpdf import FPDF
from pydantic import BaseModel, Field

from config import DATOS

DB = DATOS / "siniestros.db"  # la base se crea desde el CSV la primera vez
CSV = DATOS / "siniestros.csv"  # 6 denuncias ficticias de ejemplo
GENERADOS = DATOS / "generados"  # aquí se guardan los PDFs que genera el agente

# Lista cerrada: el modelo solo puede elegir uno de estos valores
Ramo = Literal[
    "SOAT",
    "SOATC",
    "Seguro de Vida",
    "Accidentes Personales",
    "Seguro Automotor",
    "Otros",
]
Estado = Literal[
    "BORRADOR",
    "PENDIENTE_DE_INFORMACION",
    "REGISTRADO",
    "EN_REVISION",
    "DOCUMENTACION_PENDIENTE",
    "OBSERVADO",
    "APROBADO",
    "RECHAZADO",
    "CERRADO",
]
EstadoInicial = Literal["REGISTRADO", "PENDIENTE_DE_INFORMACION"]

COLUMNAS = [
    "numero_siniestro",
    "ramo",
    "tipo_seguro",
    "numero_poliza",
    "fecha_siniestro",
    "hora_siniestro",
    "lugar_siniestro",
    "descripcion_hechos",
    "nombre_denunciante",
    "documento_denunciante",
    "telefono_denunciante",
    "nombre_asegurado",
    "documento_asegurado",
    "datos_afectados",
    "datos_vehiculo",
    "existencia_lesionados",
    "existencia_fallecidos",
    "danos_materiales",
    "documentacion_recibida",
    "documentacion_pendiente",
    "fecha_registro",
    "estado",
    "observaciones",
]

ETIQUETAS = {
    "ramo": "Ramo",
    "tipo_seguro": "Tipo de seguro",
    "numero_poliza": "Número de póliza",
    "fecha_siniestro": "Fecha del siniestro",
    "hora_siniestro": "Hora del siniestro",
    "lugar_siniestro": "Lugar del siniestro",
    "descripcion_hechos": "Descripción de los hechos",
    "nombre_denunciante": "Nombre del denunciante",
    "documento_denunciante": "Documento del denunciante",
    "telefono_denunciante": "Teléfono del denunciante",
    "nombre_asegurado": "Nombre del asegurado",
    "documento_asegurado": "Documento del asegurado",
    "datos_afectados": "Personas afectadas",
    "datos_vehiculo": "Datos del vehículo",
    "danos_materiales": "Daños materiales",
    "observaciones": "Observaciones",
}

# Documentos que se acostumbra pedir en cada ramo (material ficticio de práctica)
REQUISITOS = {
    "SOAT": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Licencia de conducir",
        "Certificado de SOAT vigente",
        "Documento del vehículo",
        "Parte policial o croquis (si hubo colisión)",
        "Certificados médicos (si hay personas lesionadas)",
    ],
    "SOATC": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Licencia de conducir",
        "Certificado de SOATC vigente",
        "Documento del vehículo",
        "Parte policial o croquis",
        "Certificados médicos (si hay personas lesionadas)",
        "Presupuesto de reparación",
    ],
    "Seguro de Vida": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Póliza o certificado de cobertura",
        "Certificado de defunción (si corresponde)",
        "Certificado médico",
        "Documentos de identificación de los beneficiarios",
    ],
    "Accidentes Personales": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Póliza o certificado de cobertura",
        "Certificado médico",
        "Radiografías o estudios (si corresponde)",
        "Facturas de atención médica",
        "Denuncia policial (si corresponde)",
    ],
    "Seguro Automotor": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Licencia de conducir",
        "Póliza vigente",
        "Documento del vehículo",
        "Parte policial o denuncia de robo",
        "Croquis o fotografías de los daños",
        "Presupuesto de reparación",
    ],
    "Otros": [
        "Formulario de declaración de siniestro",
        "Cédula de identidad del denunciante",
        "Póliza o certificado de cobertura",
        "Documentos de respaldo del hecho",
    ],
}

# Datos que siempre hacen falta para registrar una denuncia completa
OBLIGATORIOS = [
    "numero_poliza",
    "fecha_siniestro",
    "lugar_siniestro",
    "descripcion_hechos",
    "nombre_denunciante",
    "documento_denunciante",
    "nombre_asegurado",
    "documento_asegurado",
]
COMPLEMENTARIOS = ["hora_siniestro", "telefono_denunciante", "danos_materiales", "observaciones"]


class DenunciaNueva(BaseModel):
    """Información que el agente extrae de la conversación. Solo el ramo es imprescindible."""

    ramo: Ramo = Field(description="Ramo del seguro: SOAT, SOATC, Seguro de Vida, Accidentes Personales, Seguro Automotor u Otros")
    tipo_seguro: str | None = Field(default=None, description="Nombre del producto o cobertura, por ejemplo 'SOAT - responsabilidad civil'")
    numero_poliza: str | None = Field(default=None, description="Número de póliza o certificado")
    fecha_siniestro: date | None = Field(default=None, description="Fecha del siniestro en formato AAAA-MM-DD")
    hora_siniestro: str | None = Field(default=None, description="Hora aproximada, por ejemplo '15:30'")
    lugar_siniestro: str | None = Field(default=None, description="Lugar o dirección del siniestro")
    descripcion_hechos: str | None = Field(default=None, description="Relato de lo ocurrido, en palabras del usuario")
    nombre_denunciante: str | None = Field(default=None, description="Nombre completo de quien denuncia")
    documento_denunciante: str | None = Field(default=None, description="Documento de identidad del denunciante")
    telefono_denunciante: str | None = Field(default=None, description="Teléfono de contacto del denunciante")
    nombre_asegurado: str | None = Field(default=None, description="Nombre completo del asegurado")
    documento_asegurado: str | None = Field(default=None, description="Documento de identidad del asegurado")
    datos_afectados: list[str] = Field(default_factory=list, description="Personas afectadas: nombre, rol y lesiones")
    datos_vehiculo: str | None = Field(default=None, description="Marca, modelo, año, placa y color del vehículo")
    existencia_lesionados: bool = Field(default=False, description="True si hubo personas lesionadas")
    existencia_fallecidos: bool = Field(default=False, description="True si hubo personas fallecidas")
    danos_materiales: str | None = Field(default=None, description="Descripción de los daños materiales")
    documentacion_recibida: list[str] = Field(default_factory=list, description="Documentos que el usuario ya entregó")
    documentacion_pendiente: list[str] = Field(default_factory=list, description="Documentos que quedan pendientes")
    observaciones: str | None = Field(default=None, description="Observaciones adicionales")


class Denuncia(DenunciaNueva):
    """Una denuncia ya guardada en la base."""

    id: int | None = None
    numero_siniestro: str
    fecha_registro: datetime
    estado: Estado = "REGISTRADO"


def hoy() -> str:
    """Instrucción dinámica: el modelo no sabe qué día es; se lo decimos en cada mensaje."""
    return f"Hoy es {date.today().isoformat()}."


# ═══ Base de datos ══════════════════════════════════════════════════════════════════


def crear_base() -> None:
    """Crea siniestros.db desde cero con las denuncias ficticias del CSV."""
    DB.unlink(missing_ok=True)
    with CSV.open(encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo, delimiter=";"))
    conexion = sqlite3.connect(DB)
    with conexion:
        conexion.execute(
            "CREATE TABLE siniestros ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            + ", ".join(f"{columna} TEXT" for columna in COLUMNAS)
            + ", UNIQUE (numero_siniestro))"
        )
        conexion.execute(
            "CREATE TABLE historial ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "numero_siniestro TEXT NOT NULL, "
            "fecha_hora TEXT NOT NULL, "
            "estado_anterior TEXT, "
            "estado_nuevo TEXT NOT NULL, "
            "usuario TEXT, "
            "observacion TEXT)"
        )
        conexion.executemany(
            f"INSERT INTO siniestros ({', '.join(COLUMNAS)}) VALUES ({', '.join('?' for _ in COLUMNAS)})",
            [tuple(fila[columna] for columna in COLUMNAS) for fila in filas],
        )
        conexion.executemany(
            "INSERT INTO historial (numero_siniestro, fecha_hora, estado_anterior, estado_nuevo, usuario, observacion) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (fila["numero_siniestro"], fila["fecha_registro"], None, fila["estado"],
                 "Sistema (carga inicial)", "Datos ficticios de práctica")
                for fila in filas
            ],
        )
    conexion.close()


def conectar(solo_lectura: bool = False) -> sqlite3.Connection:
    """Abre la base. Si no existe, la crea desde el CSV. Cada fila se lee como diccionario."""
    if not DB.exists():
        crear_base()
    if solo_lectura:
        conexion = sqlite3.connect(DB.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        conexion = sqlite3.connect(DB)
    conexion.row_factory = sqlite3.Row
    return conexion


# ═══ Listas guardadas como texto ═════════════════════════════════════════════════════


def _unir(lista: list[str]) -> str:
    return " | ".join(elemento.strip() for elemento in lista if elemento.strip())


def _separar(texto: str | None) -> list[str]:
    return [parte.strip() for parte in (texto or "").split(" | ") if parte.strip()]


def _enmascarar(documento: str | None) -> str | None:
    """En los listados se muestra solo el final del documento: menos datos personales."""
    if not documento:
        return None
    return "*" * max(0, len(documento) - 4) + documento[-4:]


def _si_no(valor: bool) -> str:
    return "Sí" if valor else "No"


# ═══ Reglas de la denuncia ═══════════════════════════════════════════════════════════


def documentacion_para(ramo: Ramo) -> list[str]:
    """Documentos que se acostumbra pedir en un ramo."""
    return list(REQUISITOS.get(ramo, REQUISITOS["Otros"]))


def _ya_recibido(documento: str, recibidos: list[str]) -> bool:
    nombre = documento.lower()
    return any(nombre in recibido.lower() or recibido.lower() in nombre for recibido in recibidos)


def faltantes(denuncia: DenunciaNueva) -> dict:
    """Qué información falta y qué documentación conviene pedir, según el ramo."""
    obligatorios = list(OBLIGATORIOS)
    if denuncia.ramo in {"SOAT", "SOATC", "Seguro Automotor"}:
        obligatorios.append("datos_vehiculo")
    if denuncia.existencia_lesionados or denuncia.existencia_fallecidos:
        obligatorios.append("datos_afectados")

    faltan_obligatorios = [ETIQUETAS[campo] for campo in obligatorios if not getattr(denuncia, campo)]
    faltan_complementarios = [ETIQUETAS[campo] for campo in COMPLEMENTARIOS if not getattr(denuncia, campo)]
    pendientes = [
        documento
        for documento in documentacion_para(denuncia.ramo)
        if not _ya_recibido(documento, denuncia.documentacion_recibida)
    ]
    return {
        "obligatorios_faltantes": faltan_obligatorios,
        "complementarios_faltantes": faltan_complementarios,
        "documentacion_sugerida": pendientes,
        "listo_para_registrar": not faltan_obligatorios,
    }


# ═══ Operaciones ═════════════════════════════════════════════════════════════════════


def _duplicados(conexion: sqlite3.Connection, denuncia: DenunciaNueva) -> list[dict]:
    """Denuncias parecidas: mismo documento o póliza, misma fecha y mismo ramo."""
    if not denuncia.fecha_siniestro or not (denuncia.documento_asegurado or denuncia.numero_poliza):
        return []
    criterios = ["fecha_siniestro = ?", "ramo = ?"]
    valores = [denuncia.fecha_siniestro.isoformat(), denuncia.ramo]
    parecidos = []
    if denuncia.documento_asegurado:
        parecidos.append("LOWER(COALESCE(documento_asegurado, '')) = LOWER(?)")
        valores.append(denuncia.documento_asegurado)
    if denuncia.numero_poliza:
        parecidos.append("LOWER(COALESCE(numero_poliza, '')) = LOWER(?)")
        valores.append(denuncia.numero_poliza)
    filas = conexion.execute(
        "SELECT numero_siniestro, fecha_siniestro, estado FROM siniestros WHERE "
        + " AND ".join(criterios)
        + " AND ("
        + " OR ".join(parecidos)
        + ") LIMIT 3",
        valores,
    ).fetchall()
    return [dict(fila) for fila in filas]


def _numero_nuevo(conexion: sqlite3.Connection) -> str:
    """SIN-2026-0001, SIN-2026-0002… según el año en curso."""
    anio = date.today().year
    filas = conexion.execute(
        "SELECT numero_siniestro FROM siniestros WHERE numero_siniestro LIKE ?",
        (f"SIN-{anio}-%",),
    ).fetchall()
    secuencial = max((int(fila[0].rsplit("-", 1)[-1]) for fila in filas), default=0) + 1
    return f"SIN-{anio}-{secuencial:04d}"


def registrar(
    denuncia: DenunciaNueva,
    estado_inicial: EstadoInicial = "REGISTRADO",
    confirmar_duplicado: bool = False,
) -> dict:
    """Guarda la denuncia. Antes revisa datos obligatorios y posibles duplicados."""
    revision = faltantes(denuncia)
    if revision["obligatorios_faltantes"] and estado_inicial == "REGISTRADO":
        return {
            "registrado": False,
            "error": "Faltan datos obligatorios para registrar la denuncia.",
            "faltantes": revision["obligatorios_faltantes"],
            "sugerencia": "Pide esos datos o guárdala como PENDIENTE_DE_INFORMACION.",
        }

    conexion = conectar()
    try:
        coincidencias = _duplicados(conexion, denuncia)
        if coincidencias and not confirmar_duplicado:
            return {
                "registrado": False,
                "advertencia": "Ya existe una denuncia con características similares.",
                "coincidencias": coincidencias,
                "sugerencia": "Informa al usuario y, si confirma que es otra denuncia, repite con confirmar_duplicado=True.",
            }

        numero = _numero_nuevo(conexion)
        fecha_registro = datetime.now().isoformat(timespec="seconds")
        estado = estado_inicial
        pendientes = denuncia.documentacion_pendiente or revision["documentacion_sugerida"]

        valores = {
            "numero_siniestro": numero,
            "ramo": denuncia.ramo,
            "tipo_seguro": denuncia.tipo_seguro,
            "numero_poliza": denuncia.numero_poliza,
            "fecha_siniestro": denuncia.fecha_siniestro.isoformat() if denuncia.fecha_siniestro else None,
            "hora_siniestro": denuncia.hora_siniestro,
            "lugar_siniestro": denuncia.lugar_siniestro,
            "descripcion_hechos": denuncia.descripcion_hechos,
            "nombre_denunciante": denuncia.nombre_denunciante,
            "documento_denunciante": denuncia.documento_denunciante,
            "telefono_denunciante": denuncia.telefono_denunciante,
            "nombre_asegurado": denuncia.nombre_asegurado,
            "documento_asegurado": denuncia.documento_asegurado,
            "datos_afectados": _unir(denuncia.datos_afectados),
            "datos_vehiculo": denuncia.datos_vehiculo,
            "existencia_lesionados": "1" if denuncia.existencia_lesionados else "0",
            "existencia_fallecidos": "1" if denuncia.existencia_fallecidos else "0",
            "danos_materiales": denuncia.danos_materiales,
            "documentacion_recibida": _unir(denuncia.documentacion_recibida),
            "documentacion_pendiente": _unir(pendientes),
            "fecha_registro": fecha_registro,
            "estado": estado,
            "observaciones": denuncia.observaciones,
        }
        with conexion:  # transacción: guarda todo o nada
            conexion.execute(
                f"INSERT INTO siniestros ({', '.join(COLUMNAS)}) VALUES ({', '.join('?' for _ in COLUMNAS)})",
                tuple(valores[columna] for columna in COLUMNAS),
            )
            conexion.execute(
                "INSERT INTO historial (numero_siniestro, fecha_hora, estado_anterior, estado_nuevo, usuario, observacion) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (numero, fecha_registro, None, estado, denuncia.nombre_denunciante or "Denunciante",
                 "Registro inicial de la denuncia"),
            )
    except sqlite3.Error as error:
        return {"registrado": False, "error": f"No se pudo guardar en la base: {error}"}
    finally:
        conexion.close()

    return {
        "registrado": True,
        "numero_siniestro": numero,
        "ramo": denuncia.ramo,
        "fecha_siniestro": valores["fecha_siniestro"],
        "estado": estado,
        "documentacion_pendiente": pendientes,
        "faltantes": revision["obligatorios_faltantes"],
        "fuente": "base de datos local de siniestros",
    }


def buscar(
    numero_siniestro: str | None = None,
    numero_poliza: str | None = None,
    documento: str | None = None,
    nombre: str | None = None,
    fecha_siniestro: str | None = None,
    ramo: Ramo | None = None,
    tipo_seguro: str | None = None,
    estado: Estado | None = None,
) -> dict:
    """Busca denuncias por cualquiera de esos criterios. Devuelve una lista resumida."""
    criterios: list[str] = []
    valores: list[str] = []
    if numero_siniestro:
        criterios.append("numero_siniestro LIKE ?")
        valores.append(f"%{numero_siniestro}%")
    if numero_poliza:
        criterios.append("numero_poliza LIKE ?")
        valores.append(f"%{numero_poliza}%")
    if documento:
        criterios.append("(documento_asegurado LIKE ? OR documento_denunciante LIKE ?)")
        valores.extend([f"%{documento}%", f"%{documento}%"])
    if nombre:
        criterios.append("(nombre_asegurado LIKE ? OR nombre_denunciante LIKE ?)")
        valores.extend([f"%{nombre}%", f"%{nombre}%"])
    if fecha_siniestro:
        criterios.append("fecha_siniestro = ?")
        valores.append(fecha_siniestro)
    if ramo:
        criterios.append("ramo = ?")
        valores.append(ramo)
    if tipo_seguro:
        criterios.append("tipo_seguro LIKE ?")
        valores.append(f"%{tipo_seguro}%")
    if estado:
        criterios.append("estado = ?")
        valores.append(estado)
    if not criterios:
        return {"error": "Indica al menos un criterio: número de siniestro, póliza, documento, nombre, fecha, ramo, tipo de seguro o estado."}

    conexion = conectar(solo_lectura=True)
    filas = conexion.execute(
        "SELECT numero_siniestro, ramo, tipo_seguro, numero_poliza, fecha_siniestro, hora_siniestro, "
        "lugar_siniestro, nombre_asegurado, documento_asegurado, estado, documentacion_pendiente "
        f"FROM siniestros WHERE {' AND '.join(criterios)} ORDER BY fecha_registro DESC LIMIT 20",  # SQL fijo; valores en ?
        valores,
    ).fetchall()
    conexion.close()

    return {
        "total": len(filas),
        "siniestros": [
            {
                "numero_siniestro": fila["numero_siniestro"],
                "ramo": fila["ramo"],
                "tipo_seguro": fila["tipo_seguro"],
                "numero_poliza": fila["numero_poliza"],
                "fecha_siniestro": fila["fecha_siniestro"],
                "hora_siniestro": fila["hora_siniestro"],
                "lugar_siniestro": fila["lugar_siniestro"],
                "nombre_asegurado": fila["nombre_asegurado"],
                "documento_asegurado": _enmascarar(fila["documento_asegurado"]),
                "estado": fila["estado"],
                "documentacion_pendiente": _separar(fila["documentacion_pendiente"]),
            }
            for fila in filas
        ],
        "fuente": "base de datos local de siniestros",
    }


def detalle(numero_siniestro: str) -> dict:
    """Todos los datos de una denuncia y su historial de estados."""
    conexion = conectar(solo_lectura=True)
    fila = conexion.execute(
        "SELECT * FROM siniestros WHERE numero_siniestro = ?", (numero_siniestro,)
    ).fetchone()
    if not fila:
        conexion.close()
        return {"error": f"No encontré la denuncia {numero_siniestro}."}
    historial = conexion.execute(
        "SELECT fecha_hora, estado_anterior, estado_nuevo, usuario, observacion "
        "FROM historial WHERE numero_siniestro = ? ORDER BY id",
        (numero_siniestro,),
    ).fetchall()
    conexion.close()

    datos = dict(fila)
    datos["datos_afectados"] = _separar(datos["datos_afectados"])
    datos["documentacion_recibida"] = _separar(datos["documentacion_recibida"])
    datos["documentacion_pendiente"] = _separar(datos["documentacion_pendiente"])
    datos["existencia_lesionados"] = datos["existencia_lesionados"] == "1"
    datos["existencia_fallecidos"] = datos["existencia_fallecidos"] == "1"
    return {
        "siniestro": datos,
        "historial": [dict(registro) for registro in historial],
        "fuente": "base de datos local de siniestros",
    }


def cambiar_estado(numero_siniestro: str, estado_nuevo: Estado, usuario: str, observacion: str) -> dict:
    """Cambia el estado y deja registro en el historial. Exige usuario y motivo."""
    if not usuario.strip() or not observacion.strip():
        return {"error": "Para cambiar el estado se necesita el usuario responsable y una observación o motivo."}
    conexion = conectar()
    try:
        fila = conexion.execute(
            "SELECT estado FROM siniestros WHERE numero_siniestro = ?", (numero_siniestro,)
        ).fetchone()
        if not fila:
            return {"error": f"No encontré la denuncia {numero_siniestro}."}
        estado_anterior = fila["estado"]
        if estado_anterior == estado_nuevo:
            return {"error": f"La denuncia {numero_siniestro} ya está en estado {estado_nuevo}."}
        fecha_hora = datetime.now().isoformat(timespec="seconds")
        with conexion:
            conexion.execute(
                "UPDATE siniestros SET estado = ? WHERE numero_siniestro = ?",
                (estado_nuevo, numero_siniestro),
            )
            conexion.execute(
                "INSERT INTO historial (numero_siniestro, fecha_hora, estado_anterior, estado_nuevo, usuario, observacion) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (numero_siniestro, fecha_hora, estado_anterior, estado_nuevo, usuario.strip(), observacion.strip()),
            )
    except sqlite3.Error as error:
        return {"error": f"No se pudo cambiar el estado: {error}"}
    finally:
        conexion.close()
    return {
        "actualizado": True,
        "numero_siniestro": numero_siniestro,
        "estado_anterior": estado_anterior,
        "estado_nuevo": estado_nuevo,
        "fecha_hora": fecha_hora,
        "usuario": usuario.strip(),
        "observacion": observacion.strip(),
    }


# ═══ PDFs de apoyo ═══════════════════════════════════════════════════════════════════


def _pdf(titulo: str) -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, titulo, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    return pdf


def _linea(pdf: FPDF, etiqueta: str, valor) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(55, 6, f"{etiqueta}:", new_x="RIGHT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, str(valor) if valor not in (None, "") else "Pendiente", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)


def _aviso(pdf: FPDF) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(
        0,
        5,
        "AVISO: este documento acredita únicamente la recepción de la denuncia. "
        "No constituye una aprobación del siniestro ni una decisión de cobertura, "
        "indemnización o responsabilidad legal. Documento generado con datos ficticios de práctica.",
        new_x="LMARGIN",
        new_y="NEXT",
    )


def _archivo(nombre: str) -> Path:
    GENERADOS.mkdir(parents=True, exist_ok=True)
    return GENERADOS / nombre


def generar_comprobante(numero_siniestro: str) -> dict:
    """Genera el comprobante de recepción de una denuncia ya registrada."""
    datos = detalle(numero_siniestro)
    if "error" in datos:
        return datos
    siniestro = datos["siniestro"]
    archivo = _archivo(f"comprobante_{siniestro['numero_siniestro']}.pdf")

    pdf = _pdf("COMPROBANTE DE RECEPCION DE DENUNCIA")
    _linea(pdf, "Número de siniestro", siniestro["numero_siniestro"])
    _linea(pdf, "Ramo", siniestro["ramo"])
    _linea(pdf, "Tipo de seguro", siniestro["tipo_seguro"])
    _linea(pdf, "Número de póliza", siniestro["numero_poliza"])
    _linea(pdf, "Fecha del siniestro", f"{siniestro['fecha_siniestro']} {siniestro['hora_siniestro'] or ''}".strip())
    _linea(pdf, "Lugar", siniestro["lugar_siniestro"])
    _linea(pdf, "Asegurado", f"{siniestro['nombre_asegurado']} ({siniestro['documento_asegurado']})")
    _linea(pdf, "Denunciante", f"{siniestro['nombre_denunciante']} ({siniestro['documento_denunciante']})")
    _linea(pdf, "Descripción", siniestro["descripcion_hechos"])
    _linea(pdf, "Personas afectadas", ", ".join(siniestro["datos_afectados"]) or "Sin personas afectadas")
    _linea(pdf, "Lesionados", _si_no(siniestro["existencia_lesionados"]))
    _linea(pdf, "Fallecidos", _si_no(siniestro["existencia_fallecidos"]))
    _linea(pdf, "Daños materiales", siniestro["danos_materiales"])
    _linea(pdf, "Documentación recibida", ", ".join(siniestro["documentacion_recibida"]) or "Ninguna")
    _linea(pdf, "Documentación pendiente", ", ".join(siniestro["documentacion_pendiente"]) or "Ninguna")
    _linea(pdf, "Estado", siniestro["estado"])
    _linea(pdf, "Fecha de registro", siniestro["fecha_registro"])
    _aviso(pdf)
    pdf.output(str(archivo))
    return {
        "archivo": archivo.name,
        "ruta": str(archivo),
        "numero_siniestro": siniestro["numero_siniestro"],
        "aviso": "Comprobante de recepción; no es una aprobación del siniestro.",
    }


def generar_guia(ramo: Ramo) -> dict:
    """Genera una guía con los pasos y los documentos que se piden en un ramo."""
    archivo = _archivo(f"guia_denuncia_{ramo.lower().replace(' ', '_')}.pdf")
    pdf = _pdf(f"GUIA PARA DENUNCIAR UN SINIESTRO - {ramo.upper()}")
    pasos = [
        "1. Reúne la información del hecho: fecha, hora aproximada, lugar y relato de lo ocurrido.",
        "2. Ten a mano los datos del asegurado, del denunciante y de las personas afectadas.",
        "3. Prepara los documentos de la lista siguiente; los que falten quedan como pendientes.",
        "4. Presenta la denuncia por este canal y revisa el resumen antes de confirmarlo.",
        "5. Guarda el número de siniestro: lo necesitas para consultar el seguimiento.",
    ]
    for paso in pasos:
        pdf.multi_cell(0, 6, paso, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Documentos que se acostumbra pedir", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    for documento in documentacion_para(ramo):
        pdf.multi_cell(0, 6, f"- {documento}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Estados de la denuncia", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0,
        6,
        "BORRADOR, PENDIENTE_DE_INFORMACION, REGISTRADO, EN_REVISION, DOCUMENTACION_PENDIENTE, "
        "OBSERVADO, APROBADO, RECHAZADO y CERRADO. El registro de la denuncia no implica aprobación.",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    _aviso(pdf)
    pdf.output(str(archivo))
    return {
        "archivo": archivo.name,
        "ruta": str(archivo),
        "ramo": ramo,
        "aviso": "Guía de orientación; no es un documento oficial de aprobación.",
    }
