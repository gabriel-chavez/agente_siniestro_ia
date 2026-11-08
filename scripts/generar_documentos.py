"""Genera los PDFs ficticios de procedimientos que usa el RAG del agente.

Uso:  uv run python scripts/generar_documentos.py
Los archivos se guardan en datos/documentos/. Son material de práctica, no documentos reales.
"""

from pathlib import Path

from fpdf import FPDF

DOCUMENTOS = Path(__file__).resolve().parent.parent / "datos" / "documentos"
PIE = (
    "Documento ficticio elaborado para el ejercicio agente_siniestro_ia. "
    "No es un documento oficial de ninguna aseguradora y no aprueba siniestros."
)


def crear_pdf(nombre: str, titulo: str, secciones: list[tuple[str, list[str]]]) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    pdf.multi_cell(0, 9, titulo, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)
    for subtitulo, parrafos in secciones:
        pdf.set_font("Helvetica", "B", 11)
        pdf.multi_cell(0, 7, subtitulo, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for parrafo in parrafos:
            pdf.multi_cell(0, 6, parrafo, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        pdf.ln(2)
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 5, PIE, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(DOCUMENTOS / nombre))
    print(f"  creado {nombre}")


def main() -> None:
    DOCUMENTOS.mkdir(parents=True, exist_ok=True)

    crear_pdf(
        "manual_denuncia_siniestros.pdf",
        "MANUAL DE RECEPCION DE DENUNCIAS DE SINIESTROS",
        [
            ("1. Alcance", [
                "Este manual orienta la recepcion de denuncias de siniestros de los ramos SOAT, SOATC, "
                "Seguro de Vida, Accidentes Personales y Seguro Automotor.",
                "La denuncia es la declaracion del hecho. El registro es la incorporacion de esa denuncia "
                "al sistema. La evaluacion y la aprobacion son etapas posteriores y no automaticas.",
            ]),
            ("2. Datos minimos de una denuncia", [
                "Ramo y tipo de seguro. Numero de poliza o certificado. Fecha, hora aproximada y lugar del siniestro. "
                "Descripcion de los hechos. Nombre y documento del asegurado y del denunciante. Telefono de contacto. "
                "Personas afectadas, lesionados o fallecidos. Danos materiales. Documentacion disponible.",
                "Cuando un dato no este disponible, se registra como pendiente y se deja constancia. "
                "No se completan datos por suposicion.",
            ]),
            ("3. Pasos del proceso", [
                "Paso 1. El denunciante describe el siniestro en lenguaje natural.",
                "Paso 2. El asistente extrae los datos y pregunta solo por lo que falta.",
                "Paso 3. Se muestra un resumen y se pide confirmacion explicita.",
                "Paso 4. Si el usuario confirma, se registra la denuncia y se genera un numero unico.",
                "Paso 5. Se entrega el comprobante de recepcion y la lista de documentacion pendiente.",
                "Paso 6. El caso pasa a evaluacion. El estado se actualiza solo mediante operaciones autorizadas.",
            ]),
            ("4. Estados de la denuncia", [
                "BORRADOR: informacion inicial, aun no presentada.",
                "PENDIENTE_DE_INFORMACION: registrada con datos o documentos pendientes.",
                "REGISTRADO: denuncia recibida con la informacion minima.",
                "EN_REVISION: el caso esta siendo evaluado.",
                "DOCUMENTACION_PENDIENTE: falta documentacion solicitada.",
                "OBSERVADO: se encontro una observacion que debe subsanarse.",
                "APROBADO, RECHAZADO y CERRADO: resultados de la evaluacion o del cierre del caso.",
            ]),
            ("5. Confidencialidad", [
                "La informacion de los siniestros es confidencial. Se solicita solo lo necesario y no se "
                "revelan datos de otros asegurados. Cada cambio de estado queda en un historial con fecha, "
                "estado anterior, estado nuevo, usuario responsable y motivo.",
            ]),
        ],
    )

    crear_pdf(
        "requisitos_por_ramo.pdf",
        "REQUISITOS DOCUMENTALES POR RAMO",
        [
            ("SOAT", [
                "Formulario de declaracion de siniestro.",
                "Cedula de identidad del denunciante.",
                "Licencia de conducir.",
                "Certificado de SOAT vigente.",
                "Documento del vehiculo.",
                "Parte policial o croquis si hubo colision.",
                "Certificados medicos si hay personas lesionadas.",
            ]),
            ("SOATC", [
                "Los mismos documentos del SOAT.",
                "Certificado de SOATC vigente.",
                "Presupuesto de reparacion del vehiculo.",
            ]),
            ("Seguro de Vida", [
                "Formulario de declaracion de siniestro.",
                "Cedula de identidad del denunciante.",
                "Poliza o certificado de cobertura.",
                "Certificado de defuncion cuando corresponda.",
                "Certificado medico.",
                "Documentos de identificacion de los beneficiarios.",
            ]),
            ("Accidentes Personales", [
                "Formulario de declaracion de siniestro.",
                "Cedula de identidad del denunciante.",
                "Poliza o certificado de cobertura.",
                "Certificado medico.",
                "Radiografias o estudios cuando corresponda.",
                "Facturas de atencion medica.",
                "Denuncia policial si corresponde.",
            ]),
            ("Seguro Automotor", [
                "Formulario de declaracion de siniestro.",
                "Cedula de identidad del denunciante.",
                "Licencia de conducir.",
                "Poliza vigente.",
                "Documento del vehiculo.",
                "Parte policial o denuncia de robo.",
                "Croquis o fotografias de los danos.",
                "Presupuesto de reparacion.",
            ]),
            ("Recomendacion general", [
                "Se solicita primero la documentacion indispensable y el resto queda como pendiente. "
                "La falta de un documento no impide recibir la denuncia: se registra la observacion "
                "y se informa al denunciante que debe completarla.",
            ]),
        ],
    )

    crear_pdf(
        "formulario_declaracion_siniestro.pdf",
        "FORMULARIO DE DECLARACION DE SINIESTRO",
        [
            ("Datos del denunciante", [
                "Nombre completo: ______________________________________________",
                "Documento de identidad: __________________  Telefono: __________________",
                "Relacion con el asegurado: ____________________________________",
            ]),
            ("Datos del asegurado", [
                "Nombre completo: ______________________________________________",
                "Documento de identidad: __________________  Poliza: __________________",
                "Ramo y tipo de seguro: ________________________________________",
            ]),
            ("Datos del siniestro", [
                "Fecha: ____________  Hora aproximada: ____________",
                "Lugar: ________________________________________________________",
                "Descripcion de los hechos: ____________________________________",
                "______________________________________________________________",
                "Personas afectadas: ___________________________________________",
                "Hubo lesionados: Si / No    Hubo fallecidos: Si / No",
                "Danos materiales: _____________________________________________",
                "Datos del vehiculo, si corresponde: ___________________________",
            ]),
            ("Documentacion entregada", [
                "Marcar los documentos adjuntos y anotar los pendientes. "
                "El formulario no acredita la aprobacion del siniestro: solo registra la declaracion.",
            ]),
        ],
    )

    crear_pdf(
        "instructivo_soat.pdf",
        "INSTRUCTIVO PARA DENUNCIAS SOAT Y SOATC",
        [
            ("Que cubre el SOAT", [
                "El SOAT cubre atencion medica y compensaciones por lesiones o fallecimientos causados "
                "en accidentes de transito, dentro de los limites de la poliza. El SOATC amplia la cobertura.",
            ]),
            ("Que hacer despues del accidente", [
                "1. Priorizar la atencion medica de las personas heridas.",
                "2. Registrar la fecha, la hora y el lugar exactos.",
                "3. Anotar los datos de los vehiculos y de las personas involucradas.",
                "4. Solicitar el parte policial o el croquis del hecho.",
                "5. Reunir los certificados medicos de los lesionados.",
            ]),
            ("Documentos para la denuncia", [
                "Formulario de declaracion, cedula de identidad, licencia de conducir, certificado de SOAT "
                "o SOATC vigente, documento del vehiculo, parte policial y certificados medicos.",
            ]),
            ("Importante", [
                "La recepcion de la denuncia no significa que el caso este aprobado. La evaluacion de la "
                "cobertura corresponde al area de siniestros. Este instructivo es material ficticio de practica.",
            ]),
        ],
    )

    crear_pdf(
        "guia_seguimiento_denuncia.pdf",
        "GUIA DE SEGUIMIENTO DE UNA DENUNCIA",
        [
            ("Como consultar", [
                "Se puede buscar una denuncia por numero de siniestro, numero de poliza, documento de identidad, "
                "nombre del asegurado o del denunciante, fecha del siniestro, ramo o estado.",
                "Si la busqueda devuelve varios resultados, se muestra una lista resumida y se pide identificar "
                "el registro que se desea consultar.",
            ]),
            ("Que muestra el seguimiento", [
                "El detalle de la denuncia incluye los datos declarados, la documentacion recibida y pendiente, "
                "el estado actual y el historial de cambios.",
                "Cada cambio de estado registra fecha y hora, estado anterior, estado nuevo, usuario responsable "
                "y la observacion o motivo.",
            ]),
            ("Estados y su significado", [
                "REGISTRADO: la denuncia fue recibida. Aun no implica evaluacion ni aprobacion.",
                "EN_REVISION: el caso esta siendo analizado por el area correspondiente.",
                "DOCUMENTACION_PENDIENTE: se espera documentacion del denunciante.",
                "OBSERVADO: existe una observacion que debe corregirse o aclararse.",
                "APROBADO: la evaluacion concluyo favorablemente.",
                "RECHAZADO: la evaluacion no admitio la cobertura solicitada.",
                "CERRADO: el caso termino y ya no admite cambios.",
            ]),
            ("Recomendaciones", [
                "Guarda el numero de siniestro y el comprobante de recepcion. Consulta el estado con ese numero "
                "y entrega la documentacion pendiente lo antes posible.",
            ]),
        ],
    )


if __name__ == "__main__":
    main()
