"""Router de Reportes — exportación Excel, PDF y resumen estadístico."""
import sys
import io
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from src.models.bitacora_model import BitacoraModel
from src.utils.config import APP_VERSION, APP_NAME
from src.utils.config_manager import DEFAULTS, cargar_config, obtener_clasificaciones_activas
from src.utils.helpers import ordenar_df_por_labor

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF_MIME = "application/pdf"


def _get_flash(request: Request) -> dict:
    return request.session.pop("flash", None) or {}


def _get_empresa_id(request: Request) -> int:
    """Obtiene el empresa_id del usuario actual de la sesión."""
    user = request.session.get("user")
    if user:
        return user.get("empresa_id", 1)
    return 1


# ── Helpers PDF ───────────────────────────────────────────────────────────────

def _crear_estilos_pdf():
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    _PDF_HEADER_BG = colors.HexColor("#1a2540")
    _PDF_ACCENT = colors.HexColor("#1a6fc4")

    base = getSampleStyleSheet()
    estilos = {}
    estilos["titulo"] = ParagraphStyle(
        "PdfTitulo", parent=base["Title"],
        fontSize=14, textColor=_PDF_HEADER_BG,
        spaceAfter=4, alignment=TA_LEFT, fontName="Helvetica-Bold",
    )
    estilos["subtitulo"] = ParagraphStyle(
        "PdfSubtitulo", parent=base["Normal"],
        fontSize=9, textColor=colors.HexColor("#6b7280"),
        spaceAfter=2, alignment=TA_LEFT,
    )
    estilos["seccion"] = ParagraphStyle(
        "PdfSeccion", parent=base["Heading2"],
        fontSize=10, textColor=_PDF_ACCENT,
        spaceBefore=8, spaceAfter=4, fontName="Helvetica-Bold",
    )
    estilos["normal"] = ParagraphStyle(
        "PdfNormal", parent=base["Normal"], fontSize=8, leading=11,
    )
    estilos["header_cell"] = ParagraphStyle(
        "PdfHeaderCell", parent=base["Normal"],
        fontSize=8, leading=11, textColor=colors.white,
        fontName="Helvetica-Bold",
    )
    estilos["pie"] = ParagraphStyle(
        "PdfPie", parent=base["Normal"],
        fontSize=7, textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER,
    )
    return estilos


def _tabla_estilo_principal():
    from reportlab.platypus import TableStyle
    from reportlab.lib import colors

    _PDF_HEADER_BG = colors.HexColor("#1a2540")
    _PDF_HEADER_FG = colors.white
    _PDF_ACCENT = colors.HexColor("#1a6fc4")
    _PDF_ROW_ODD = colors.HexColor("#f0f4f8")
    _PDF_ROW_EVEN = colors.white
    _PDF_GRID = colors.HexColor("#dde3ec")

    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _PDF_HEADER_BG),
        ("TEXTCOLOR",  (0, 0), (-1, 0), _PDF_HEADER_FG),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("FONTSIZE",   (0, 1), (-1, -1), 7),
        ("ALIGN",      (0, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
        ("GRID",       (0, 0), (-1, -1), 0.4, _PDF_GRID),
        ("LINEBELOW",  (0, 0), (-1, 0), 1.5, _PDF_ACCENT),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ])


def _construir_header_pdf(estilos, titulo, lineas_info):
    from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    _PDF_HEADER_BG = colors.HexColor("#1a2540")
    _PDF_ACCENT = colors.HexColor("#1a6fc4")

    elementos = []
    banner_style = ParagraphStyle(
        "Banner", parent=estilos["titulo"],
        textColor=colors.white, fontSize=11,
    )
    tabla_titulo = Table([[Paragraph(titulo, banner_style)]], colWidths=["100%"])
    tabla_titulo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _PDF_HEADER_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    elementos.append(tabla_titulo)
    elementos.append(Spacer(1, 4))
    for linea in lineas_info:
        elementos.append(Paragraph(linea, estilos["subtitulo"]))
    elementos.append(Spacer(1, 3))
    elementos.append(HRFlowable(width="100%", thickness=1, color=_PDF_ACCENT))
    elementos.append(Spacer(1, 6))
    return elementos


def _pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    from reportlab.lib import colors
    canvas.setFillColor(colors.HexColor("#9ca3af"))
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    page_text = f"Página {doc.page}  ·  {APP_NAME} {APP_VERSION}  ·  Generado: {now}"
    canvas.drawCentredString(doc.width / 2 + doc.leftMargin, 20, page_text)
    canvas.restoreState()


def _generar_pdf_bitacora(df, fi_str: str = "", ff_str: str = "") -> bytes:
    """Genera un PDF de la bitácora y devuelve los bytes."""
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import cm

    activas = obtener_clasificaciones_activas()
    estilos = _crear_estilos_pdf()

    cols_clasificacion = [c for c in ["GSI", "RMR"] if c in activas and c in df.columns]
    cols_mostrar = ["Fecha", "Turno", "Labor"] + cols_clasificacion + ["Soporte", "Observaciones"]
    cols_mostrar = [c for c in cols_mostrar if c in df.columns]

    ancho_base = {"Fecha": 60, "Turno": 42, "Labor": 85,
                  "GSI": 34, "RMR": 34,
                  "Soporte": 120, "Observaciones": 120}
    col_widths = [ancho_base.get(c, 60) for c in cols_mostrar]

    periodo = f"{fi_str} — {ff_str}" if fi_str and ff_str else "Completo"
    lineas_info = [
        f"<b>Período:</b> {periodo}",
        f"<b>Total de registros:</b> {len(df)}",
        f"<b>Clasificaciones activas:</b> {' · '.join(activas) if activas else 'Sin clasificación'}",
        f"<b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]

    output = io.BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    header_row = [Paragraph(c, estilos["header_cell"]) for c in cols_mostrar]
    data = [header_row]
    for _, row in df.iterrows():
        data.append([
            Paragraph(str(row.get(c, "") or ""), estilos["normal"])
            for c in cols_mostrar
        ])

    tabla = Table(data, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(_tabla_estilo_principal())

    elementos = _construir_header_pdf(estilos, "Bitácora Geomecánica", lineas_info)
    elementos.append(tabla)

    pdf.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    output.seek(0)
    return output.read()


def _generar_pdf_sostenimiento(df, fi_str: str = "", ff_str: str = "") -> bytes:
    """Genera un PDF de sostenimiento y devuelve los bytes."""
    from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.units import cm

    estilos = _crear_estilos_pdf()

    cols_mostrar = [c for c in df.columns if c != "id"]

    ancho_base = {"Fecha": 58, "Turno": 40, "Labor": 80, "Observaciones": 100,
                  "Tipo_Shotcrete": 50}
    col_widths = [ancho_base.get(c, 55) for c in cols_mostrar]

    periodo = f"{fi_str} — {ff_str}" if fi_str and ff_str else "Completo"
    lineas_info = [
        f"<b>Período:</b> {periodo}",
        f"<b>Total de registros:</b> {len(df)}",
        f"<b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]

    output = io.BytesIO()
    pdf = SimpleDocTemplate(
        output,
        pagesize=landscape(letter),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    header_row = [Paragraph(c.replace("_", " "), estilos["header_cell"]) for c in cols_mostrar]
    data = [header_row]
    for _, row in df.iterrows():
        data.append([
            Paragraph(str(row.get(c, "") or ""), estilos["normal"])
            for c in cols_mostrar
        ])

    tabla = Table(data, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(_tabla_estilo_principal())

    elementos = _construir_header_pdf(estilos, "Sostenimiento Diario", lineas_info)
    elementos.append(tabla)

    pdf.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
    output.seek(0)
    return output.read()


# ── Página de reportes ────────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def reportes_index(request: Request):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    labores_nombres = model.obtener_labores_guardadas()
    flash = _get_flash(request)

    # Resumen estadístico básico
    df_bit = model.obtener_bitacora()
    resumen_bit = {}
    if not df_bit.empty:
        resumen_bit["total"] = len(df_bit)
        if "Turno" in df_bit.columns:
            resumen_bit["por_turno"] = df_bit["Turno"].value_counts().to_dict()
        if "Labor" in df_bit.columns:
            resumen_bit["top_labores"] = df_bit["Labor"].value_counts().head(5).to_dict()

    df_sost = model.obtener_sostenimiento()
    resumen_sost = {}
    if not df_sost.empty:
        resumen_sost["total"] = len(df_sost)
        _cfg = cargar_config()
        campos = _cfg.get("sostenimientos_activos", DEFAULTS["sostenimientos_activos"])
        for c in campos:
            col = c["columna"]
            if col in df_sost.columns:
                try:
                    resumen_sost[c["display"]] = round(float(df_sost[col].sum()), 2)
                except (ValueError, TypeError):
                    pass

    return templates.TemplateResponse(request, "reportes/index.html", context={
        "request": request,
        "app_version": APP_VERSION,
        "labores": labores_nombres,
        "resumen_bit": resumen_bit,
        "resumen_sost": resumen_sost,
        "flash": flash,
        "active_page": "reportes",
    })


# ── Exportar bitácora a Excel ─────────────────────────────────────────────────
@router.get("/exportar/bitacora")
async def exportar_bitacora(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.buscar_registros(
        labor=labor,
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
    )

    output = io.BytesIO()
    with __import__("pandas").ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Bitácora")

    output.seek(0)
    filename = "bitacora_export.xlsx"
    return StreamingResponse(
        output,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Exportar sostenimiento a Excel ────────────────────────────────────────────
@router.get("/exportar/sostenimiento")
async def exportar_sostenimiento(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_sostenimiento(
        fecha=fecha_inicio or None,
        labor=labor or None,
    )

    output = io.BytesIO()
    with __import__("pandas").ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sostenimiento")

    output.seek(0)
    filename = "sostenimiento_export.xlsx"
    return StreamingResponse(
        output,
        media_type=EXCEL_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Exportar bitácora a PDF ───────────────────────────────────────────────────
@router.get("/pdf/bitacora")
async def pdf_bitacora(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.buscar_registros(
        labor=labor,
        fecha_inicio=fecha_inicio or None,
        fecha_fin=fecha_fin or None,
    )
    if not df.empty:
        df = ordenar_df_por_labor(df)

    pdf_bytes = _generar_pdf_bitacora(df, fi_str=fecha_inicio, ff_str=fecha_fin)
    now = datetime.now().strftime("%Y-%m-%d")
    filename = f"bitacora_{now}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type=PDF_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Exportar sostenimiento a PDF ──────────────────────────────────────────────
@router.get("/pdf/sostenimiento")
async def pdf_sostenimiento(
    request: Request,
    fecha_inicio: str = "",
    fecha_fin: str = "",
    labor: str = "",
):
    model = BitacoraModel(empresa_id=_get_empresa_id(request))
    df = model.obtener_sostenimiento(
        fecha=fecha_inicio or None,
        labor=labor or None,
    )

    pdf_bytes = _generar_pdf_sostenimiento(df, fi_str=fecha_inicio, ff_str=fecha_fin)
    now = datetime.now().strftime("%Y-%m-%d")
    filename = f"sostenimiento_{now}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type=PDF_MIME,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

