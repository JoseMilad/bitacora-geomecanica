"""
Interfaz gráfica de la Bitácora Geomecánica
Separada de la lógica de datos
"""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from tkcalendar import DateEntry
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, KeepTogether
)
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from models.bitacora_model import BitacoraModel
from utils.config import (
    APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_BG_COLOR, TURNOS, PALETTE
)
from utils.helpers import (
    obtener_fecha_actual, validar_rmr, validar_gsi,
    validar_campos_obligatorios, _obtener_turno_automatico,
    ordenar_df_por_labor,
)
from utils.config_manager import cargar_config as _cargar_config
from views.image_annotator import VentanaAnotador

_SECONDS_IN_24H = 86400

# ── Colores para PDFs (alineados con la paleta de la app) ──────────────────
_PDF_HEADER_BG   = colors.HexColor("#1a2540")   # sidebar_bg
_PDF_HEADER_FG   = colors.white
_PDF_ACCENT      = colors.HexColor("#1a6fc4")   # primary
_PDF_ROW_ODD     = colors.HexColor("#f0f4f8")   # surface
_PDF_ROW_EVEN    = colors.white
_PDF_GRID        = colors.HexColor("#dde3ec")   # card_border
_PDF_SUBHEADER   = colors.HexColor("#2d8a6e")   # secondary


def _crear_estilos_pdf():
    """Retorna estilos customizados de párrafo para PDFs."""
    base = getSampleStyleSheet()
    estilos = {}

    estilos["titulo"] = ParagraphStyle(
        "PdfTitulo",
        parent=base["Title"],
        fontSize=16,
        textColor=_PDF_HEADER_BG,
        spaceAfter=4,
        alignment=TA_LEFT,
        fontName="Helvetica-Bold",
    )
    estilos["subtitulo"] = ParagraphStyle(
        "PdfSubtitulo",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
        spaceAfter=2,
        alignment=TA_LEFT,
    )
    estilos["seccion"] = ParagraphStyle(
        "PdfSeccion",
        parent=base["Heading2"],
        fontSize=10,
        textColor=_PDF_ACCENT,
        spaceBefore=8,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    estilos["normal"] = ParagraphStyle(
        "PdfNormal",
        parent=base["Normal"],
        fontSize=8,
        leading=11,
    )
    estilos["pie"] = ParagraphStyle(
        "PdfPie",
        parent=base["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#9ca3af"),
        alignment=TA_CENTER,
    )
    return estilos


def _tabla_estilo_principal(col_widths, header_cols):
    """Retorna el TableStyle estándar para las tablas de datos del PDF."""
    n = len(header_cols) - 1
    style = TableStyle([
        # Encabezado
        ("BACKGROUND",  (0, 0), (n, 0), _PDF_HEADER_BG),
        ("TEXTCOLOR",   (0, 0), (n, 0), _PDF_HEADER_FG),
        ("FONTNAME",    (0, 0), (n, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (n, 0), 8),
        ("ALIGN",       (0, 0), (n, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (n, 0), 7),
        ("TOPPADDING",  (0, 0), (n, 0), 7),
        # Filas de datos
        ("FONTSIZE",    (0, 1), (-1, -1), 7),
        ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
        # Bordes
        ("GRID",        (0, 0), (-1, -1), 0.4, _PDF_GRID),
        ("LINEBELOW",   (0, 0), (n, 0), 1.5, _PDF_ACCENT),
        # Padding
        ("TOPPADDING",  (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ])
    return style


def _construir_bloque_header_pdf(estilos, titulo_principal, lineas_info):
    """
    Construye el bloque de encabezado estándar del PDF:
    barra azul con título + líneas de metadatos + separador.
    Devuelve una lista de elementos Platypus.
    """
    elementos = []

    # Recuadro de título con fondo oscuro usando una tabla de 1 celda
    estilos_banner = ParagraphStyle(
        "Banner", parent=estilos["titulo"],
        textColor=colors.white, fontSize=14
    )
    tabla_titulo = Table(
        [[Paragraph(titulo_principal, estilos_banner)]],
        colWidths=["100%"]
    )
    tabla_titulo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _PDF_HEADER_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 14),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 14),
    ]))
    elementos.append(tabla_titulo)
    elementos.append(Spacer(1, 6))

    # Metadatos
    for linea in lineas_info:
        elementos.append(Paragraph(linea, estilos["subtitulo"]))

    elementos.append(Spacer(1, 4))
    elementos.append(HRFlowable(width="100%", thickness=1.5, color=_PDF_ACCENT))
    elementos.append(Spacer(1, 10))
    return elementos


def _pie_pagina(canvas, doc):
    """Función de pie de página que imprime número de página y timestamp."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#9ca3af"))
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    page_text = f"Página {doc.page}  ·  {APP_NAME} {APP_VERSION}  ·  Generado: {now}"
    canvas.drawCentredString(doc.width / 2 + doc.leftMargin, 20, page_text)
    canvas.restoreState()


def aplicar_hover(btn, color_normal, color_hover):
    """Aplica efecto hover a un botón tkinter cambiando su color de fondo."""
    btn.bind("<Enter>", lambda e: btn.configure(bg=color_hover))
    btn.bind("<Leave>", lambda e: btn.configure(bg=color_normal))


def _aplicar_modo_oscuro_si_activo(ventana: tk.Toplevel):
    """Aplica el modo oscuro a una ventana Toplevel recién creada si está activo en config."""
    try:
        from utils.config_manager import cargar_config
        config = cargar_config()
        if config.get("modo_oscuro", False):
            # Defer a bit so the window is fully built before recoloring
            ventana.after(50, lambda: _aplicar_modo_oscuro(ventana, True))
    except Exception:
        pass


def _make_styled_btn(parent, text, command, style="primary", padx=12, pady=5):
    """Creates a styled tk.Button with PALETTE colors and hover effect."""
    colors_map = {
        "primary":   (PALETTE["primary"],   PALETTE["primary_hover"]),
        "secondary": (PALETTE["secondary"], PALETTE["secondary_hover"]),
        "danger":    (PALETTE["danger"],    PALETTE["danger_hover"]),
    }
    bg, hover = colors_map.get(style, colors_map["primary"])
    b = tk.Button(parent, text=text, command=command,
                  bg=bg, fg="#ffffff", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", padx=padx, pady=pady,
                  activebackground=hover, activeforeground="#ffffff")
    b.bind("<Enter>", lambda e: b.configure(bg=hover))
    b.bind("<Leave>", lambda e: b.configure(bg=bg))
    return b


def _aplicar_estilo_treeview():
    """Applies the Custom.Treeview style (dark heading + clean rows)."""
    style = ttk.Style()
    style.configure("Custom.Treeview.Heading",
        background=PALETTE["sidebar_bg"], foreground="#ffffff",
        font=("Segoe UI", 9, "bold"), relief="flat")
    style.configure("Custom.Treeview",
        rowheight=24, font=("Segoe UI", 9),
        background="#ffffff", fieldbackground="#ffffff")
    style.map("Custom.Treeview",
        background=[("selected", PALETTE["primary"])])


class BitacoraApp:
    """Aplicación principal de la Bitácora Geomecánica"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(800, 600)
        self.root.configure(bg=WINDOW_BG_COLOR)
        
        # Inicializar modelo
        self.model = BitacoraModel()
        
        # Variables de la interfaz
        self.turno_var = tk.StringVar()
        self.labor_var = tk.StringVar()
        self.lista_labores = []
        
        # Crear interfaz
        self._crear_interfaz()
        self._actualizar_labores()

        # Aplicar modo oscuro si está configurado
        from utils.config_manager import cargar_config
        config = cargar_config()
        if config.get("modo_oscuro", False):
            _aplicar_modo_oscuro(self.root, True)
            self.btn_oscuro.config(text="☀ Modo Claro")
    
    def _crear_interfaz(self):
        """Crea la interfaz gráfica principal con sidebar lateral."""
        from utils.config import PALETTE

        # Estilo base
        style = ttk.Style()
        style.theme_use("clam")

        # ── Layout principal: sidebar + content ──────────────────────────
        container = tk.Frame(self.root, bg=PALETTE["sidebar_bg"])
        container.pack(fill="both", expand=True)

        # ─── Sidebar izquierdo ──────────────────────────────────────────
        sidebar = tk.Frame(container, bg=PALETTE["sidebar_bg"], width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo / título en el sidebar
        tk.Label(
            sidebar,
            text="⛏  Bitácora\nGeomecánica",
            font=("Segoe UI", 12, "bold"),
            bg=PALETTE["sidebar_bg"],
            fg="#ffffff",
            pady=14,
            justify="center",
        ).pack(fill="x")

        tk.Frame(sidebar, bg="#2d3a5e", height=1).pack(fill="x", padx=10)

        # Botones del sidebar
        _nav_btns = []

        def _make_nav_btn(text, command):
            btn = tk.Button(
                sidebar,
                text=text,
                font=("Segoe UI", 10),
                bg=PALETTE["sidebar_bg"],
                fg=PALETTE["sidebar_text"],
                activebackground=PALETTE["sidebar_active"],
                activeforeground="#ffffff",
                relief="flat",
                anchor="w",
                padx=14,
                pady=7,
                cursor="hand2",
                command=command,
            )
            btn.pack(fill="x", pady=1)
            aplicar_hover(btn, PALETTE["sidebar_bg"], PALETTE["sidebar_active"])
            _nav_btns.append(btn)
            return btn

        _make_nav_btn("📋  Historial",           self._abrir_historial)
        _make_nav_btn("🪨  Sosten. Diario",      self._abrir_sostenimiento)
        _make_nav_btn("📄  Reporte Diario",      self._generar_reporte)
        _make_nav_btn("📊  Dashboard",            self._abrir_dashboard)
        _make_nav_btn("🏗  Labores",              self._abrir_gestion_labores)
        _make_nav_btn("🔩  Estándar Sosten.",     self._abrir_estandar)
        _make_nav_btn("📷  Registro Fotográfico", self._abrir_anotador_imagen)
        _make_nav_btn("⚙  Configuración",         self._abrir_configuracion)
        _make_nav_btn("📅  Reporte Período",      self._abrir_reporte_periodo)

        tk.Frame(sidebar, bg="#2d3a5e", height=1).pack(fill="x", padx=10, pady=8)

        self.btn_oscuro = tk.Button(
            sidebar,
            text="🌙  Modo Oscuro",
            font=("Segoe UI", 10),
            bg=PALETTE["sidebar_bg"],
            fg=PALETTE["sidebar_text"],
            activebackground=PALETTE["sidebar_active"],
            activeforeground="#ffffff",
            relief="flat",
            anchor="w",
            padx=14,
            pady=7,
            cursor="hand2",
            command=self._toggle_modo_oscuro,
        )
        self.btn_oscuro.pack(fill="x", pady=1)
        aplicar_hover(self.btn_oscuro, PALETTE["sidebar_bg"], PALETTE["sidebar_active"])

        # ─── Panel de contenido derecho ─────────────────────────────────
        content = tk.Frame(container, bg=PALETTE["surface"])
        content.pack(side="left", fill="both", expand=True)

        # Header contextual
        self._header_frame = tk.Frame(content, bg=PALETTE["sidebar_bg"], height=60)
        self._header_frame.pack(fill="x")
        self._header_frame.pack_propagate(False)

        self._lbl_header_title = tk.Label(
            self._header_frame,
            text=f"⛏  BITÁCORA GEOMECÁNICA    v{APP_VERSION}",
            font=("Segoe UI", 13, "bold"),
            bg=PALETTE["sidebar_bg"],
            fg="#ffffff",
            anchor="w",
        )
        self._lbl_header_title.pack(side="left", padx=16, pady=8)

        self._lbl_header_info = tk.Label(
            self._header_frame,
            text="",
            font=("Segoe UI", 9),
            bg=PALETTE["sidebar_bg"],
            fg="#a0b4cc",
            anchor="e",
        )
        self._lbl_header_info.pack(side="right", padx=16, pady=8)
        self._actualizar_header()

        # Scrollable form area
        form_outer = tk.Frame(content, bg=PALETTE["surface"])
        form_outer.pack(fill="both", expand=True, padx=16, pady=12)

        # ─── Card helper ─────────────────────────────────────────────────
        def _make_card(parent, title):
            """Crea un frame estilo 'card' con borde y título."""
            outer = tk.Frame(parent, bg=PALETTE["card_border"], padx=1, pady=1)
            outer.pack(fill="x", pady=6)
            inner = tk.Frame(outer, bg=PALETTE["card_bg"], padx=12, pady=10)
            inner.pack(fill="both", expand=True)
            tk.Label(
                inner,
                text=title,
                font=("Segoe UI", 9, "bold"),
                bg=PALETTE["card_bg"],
                fg=PALETTE["primary"],
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
            return inner

        # ── Card 1: Identificación ────────────────────────────────────────
        card1 = _make_card(form_outer, "Identificación")
        tk.Label(card1, text="Fecha", font=("Segoe UI", 9), bg=PALETTE["card_bg"],
                 fg=PALETTE["text_primary"]).grid(row=1, column=0, sticky="w", padx=(0,8))
        tk.Label(card1, text=obtener_fecha_actual(), font=("Segoe UI", 9, "bold"),
                 bg=PALETTE["card_bg"], fg=PALETTE["text_primary"]).grid(row=1, column=1, sticky="w")

        tk.Label(card1, text="Turno", font=("Segoe UI", 9), bg=PALETTE["card_bg"],
                 fg=PALETTE["text_primary"]).grid(row=2, column=0, sticky="w", padx=(0,8), pady=(4,0))
        combo_turno = ttk.Combobox(card1, textvariable=self.turno_var, state="readonly",
                                    values=TURNOS, width=18)
        combo_turno.grid(row=2, column=1, sticky="ew", pady=(4,0))
        self.turno_var.set(_obtener_turno_automatico())
        card1.columnconfigure(1, weight=1)

        # ── Card 2: Labor ─────────────────────────────────────────────────
        card2 = _make_card(form_outer, "Labor")
        tk.Label(card2, text="Labor", font=("Segoe UI", 9), bg=PALETTE["card_bg"],
                 fg=PALETTE["text_primary"]).grid(row=1, column=0, sticky="w", padx=(0,8))
        self.entrada_labor = ttk.Entry(card2, textvariable=self.labor_var, width=28)
        self.entrada_labor.grid(row=1, column=1, sticky="ew")
        self.entrada_labor.bind("<KeyRelease>", self._filtrar_labores)
        self.entrada_labor.bind("<FocusIn>",    self._filtrar_labores)
        self.entrada_labor.bind("<FocusOut>",   self._ocultar_lista)
        self.labor_var.trace_add("write", self._labor_a_mayusculas)

        self.lista_filtrada = tk.Listbox(card2, height=5, exportselection=False)
        self.lista_filtrada.grid(row=2, column=1, sticky="ew")
        self.lista_filtrada.bind("<<ListboxSelect>>", self._seleccionar_labor_lista)
        self.lista_filtrada.grid_remove()

        self.label_ultimo = tk.Label(card2, text="", font=("Segoe UI", 8),
                                     bg=PALETTE["card_bg"], fg=PALETTE["text_muted"])
        self.label_ultimo.grid(row=2, column=0, sticky="w", pady=2)
        card2.columnconfigure(1, weight=1)

        # ── Card 3: Geomecánica ───────────────────────────────────────────
        self._card3 = _make_card(form_outer, "Geomecánica")

        # GSI entry (always created; shown/hidden by _actualizar_campos_clasificacion)
        self._lbl_gsi = tk.Label(self._card3, text="GSI", font=("Segoe UI", 9),
                                 bg=PALETTE["card_bg"], fg=PALETTE["text_primary"])
        self._lbl_gsi.grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.entrada_gsi = ttk.Entry(self._card3, width=18)
        self.entrada_gsi.grid(row=1, column=1, sticky="ew")
        self.entrada_gsi.bind("<KeyRelease>", lambda e: self._a_mayusculas_entry(self.entrada_gsi))

        # RMR entry (always created; shown/hidden by _actualizar_campos_clasificacion)
        self._lbl_rmr = tk.Label(self._card3, text="RMR", font=("Segoe UI", 9),
                                 bg=PALETTE["card_bg"], fg=PALETTE["text_primary"])
        self._lbl_rmr.grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        self.entrada_rmr = ttk.Entry(self._card3, width=18)
        self.entrada_rmr.grid(row=2, column=1, sticky="ew", pady=(4, 0))
        self.entrada_rmr.bind("<KeyRelease>",
                              lambda e: (self._a_mayusculas_entry(self.entrada_rmr),
                                         self._calcular_soporte(e)))

        # Soporte recomendado (always shown)
        self._lbl_soporte = tk.Label(self._card3, text="Soporte recomendado",
                                     font=("Segoe UI", 9), bg=PALETTE["card_bg"],
                                     fg=PALETTE["text_primary"])
        self._lbl_soporte.grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(4, 0))
        self.entrada_soporte = ttk.Entry(self._card3, width=18)
        self.entrada_soporte.grid(row=3, column=1, sticky="ew", pady=(4, 0))
        self.entrada_soporte.bind("<KeyRelease>", lambda e: self._a_mayusculas_entry(self.entrada_soporte))
        self._card3.columnconfigure(1, weight=1)

        # Apply visibility based on current config
        self._actualizar_campos_clasificacion()

        # ── Card 4: Observaciones ─────────────────────────────────────────
        card4 = _make_card(form_outer, "Observaciones")
        self.entrada_obs = tk.Text(
            card4, height=4, width=30,
            font=("Segoe UI", 10),
            relief="flat", borderwidth=1,
            highlightthickness=1,
            highlightbackground=PALETTE["card_border"],
            highlightcolor=PALETTE["primary"],
            wrap="word",
        )
        self.entrada_obs.grid(row=1, column=0, sticky="ew")
        card4.columnconfigure(0, weight=1)

        # ── Card 5: Registro Fotográfico ─────────────────────────────────
        card5 = _make_card(form_outer, "Registro Fotográfico")
        self._imagen_path = ""
        self._lbl_imagen = tk.Label(
            card5, text="Sin imagen adjunta",
            font=("Segoe UI", 9),
            bg=PALETTE["card_bg"],
            fg=PALETTE["text_muted"],
        )
        self._lbl_imagen.grid(row=1, column=0, sticky="w", padx=(0, 8))

        btn_img = tk.Button(
            card5,
            text="📷 Adjuntar / Anotar imagen",
            font=("Segoe UI", 9, "bold"),
            bg=PALETTE["secondary"],
            fg="#ffffff",
            activebackground=PALETTE["secondary_hover"],
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=4,
            command=self._abrir_anotador_para_registro,
        )
        btn_img.grid(row=1, column=1, sticky="e", padx=(8, 0))
        aplicar_hover(btn_img, PALETTE["secondary"], PALETTE["secondary_hover"])
        card5.columnconfigure(0, weight=1)

        # ── Botón principal guardar ──────────────────────────────────────
        btn_frame = tk.Frame(content, bg=PALETTE["surface"])
        btn_frame.pack(fill="x", padx=16, pady=(0, 8))

        self._btn_guardar = tk.Button(
            btn_frame,
            text="💾  Guardar Registro",
            font=("Segoe UI", 11, "bold"),
            bg=PALETTE["primary"],
            fg="#ffffff",
            activebackground=PALETTE["primary_hover"],
            activeforeground="#ffffff",
            relief="flat",
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._guardar_datos,
        )
        self._btn_guardar.pack(fill="x")
        aplicar_hover(self._btn_guardar, PALETTE["primary"], PALETTE["primary_hover"])

        # ── Status bar inferior ──────────────────────────────────────────
        status_bar = tk.Frame(self.root, bg="#e8edf2", height=24)
        status_bar.pack(fill="x", side="bottom")
        status_bar.pack_propagate(False)

        self._lbl_status_file = tk.Label(
            status_bar,
            text="",
            font=("Segoe UI", 8),
            bg="#e8edf2",
            fg=PALETTE["text_muted"],
            anchor="w",
        )
        self._lbl_status_file.pack(side="left", padx=8)

        self._lbl_status_time = tk.Label(
            status_bar,
            text="",
            font=("Segoe UI", 8),
            bg="#e8edf2",
            fg=PALETTE["text_muted"],
            anchor="e",
        )
        self._lbl_status_time.pack(side="right", padx=8)
        self._actualizar_status_bar()

    # ── Utilidades de transformación de texto ────────────────────────────────

    @staticmethod
    def _a_mayusculas_entry(entry: ttk.Entry):
        """Convierte el contenido de un Entry de ttk a mayúsculas manteniendo la posición del cursor."""
        try:
            pos = entry.index(tk.INSERT)
            val = entry.get()
            upper = val.upper()
            if val != upper:
                entry.delete(0, tk.END)
                entry.insert(0, upper)
                entry.icursor(pos)
        except Exception:
            pass

    def _labor_a_mayusculas(self, *_):
        """Trace callback que convierte labor_var a mayúsculas."""
        val = self.labor_var.get()
        upper = val.upper()
        if val != upper:
            self.labor_var.set(upper)

    def _actualizar_header(self):
        """Actualiza el header contextual con fecha, turno y registros."""
        from utils.helpers import obtener_fecha_actual
        # Cancel any previous scheduled callback to avoid accumulation
        after_id = getattr(self, "_after_header", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        try:
            turno = self.turno_var.get() or "—"
        except Exception:
            turno = "—"
        try:
            n = len(self.model.obtener_bitacora())
        except Exception:
            n = 0
        fecha = obtener_fecha_actual()
        self._lbl_header_info.config(
            text=f"📅 {fecha}  |  Turno: {turno}  |  Registros: {n}"
        )
        self._after_header = self.root.after(60000, self._actualizar_header)

    def _actualizar_status_bar(self):
        """Actualiza la barra de estado inferior."""
        from utils.config import ARCHIVO_BITACORA
        import datetime
        # Cancel any previous scheduled callback to avoid accumulation
        after_id = getattr(self, "_after_status", None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        hora = datetime.datetime.now().strftime("%H:%M")
        archivo = str(ARCHIVO_BITACORA)
        self._lbl_status_file.config(text=f"Archivo: {archivo}")
        self._lbl_status_time.config(text=f"🕐 {hora}")
        self._after_status = self.root.after(60000, self._actualizar_status_bar)

    def _actualizar_campos_clasificacion(self):
        """Muestra u oculta los campos de clasificación según la configuración activa."""
        from utils.config_manager import obtener_clasificaciones_activas
        activas = obtener_clasificaciones_activas()

        gsi_visible = "GSI" in activas
        rmr_visible = "RMR" in activas

        if hasattr(self, "_lbl_gsi") and hasattr(self, "entrada_gsi"):
            if gsi_visible:
                self._lbl_gsi.grid()
                self.entrada_gsi.grid()
            else:
                self._lbl_gsi.grid_remove()
                self.entrada_gsi.grid_remove()
                self.entrada_gsi.delete(0, tk.END)

        if hasattr(self, "_lbl_rmr") and hasattr(self, "entrada_rmr"):
            if rmr_visible:
                self._lbl_rmr.grid()
                self.entrada_rmr.grid()
            else:
                self._lbl_rmr.grid_remove()
                self.entrada_rmr.grid_remove()
                self.entrada_rmr.delete(0, tk.END)

    def _guardar_datos(self):
        """Guarda un nuevo registro"""
        from utils.validators import ValidadorBitacora
        from utils.logger import LoggerBitacora
    
        # Preparar datos
        datos = {
            "Fecha": obtener_fecha_actual(),
            "Turno": self.turno_var.get(),
            "Labor": ValidadorBitacora.sanitizar_entrada(self.labor_var.get()),
            "GSI": self.entrada_gsi.get().strip(),
            "RMR": self.entrada_rmr.get().strip(),
            "Soporte": ValidadorBitacora.sanitizar_entrada(self.entrada_soporte.get()),
            "Observaciones": ValidadorBitacora.sanitizar_entrada(self.entrada_obs.get("1.0", tk.END)),
            "imagen_path": self._imagen_path,
        }
    
        # Validar registro completo
        valido, mensaje = ValidadorBitacora.validar_registro_completo(datos)
    
        if not valido:
            LoggerBitacora.registrar_validacion_fallida("registro_completo", str(datos), mensaje)
            messagebox.showerror("Error de validación", mensaje)
            return
    
        try:
            # Guardar con modelo
            exito, mensaje = self.model.guardar_registro(datos)
        
            if exito:
                LoggerBitacora.registrar_guardar_registro(datos)
                try:
                    from utils.toast import mostrar_toast
                    mostrar_toast(self.root, mensaje, tipo="success")
                except Exception:
                    messagebox.showinfo("Resultado", mensaje)
                self._limpiar_campos()
                self._actualizar_labores()
            elif "DUPLICADO" in mensaje:
                confirmar = messagebox.askyesno(
                    "Registro duplicado",
                    "Ya existe un registro para esta labor en este turno y fecha.\n"
                    "¿Desea guardar de todas formas?"
                )
                if confirmar:
                    exito2, msg2 = self.model.guardar_registro_forzado(datos)
                    if exito2:
                        LoggerBitacora.registrar_guardar_registro(datos)
                        try:
                            from utils.toast import mostrar_toast
                            mostrar_toast(self.root, msg2, tipo="success")
                        except Exception:
                            messagebox.showinfo("Resultado", msg2)
                        self._limpiar_campos()
                        self._actualizar_labores()
                    else:
                        messagebox.showerror("Error", msg2)
            else:
                messagebox.showerror("Error", mensaje)
                LoggerBitacora.registrar_error("guardar_registro", Exception(mensaje))
        except Exception as e:
            LoggerBitacora.registrar_error("guardar_registro", e)
            messagebox.showerror("Error", f"Error al guardar: {str(e)}")
    
    def _limpiar_campos(self):
        """Limpia todos los campos de entrada"""
        self.entrada_gsi.delete(0, tk.END)
        self.entrada_rmr.delete(0, tk.END)
        self.entrada_soporte.delete(0, tk.END)
        self.entrada_obs.delete("1.0", tk.END)
        # Limpiar imagen adjunta
        self._imagen_path = ""
        self._lbl_imagen.config(text="Sin imagen adjunta", fg=PALETTE["text_muted"])
        # Refrescar header
        try:
            self._actualizar_header()
        except Exception:
            pass
    
    def _actualizar_labores(self):
        """Actualiza la lista de labores disponibles"""
        self.lista_labores = self.model.obtener_labores_guardadas()

    def _filtrar_labores(self, event):
        """Filtra labores según texto escrito y muestra la lista desplegable"""
        texto = self.labor_var.get()
        self.lista_filtrada.delete(0, tk.END)

        if texto == "":
            resultados = self.lista_labores
        else:
            resultados = [l for l in self.lista_labores if texto.lower() in l.lower()]

        if resultados:
            for labor in resultados:
                self.lista_filtrada.insert(tk.END, labor)
            self.lista_filtrada.grid()
        else:
            self.lista_filtrada.grid_remove()

    def _seleccionar_labor_lista(self, event):
        """Selecciona labor desde la lista filtrada"""
        seleccion = self.lista_filtrada.curselection()
        if not seleccion:
            return
        labor = self.lista_filtrada.get(seleccion[0])
        self.labor_var.set(labor)
        self.lista_filtrada.grid_remove()
        self._cargar_datos_labor(labor)

    def _ocultar_lista(self, event):
        """Oculta la lista al perder el foco (con pequeño delay para permitir selección)"""
        self.root.after(150, self._verificar_ocultar)

    def _verificar_ocultar(self):
        """Oculta la lista si el foco no está en ella"""
        try:
            widget_foco = self.root.focus_get()
            if widget_foco != self.lista_filtrada:
                self.lista_filtrada.grid_remove()
        except Exception:
            self.lista_filtrada.grid_remove()

    def _cargar_datos_labor(self, labor):
        """
        Al seleccionar una labor, carga el último registro de la bitácora.
        Si no hay registros previos, intenta cargar datos del catálogo de labores.
        """
        import pandas as pd

        def es_valor_valido(valor):
            """Retorna True si el valor no es vacío ni NaN"""
            if valor is None:
                return False
            try:
                if pd.isna(valor):
                    return False
            except (TypeError, ValueError):
                pass
            return str(valor).strip() not in ("", "nan")

        # Primero intentar el último registro real de la bitácora
        registro = self.model.obtener_ultimo_registro_labor(labor)

        if registro:
            self.entrada_gsi.delete(0, tk.END)
            if es_valor_valido(registro.get("GSI")):
                self.entrada_gsi.insert(0, str(registro["GSI"]))

            self.entrada_rmr.delete(0, tk.END)
            if es_valor_valido(registro.get("RMR")):
                self.entrada_rmr.insert(0, str(registro["RMR"]))

            self.entrada_soporte.delete(0, tk.END)
            if es_valor_valido(registro.get("Soporte")):
                self.entrada_soporte.insert(0, str(registro["Soporte"]))

            if hasattr(self, 'label_ultimo'):
                self.label_ultimo.config(
                    text=f"Último registro: {registro.get('Fecha')} | "
                         f"Turno {registro.get('Turno')} | "
                         f"RMR {registro.get('RMR')}"
                )
        else:
            # Si no hay registro en la bitácora, intentar datos del catálogo
            datos = self.model.obtener_datos_labor(labor)
            if datos:
                self.entrada_gsi.delete(0, tk.END)
                if es_valor_valido(datos.get("GSI")):
                    self.entrada_gsi.insert(0, str(datos["GSI"]))

                self.entrada_rmr.delete(0, tk.END)
                if es_valor_valido(datos.get("RMR")):
                    self.entrada_rmr.insert(0, str(datos["RMR"]))
                    try:
                        rmr_val = validar_rmr(str(datos["RMR"]))
                        if rmr_val is not None:
                            tipo = str(datos.get("Tipo", "Temporal"))
                            soporte = self.model.recomendar_soporte(rmr_val, tipo=tipo)
                            self.entrada_soporte.delete(0, tk.END)
                            self.entrada_soporte.insert(0, soporte)
                    except Exception:
                        pass

                if hasattr(self, 'label_ultimo'):
                    tipo = datos.get("Tipo", "")
                    self.label_ultimo.config(text=f"Tipo: {tipo}" if es_valor_valido(tipo) else "Sin registros previos")
            else:
                if hasattr(self, 'label_ultimo'):
                    self.label_ultimo.config(text="Sin registros previos")

    def _seleccionar_labor(self, event):
        """Selecciona una labor y carga sus datos técnicos"""
        labor = self.labor_var.get()
        if labor:
            self._cargar_ultimo_registro(labor)
    
    def _cargar_ultimo_registro(self, labor):
        """Carga el último registro de una labor"""
        registro = self.model.obtener_ultimo_registro_labor(labor)
        
        if not registro:
            return
        
        self.entrada_gsi.delete(0, tk.END)
        self.entrada_gsi.insert(0, str(registro.get("GSI", "")))
        
        self.entrada_rmr.delete(0, tk.END)
        self.entrada_rmr.insert(0, str(registro.get("RMR", "")))
        
        self.entrada_soporte.delete(0, tk.END)
        self.entrada_soporte.insert(0, str(registro.get("Soporte", "")))
        
        if hasattr(self, 'label_ultimo'):
            self.label_ultimo.config(
                text=f"Último registro: {registro.get('Fecha')} | "
                     f"Turno {registro.get('Turno')} | "
                     f"RMR {registro.get('RMR')}"
            )
    
    def _abrir_gestion_labores(self):
        """Abre la ventana de gestión de labores"""
        VentanaLabores(self.root, self.model, self._actualizar_labores)
    
    def _calcular_soporte(self, event):
        """Calcula automáticamente el soporte según clasificaciones activas"""
        try:
            from utils.config_manager import obtener_clasificaciones_activas

            rmr = validar_rmr(self.entrada_rmr.get())
            if rmr is None:
                return

            # Intentar obtener el tipo de labor seleccionada
            tipo = "Temporal"
            labor = self.labor_var.get().strip()
            if labor:
                datos_labor = self.model.obtener_datos_labor(labor)
                if datos_labor:
                    tipo_raw = datos_labor.get("Tipo")
                    try:
                        import pandas as pd
                        tipo_es_valido = tipo_raw and not pd.isna(tipo_raw) and str(tipo_raw).strip() not in ("", "nan")
                    except (TypeError, ValueError):
                        tipo_es_valido = bool(tipo_raw and str(tipo_raw).strip() not in ("", "nan"))
                    if tipo_es_valido:
                        tipo = str(tipo_raw)

            # Intentar cada clasificación activa hasta encontrar recomendación
            activas = obtener_clasificaciones_activas()
            partes = []
            for sistema in activas:
                if sistema == "RMR" and rmr is not None:
                    rec = self.model.recomendar_soporte(rmr, tipo=tipo, sistema="RMR")
                    if rec:
                        partes.append(rec)
            # Si hay resultado, usar el primero encontrado
            soporte = partes[0] if partes else ""
            self.entrada_soporte.delete(0, tk.END)
            self.entrada_soporte.insert(0, soporte)
        except Exception:
            pass
    
    def _abrir_historial(self):
        """Abre ventana de historial"""
        VentanaHistorial(self.root, self.model)
    
    def _abrir_estandar(self):
        """Abre ventana de estándar de sostenimiento"""
        VentanaEstandar(self.root, self.model)

    def _abrir_sostenimiento(self):
        """Abre ventana de sostenimiento diario"""
        VentanaSostenimiento(self.root, self.model)

    def _abrir_dashboard(self):
        """Abre el dashboard de sostenimiento"""
        VentanaDashboard(self.root, self.model)

    def _abrir_configuracion(self):
        """Abre el panel de configuración"""
        def _al_cerrar():
            # Recargar configuración al cerrar
            from utils.config_manager import cargar_config
            config = cargar_config()
            color = config.get("theme_color", WINDOW_BG_COLOR)
            self.root.configure(bg=color)
            # Actualizar campos de clasificación según nueva configuración
            self._actualizar_campos_clasificacion()

        VentanaConfiguracion(self.root, _al_cerrar)

    def _abrir_sostenimientos(self):
        """Abre la ventana de gestión de sostenimientos"""
        VentanaSostenimientos(self.root)

    def _abrir_reporte_periodo(self):
        """Abre la ventana de reporte por período"""
        VentanaReportePeriodo(self.root, self.model)

    def _abrir_anotador_imagen(self):
        """Abre la ventana de registro fotográfico vinculado a labores."""
        VentanaRegistroFotografico(self.root, self.model)

    def _abrir_anotador_para_registro(self):
        """Abre el anotador de imágenes y vincula el resultado al registro actual."""
        from pathlib import Path as _Path

        labor = self.labor_var.get().strip() or None

        def _on_imagen_guardada(path):
            self._imagen_path = path
            nombre = _Path(path).name
            self._lbl_imagen.config(text=f"📎 {nombre}", fg=PALETTE["success"])

        # Si ya hay una imagen, abrir para editar
        if self._imagen_path:
            VentanaAnotador(self.root, image_path=self._imagen_path,
                            callback=_on_imagen_guardada, labor_name=labor)
        else:
            VentanaAnotador(self.root, callback=_on_imagen_guardada, labor_name=labor)

    def _toggle_modo_oscuro(self):
        """Alterna entre modo oscuro y claro"""
        from utils.config_manager import cargar_config, guardar_config
        config = cargar_config()
        modo_oscuro = not config.get("modo_oscuro", False)
        config["modo_oscuro"] = modo_oscuro
        guardar_config(config)
        _aplicar_modo_oscuro(self.root, modo_oscuro)
        self.btn_oscuro.config(text="☀ Modo Claro" if modo_oscuro else "🌙 Modo Oscuro")
    
    def _generar_reporte(self):
        """Genera reporte PDF del día, con vista previa"""
        df = self.model.obtener_bitacora()
        fecha_hoy = obtener_fecha_actual()
        
        df_hoy = df[df["Fecha"] == fecha_hoy]
        
        if df_hoy.empty:
            messagebox.showinfo("Info", "No hay registros hoy")
            return

        _mostrar_vista_previa(
            self.root,
            df_hoy,
            titulo=f"Vista Previa — Reporte Diario {fecha_hoy}",
            callback_confirmar=lambda: self._generar_pdf_diario(df_hoy, fecha_hoy)
        )
    
    def _generar_pdf_diario(self, df, fecha):
        """Genera PDF con registros del día – con diseño visual mejorado."""
        from utils.config_manager import obtener_clasificaciones_activas
        fecha_archivo = datetime.now().strftime("%d-%m-%Y")
        nombre_archivo = f"reporte_geomecanica_{fecha_archivo}.pdf"

        estilos = _crear_estilos_pdf()
        activas = obtener_clasificaciones_activas()

        # Ordenar por labor numéricamente
        df = ordenar_df_por_labor(df)

        # Columnas a incluir: Fecha ya está en el encabezado, no repetir en tabla
        cols_clasificacion = [c for c in ["GSI", "RMR"] if c in activas and c in df.columns]
        cols_mostrar = ["Turno", "Labor"] + cols_clasificacion + ["Soporte", "Observaciones"]
        cols_mostrar = [c for c in cols_mostrar if c in df.columns]

        # Anchos de columna (ajustados al tamaño de hoja carta apaisada)
        ancho_base = {"Turno": 44, "Labor": 100,
                      "GSI": 36, "RMR": 36,
                      "Soporte": 145, "Observaciones": 145}
        col_widths = [ancho_base.get(c, 60) for c in cols_mostrar]

        pdf = SimpleDocTemplate(
            nombre_archivo,
            pagesize=landscape(letter),
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        elementos = []

        # ── Encabezado ───────────────────────────────────────────────────
        clasificaciones_texto = " · ".join(activas) if activas else "Sin clasificación"
        lineas_info = [
            f"<b>Fecha del reporte:</b> {fecha}",
            f"<b>Turno:</b> {df['Turno'].iloc[0] if 'Turno' in df.columns and not df.empty else '—'}  "
            f"<b>Total de registros:</b> {len(df)}",
            f"<b>Clasificaciones activas:</b> {clasificaciones_texto}",
        ]
        elementos += _construir_bloque_header_pdf(estilos, "⛏  REPORTE DIARIO GEOMECÁNICA", lineas_info)

        # ── Tabla principal ──────────────────────────────────────────────
        encabezado = cols_mostrar[:]
        datos = [encabezado]
        for _, row in df.iterrows():
            fila = []
            for col in cols_mostrar:
                val = str(row[col]) if str(row[col]) != "nan" else ""
                if col in ("Soporte", "Observaciones"):
                    fila.append(Paragraph(val, estilos["normal"]))
                else:
                    fila.append(val)
            datos.append(fila)

        tabla = Table(datos, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(_tabla_estilo_principal(col_widths, encabezado))
        elementos.append(tabla)
        elementos.append(Spacer(1, 28))

        # ── Resumen estadístico ──────────────────────────────────────────
        elementos.append(Paragraph("Resumen del día", estilos["seccion"]))
        elementos.append(HRFlowable(width="100%", thickness=0.5, color=_PDF_GRID))
        elementos.append(Spacer(1, 6))

        if "Turno" in df.columns:
            by_turno = df["Turno"].value_counts()
            resumen_rows = [["Turno", "Registros"]]
            for t, n in by_turno.items():
                resumen_rows.append([str(t), str(n)])
            tbl_res = Table(resumen_rows, colWidths=[100, 60])
            tbl_res.setStyle(TableStyle([
                ("BACKGROUND",  (0, 0), (-1, 0), _PDF_SUBHEADER),
                ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",    (0, 0), (-1, -1), 8),
                ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
                ("GRID",        (0, 0), (-1, -1), 0.4, _PDF_GRID),
                ("TOPPADDING",  (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            elementos.append(tbl_res)
            elementos.append(Spacer(1, 20))

        # ── Firmas ───────────────────────────────────────────────────────
        firma_style = ParagraphStyle("Firma", fontSize=8, alignment=TA_CENTER,
                                     textColor=colors.HexColor("#374151"))
        firma_linea = HRFlowable(width="40%", thickness=0.8, color=colors.HexColor("#374151"))
        firma_tabla = Table(
            [
                [firma_linea, firma_linea],
                [Paragraph("Geomecánica", firma_style), Paragraph("Supervisor", firma_style)],
            ],
            colWidths=["45%", "45%"],
            hAlign="CENTER",
        )
        firma_tabla.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(firma_tabla)

        pdf.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
        messagebox.showinfo("PDF", f"Reporte diario generado:\n{nombre_archivo}")


class VentanaHistorial:
    """Ventana para ver historial de registros"""
    
    def __init__(self, parent, model):
        self.model = model
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Historial de Labores")
        self.ventana.geometry("900x600")
        self.ventana.minsize(750, 450)
        self.ventana.configure(bg=PALETTE["surface"])
        self._df_actual = None
        self._indices_originales = []
        self._todos_registros = None  # cache para búsqueda global
        
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self.ventana)
    
    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de historial"""
        # Header
        header = tk.Frame(self.ventana, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📋 Historial de Registros",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Custom Treeview style
        _aplicar_estilo_treeview()

        # Frame de búsqueda
        frame_busqueda = tk.Frame(self.ventana, bg=PALETTE["surface"])
        frame_busqueda.pack(pady=5, padx=10, fill="x")
        
        for i in range(6):
            frame_busqueda.columnconfigure(i, weight=1)
        
        # Variables
        self.buscar_var = tk.StringVar()
        self.fecha_inicio_var = tk.StringVar()
        self.fecha_fin_var = tk.StringVar()
        self.busqueda_global_var = tk.StringVar()
        
        # Búsqueda por labor y fechas
        ttk.Label(frame_busqueda, text="Buscar Labor:").grid(row=0, column=0, padx=5, pady=4)
        entrada_buscar = ttk.Entry(frame_busqueda, textvariable=self.buscar_var, width=20)
        entrada_buscar.grid(row=0, column=1, padx=5, pady=4)
        entrada_buscar.bind("<KeyRelease>", lambda e: self._buscar_labor())
        
        ttk.Label(frame_busqueda, text="Desde:").grid(row=0, column=2, padx=5, pady=4)
        entrada_inicio = DateEntry(
            frame_busqueda,
            textvariable=self.fecha_inicio_var,
            date_pattern="dd/mm/yyyy",
            width=12
        )
        entrada_inicio.grid(row=0, column=3, padx=5, pady=4)
        entrada_inicio.bind("<<DateEntrySelected>>", lambda e: self._buscar_labor())
        
        ttk.Label(frame_busqueda, text="Hasta:").grid(row=0, column=4, padx=5, pady=4)
        entrada_fin = DateEntry(
            frame_busqueda,
            textvariable=self.fecha_fin_var,
            date_pattern="dd/mm/yyyy",
            width=12
        )
        entrada_fin.grid(row=0, column=5, padx=5, pady=4)
        entrada_fin.bind("<<DateEntrySelected>>", lambda e: self._buscar_labor())

        # Buscador global (fila 1)
        frame_global = tk.Frame(self.ventana, bg=PALETTE["surface"])
        frame_global.pack(padx=10, fill="x")
        ttk.Label(frame_global, text="🔍 Búsqueda global:").pack(side="left", padx=5)
        entrada_global = ttk.Entry(frame_global, textvariable=self.busqueda_global_var, width=35)
        entrada_global.pack(side="left", padx=5)
        entrada_global.bind("<KeyRelease>", lambda e: self._filtrar_global())
        self.lbl_contador = ttk.Label(frame_global, text="")
        self.lbl_contador.pack(side="left", padx=10)
        
        # Tabla
        columnas = ["Fecha", "Turno", "Labor", "GSI", "RMR", "Soporte", "Observaciones"]
        self.tabla = ttk.Treeview(
            self.ventana,
            columns=columnas,
            show="headings",
            height=14,
            style="Custom.Treeview",
        )
        self.tabla.tag_configure("odd", background="#f7f9fc")
        self.tabla.tag_configure("even", background="#ffffff")
        
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, anchor="center")
        
        self.tabla.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        # Botones
        frame_botones = tk.Frame(self.ventana, bg=PALETTE["surface"])
        frame_botones.pack(pady=8)

        def _place(text, command, style="primary"):
            b = _make_styled_btn(frame_botones, text, command, style=style, padx=10, pady=4)
            b.pack(side="left", padx=4)
            return b

        _place("✏ Editar",        self._editar_registro,  "primary")
        _place("🗑 Eliminar",      self._eliminar_registro, "danger")
        _place("📊 Excel",         self._exportar_excel,    "secondary")
        _place("📄 PDF",           self._exportar_pdf,      "secondary")
        self.btn_deshacer = _place("↩ Deshacer", self._deshacer, "primary")
        _place("📦 Archivar",      self._archivar_periodo,  "primary")
        _place("✕ Cerrar",         self.ventana.destroy,    "danger")
        
        self._buscar_labor()
    
    def _buscar_labor(self):
        """Busca registros según filtros y guarda los índices originales"""
        labor = self.buscar_var.get()
        fecha_inicio = self.fecha_inicio_var.get()
        fecha_fin = self.fecha_fin_var.get()
        
        df = self.model.buscar_registros(labor, fecha_inicio, fecha_fin)
        self._df_actual = df.copy()
        self._todos_registros = df.copy()
        self._indices_originales = list(df.index)
        
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        
        for i, (_, row) in enumerate(df.iterrows()):
            tag = "odd" if i % 2 == 0 else "even"
            self.tabla.insert("", "end", values=list(row), tags=(tag,))

        total = len(df)
        self.lbl_contador.config(text=f"Mostrando {total} de {total} registros")

    def _filtrar_global(self):
        """Filtra todos los registros visibles en tiempo real por texto en todas las columnas."""
        texto = self.busqueda_global_var.get().strip().lower()
        if self._todos_registros is None:
            return

        for fila in self.tabla.get_children():
            self.tabla.delete(fila)

        if not texto:
            df_filtrado = self._todos_registros
        else:
            mask = self._todos_registros.apply(
                lambda row: any(texto in str(v).lower() for v in row), axis=1
            )
            df_filtrado = self._todos_registros[mask]

        self._df_actual = df_filtrado.copy()
        self._indices_originales = list(df_filtrado.index)

        for i, (_, row) in enumerate(df_filtrado.iterrows()):
            tag = "odd" if i % 2 == 0 else "even"
            self.tabla.insert("", "end", values=list(row), tags=(tag,))

        total_all = len(self._todos_registros)
        total_vis = len(df_filtrado)
        self.lbl_contador.config(text=f"Mostrando {total_vis} de {total_all} registros")

    def _obtener_indice_seleccionado(self):
        """Devuelve el índice real del DataFrame para la fila seleccionada"""
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Seleccione un registro", parent=self.ventana)
            return None
        pos = self.tabla.index(seleccion[0])
        if pos >= len(self._indices_originales):
            return None
        return self._indices_originales[pos]

    def _editar_registro(self):
        """Abre ventana emergente para editar el registro seleccionado"""
        indice = self._obtener_indice_seleccionado()
        if indice is None:
            return

        seleccion = self.tabla.selection()
        valores = self.tabla.item(seleccion[0])["values"]

        # Verificar modo solo lectura (>24 horas)
        try:
            from utils.config_manager import cargar_config
            import pandas as pd
            fecha_registro = str(valores[0])  # Fecha es la primera columna
            fecha_dt = pd.to_datetime(fecha_registro, dayfirst=True, errors="coerce")
            if fecha_dt is not pd.NaT and (datetime.now() - fecha_dt).total_seconds() > _SECONDS_IN_24H:
                config = cargar_config()
                pwd_correcta = config.get("password_edicion", "admin1234")
                win_pwd = tk.Toplevel(self.ventana)
                win_pwd.title("Acceso restringido")
                win_pwd.geometry("320x130")
                win_pwd.grab_set()
                ttk.Label(win_pwd,
                          text="Este registro tiene más de 24 horas.\nIngrese la contraseña para editar:",
                          justify="center").pack(pady=10)
                pwd_var = tk.StringVar()
                ttk.Entry(win_pwd, textvariable=pwd_var, show="*", width=20).pack()
                permitido = [False]

                def _verificar():
                    if pwd_var.get() == pwd_correcta:
                        permitido[0] = True
                        win_pwd.destroy()
                    else:
                        messagebox.showerror("Error", "Contraseña incorrecta", parent=win_pwd)

                ttk.Button(win_pwd, text="Aceptar", command=_verificar).pack(pady=8)
                self.ventana.wait_window(win_pwd)
                if not permitido[0]:
                    return
        except Exception:
            pass

        ventana_editar = tk.Toplevel(self.ventana)
        ventana_editar.title("Editar Registro")
        ventana_editar.geometry("500x400")
        ventana_editar.grab_set()

        campos = ["Turno", "Labor", "GSI", "RMR", "Soporte", "Observaciones"]
        nombres = ["Fecha", "Turno", "Labor", "GSI", "RMR", "Soporte", "Observaciones"]
        entradas = {}

        for i, nombre in enumerate(nombres):
            ttk.Label(ventana_editar, text=nombre).grid(row=i, column=0, sticky="w", padx=10, pady=4)
            if nombre == "Fecha":
                ttk.Label(ventana_editar, text=str(valores[i])).grid(row=i, column=1, sticky="w", padx=10)
            elif nombre == "Observaciones":
                txt = tk.Text(ventana_editar, height=4, width=35, font=("Segoe UI", 10))
                txt.grid(row=i, column=1, sticky="ew", padx=10, pady=4)
                txt.insert("1.0", str(valores[i]) if str(valores[i]) != "nan" else "")
                entradas[nombre] = txt
            else:
                var = tk.StringVar(value=str(valores[i]) if str(valores[i]) != "nan" else "")
                ttk.Entry(ventana_editar, textvariable=var, width=35).grid(row=i, column=1, sticky="ew", padx=10, pady=4)
                entradas[nombre] = var

        ventana_editar.columnconfigure(1, weight=1)

        def _confirmar():
            nuevos = {}
            for nombre in campos:
                if nombre == "Observaciones":
                    nuevos[nombre] = entradas[nombre].get("1.0", tk.END).strip()
                else:
                    nuevos[nombre] = entradas[nombre].get().strip()
            exito, msg = self.model.editar_registro(indice, nuevos)
            if exito:
                messagebox.showinfo("Éxito", msg, parent=ventana_editar)
                ventana_editar.destroy()
                self._buscar_labor()
            else:
                messagebox.showerror("Error", msg, parent=ventana_editar)

        ttk.Button(ventana_editar, text="Confirmar", command=_confirmar).grid(
            row=len(nombres), column=0, columnspan=2, pady=10)

    def _deshacer(self):
        """Deshace la última acción (undo)"""
        exito, msg = self.model.deshacer_ultima_accion()
        if exito:
            messagebox.showinfo("Deshacer", msg, parent=self.ventana)
            self._buscar_labor()
        else:
            messagebox.showinfo("Deshacer", msg, parent=self.ventana)

    def _archivar_periodo(self):
        """Abre ventana para archivar un período"""
        win = tk.Toplevel(self.ventana)
        win.title("Archivar Período")
        win.geometry("360x200")
        win.grab_set()

        ttk.Label(win, text="Seleccione el rango de fechas a archivar:",
                  font=("Segoe UI", 10)).pack(pady=10)

        frame_f = ttk.Frame(win)
        frame_f.pack(pady=5)
        ttk.Label(frame_f, text="Desde:").grid(row=0, column=0, padx=5)
        fi = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        fi.grid(row=0, column=1, padx=5)
        ttk.Label(frame_f, text="Hasta:").grid(row=0, column=2, padx=5)
        ff = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        ff.grid(row=0, column=3, padx=5)

        lbl_info = ttk.Label(win, text="")
        lbl_info.pack(pady=5)

        def _previsualizar():
            import pandas as pd
            try:
                df = self.model.obtener_bitacora()
                if df.empty:
                    lbl_info.config(text="No hay registros")
                    return
                df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
                inicio = datetime.strptime(fi.get(), "%d/%m/%Y")
                fin = datetime.strptime(ff.get(), "%d/%m/%Y")
                n = len(df[(df["Fecha_dt"] >= inicio) & (df["Fecha_dt"] <= fin)])
                lbl_info.config(text=f"Se archivarán {n} registro(s)")
            except Exception as e:
                lbl_info.config(text=f"Error: {e}")

        def _confirmar():
            _previsualizar()
            if not messagebox.askyesno("Confirmar", "¿Archivar los registros seleccionados?\n"
                                       "Se moverán al archivo histórico y se eliminarán del principal.",
                                       parent=win):
                return
            exito, msg, _ = self.model.archivar_periodo(fi.get(), ff.get())
            messagebox.showinfo("Archivar", msg, parent=win)
            if exito:
                win.destroy()
                self._buscar_labor()

        frame_btn = ttk.Frame(win)
        frame_btn.pack(pady=8)
        ttk.Button(frame_btn, text="Previsualizar", command=_previsualizar).pack(side="left", padx=5)
        ttk.Button(frame_btn, text="Archivar", command=_confirmar).pack(side="left", padx=5)
        ttk.Button(frame_btn, text="Cancelar", command=win.destroy).pack(side="left", padx=5)

    def _eliminar_registro(self):
        """Elimina el registro seleccionado con confirmación"""
        indice = self._obtener_indice_seleccionado()
        if indice is None:
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            "¿Está seguro de que desea eliminar este registro?\nEsta acción no se puede deshacer.",
            parent=self.ventana
        )
        if confirmar:
            exito, msg = self.model.eliminar_registro(indice)
            if exito:
                messagebox.showinfo("Éxito", msg, parent=self.ventana)
                self._buscar_labor()
            else:
                messagebox.showerror("Error", msg, parent=self.ventana)

    def _exportar_excel(self):
        """Exporta el historial filtrado a un archivo Excel"""
        labor = self.buscar_var.get()
        fecha_inicio = self.fecha_inicio_var.get()
        fecha_fin = self.fecha_fin_var.get()

        df = self.model.buscar_registros(labor, fecha_inicio, fecha_fin)

        if df.empty:
            messagebox.showinfo("Info", "No hay datos para exportar", parent=self.ventana)
            return

        # Ordenar por labor numéricamente
        df = ordenar_df_por_labor(df)

        nombre_archivo = f"historial_geomecanica_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        exito, mensaje = self.model.exportar_historial_excel(df, nombre_archivo)
        if exito:
            messagebox.showinfo("Exportar Excel", f"Archivo exportado:\n{nombre_archivo}", parent=self.ventana)
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana)
    
    def _exportar_pdf(self):
        """Exporta historial a PDF – con diseño visual mejorado."""
        from utils.config_manager import obtener_clasificaciones_activas
        labor = self.buscar_var.get()
        fecha_inicio = self.fecha_inicio_var.get()
        fecha_fin = self.fecha_fin_var.get()

        df = self.model.buscar_registros(labor, fecha_inicio, fecha_fin)

        if df.empty:
            messagebox.showinfo("Info", "No hay datos para exportar")
            return

        # Ordenar por labor numéricamente
        df = ordenar_df_por_labor(df)

        activas = obtener_clasificaciones_activas()
        labor_real = df["Labor"].iloc[0] if not df.empty else (labor or "general")
        nombre = f"historial_labor_{labor_real}.pdf".replace(" ", "_")

        estilos = _crear_estilos_pdf()

        # Columnas a incluir según clasificaciones activas
        cols_clasificacion = [c for c in ["GSI", "RMR"] if c in activas and c in df.columns]
        cols_mostrar = ["Fecha", "Turno", "Labor"] + cols_clasificacion + ["Soporte", "Observaciones"]
        cols_mostrar = [c for c in cols_mostrar if c in df.columns]

        ancho_base = {"Fecha": 60, "Turno": 42, "Labor": 85,
                      "GSI": 34, "RMR": 34,
                      "Soporte": 125, "Observaciones": 125}
        col_widths = [ancho_base.get(c, 60) for c in cols_mostrar]

        periodo_txt = ""
        if fecha_inicio and fecha_fin:
            periodo_txt = f"{fecha_inicio} al {fecha_fin}"
        elif fecha_inicio:
            periodo_txt = f"desde {fecha_inicio}"
        elif fecha_fin:
            periodo_txt = f"hasta {fecha_fin}"

        clasificaciones_texto = " · ".join(activas) if activas else "Sin clasificación"
        labores_unicas = df["Labor"].unique().tolist() if "Labor" in df.columns else []
        labores_txt = ", ".join(str(l) for l in labores_unicas[:5])
        if len(labores_unicas) > 5:
            labores_txt += f" (+{len(labores_unicas)-5} más)"

        lineas_info = [
            f"<b>Labor(es):</b> {labores_txt or labor_real}",
        ]
        if periodo_txt:
            lineas_info.append(f"<b>Período:</b> {periodo_txt}")
        lineas_info += [
            f"<b>Total de registros:</b> {len(df)}",
            f"<b>Clasificaciones activas:</b> {clasificaciones_texto}",
            f"<b>Exportado:</b> {obtener_fecha_actual()}",
        ]

        pdf = SimpleDocTemplate(
            nombre,
            pagesize=landscape(letter),
            leftMargin=2*cm, rightMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        elementos = []

        elementos += _construir_bloque_header_pdf(
            estilos, "📋  HISTORIAL DE LABORES — GEOMECÁNICA", lineas_info
        )

        # Tabla de datos
        encabezado = cols_mostrar[:]
        datos = [encabezado]
        for _, row in df.iterrows():
            fila = []
            for col in cols_mostrar:
                val = str(row[col]) if str(row[col]) != "nan" else ""
                if col in ("Soporte", "Observaciones"):
                    fila.append(Paragraph(val, estilos["normal"]))
                else:
                    fila.append(val)
            datos.append(fila)

        tabla = Table(datos, colWidths=col_widths, repeatRows=1)
        tabla.setStyle(_tabla_estilo_principal(col_widths, encabezado))
        elementos.append(tabla)
        elementos.append(Spacer(1, 18))

        # Bloque de estadísticas
        elementos.append(Paragraph("Estadísticas del historial", estilos["seccion"]))
        elementos.append(HRFlowable(width="100%", thickness=0.5, color=_PDF_GRID))
        elementos.append(Spacer(1, 6))

        try:
            import pandas as pd
            stat_rows = []
            if "Labor" in df.columns:
                top_labor = df["Labor"].value_counts().idxmax()
                stat_rows.append(["Labor con más registros", str(top_labor)])
            if "Turno" in df.columns:
                for t, n in df["Turno"].value_counts().items():
                    stat_rows.append([f"Registros turno {t}", str(n)])
            if stat_rows:
                tbl_stat = Table([["Indicador", "Valor"]] + stat_rows, colWidths=[200, 120])
                tbl_stat.setStyle(TableStyle([
                    ("BACKGROUND",  (0, 0), (-1, 0), _PDF_SUBHEADER),
                    ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                    ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE",    (0, 0), (-1, -1), 8),
                    ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
                    ("ALIGN",       (0, 0), (0, -1), "LEFT"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
                    ("GRID",        (0, 0), (-1, -1), 0.4, _PDF_GRID),
                    ("TOPPADDING",  (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elementos.append(tbl_stat)
        except Exception:
            pass

        pdf.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
        messagebox.showinfo("PDF", f"Historial exportado:\n{nombre}")


class VentanaEstandar:
    """Ventana para editar estándares de sostenimiento con soporte multi-clasificación"""
    
    def __init__(self, parent, model):
        self.model = model
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Estándar de Sostenimiento")
        self.ventana.geometry("750x500")
        self.ventana.minsize(650, 400)
        self.ventana.configure(bg=PALETTE["surface"])
        
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self.ventana)
    
    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de estándar con pestañas por sistema"""
        from utils.config_manager import (
            obtener_clasificaciones_activas,
            obtener_clasificaciones_disponibles,
            columnas_estandar,
        )

        # Header
        header = tk.Frame(self.ventana, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🔩 Estándar de Sostenimiento",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        activas = obtener_clasificaciones_activas()
        disponibles = {c["id"]: c["nombre"] for c in obtener_clasificaciones_disponibles()}

        # Notebook (pestañas)
        self.notebook = ttk.Notebook(self.ventana)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        self._tabs = {}

        for sistema_id in activas:
            nombre = disponibles.get(sistema_id, sistema_id)
            cols = columnas_estandar(sistema_id)
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=nombre)

            tabla = ttk.Treeview(frame, columns=cols, show="headings")
            col_min, col_max = cols[0], cols[1]
            anchos = {col_min: 80, col_max: 80, "Tipo": 120, "Soporte": 250}
            for col in cols:
                tabla.heading(col, text=col)
                tabla.column(col, width=anchos.get(col, 100), anchor="center")
            tabla.pack(pady=5, fill="both", expand=True, padx=5)

            # Cargar datos existentes
            df = self.model.obtener_estandar_sostenimiento(sistema_id)
            for _, row in df.iterrows():
                tipo_val = row.get("Tipo", "") if "Tipo" in df.columns else ""
                tabla.insert("", "end", values=(
                    row.get(col_min, ""), row.get(col_max, ""), tipo_val,
                    row.get("Soporte", "")
                ))

            # Frame de inputs
            frame_inputs = tk.Frame(frame)
            frame_inputs.pack(pady=5)

            tk.Label(frame_inputs, text=f"{col_min}").grid(row=0, column=0, padx=5)
            entrada_min = tk.Entry(frame_inputs, width=8)
            entrada_min.grid(row=0, column=1, padx=5)

            tk.Label(frame_inputs, text=f"{col_max}").grid(row=0, column=2, padx=5)
            entrada_max = tk.Entry(frame_inputs, width=8)
            entrada_max.grid(row=0, column=3, padx=5)

            tk.Label(frame_inputs, text="Tipo").grid(row=0, column=4, padx=5)
            tipo_var = tk.StringVar(value="Temporal")
            ttk.Combobox(
                frame_inputs,
                textvariable=tipo_var,
                values=["Temporal", "Permanente"],
                state="readonly",
                width=12
            ).grid(row=0, column=5, padx=5)

            tk.Label(frame_inputs, text="Soporte").grid(row=0, column=6, padx=5)
            entrada_soporte = tk.Entry(frame_inputs, width=25)
            entrada_soporte.grid(row=0, column=7, padx=5)

            # Frame de botones
            frame_botones = tk.Frame(frame, bg=PALETTE["surface"])
            frame_botones.pack(pady=5)

            tab_data = {
                "sistema": sistema_id,
                "tabla": tabla,
                "entrada_min": entrada_min,
                "entrada_max": entrada_max,
                "tipo_var": tipo_var,
                "entrada_soporte": entrada_soporte,
                "cols": cols,
            }
            self._tabs[sistema_id] = tab_data

            def _make_agregar(td=tab_data):
                return lambda: self._agregar_fila(td)
            def _make_editar(td=tab_data):
                return lambda: self._editar_fila(td)
            def _make_eliminar(td=tab_data):
                return lambda: self._eliminar_fila(td)
            def _make_guardar(td=tab_data):
                return lambda: self._guardar_estandar(td)

            def _eplace(text, command, style="primary", parent_frame=frame_botones):
                b = _make_styled_btn(parent_frame, text, command, style=style)
                b.pack(side="left", padx=5)
                return b

            _eplace("➕ Agregar Fila",    _make_agregar(),     "primary", frame_botones)
            _eplace("✏ Editar Fila",     _make_editar(),      "secondary", frame_botones)
            _eplace("🗑 Eliminar Fila",   _make_eliminar(),    "danger",  frame_botones)
            _eplace("💾 Guardar",         _make_guardar(),     "primary", frame_botones)
    
    def _agregar_fila(self, tab_data):
        """Agrega una fila a la tabla del sistema activo"""
        val_min = tab_data["entrada_min"].get()
        val_max = tab_data["entrada_max"].get()
        tipo = tab_data["tipo_var"].get()
        soporte = tab_data["entrada_soporte"].get()

        if not val_min or not val_max or not soporte:
            messagebox.showwarning("Error", "Complete todos los campos")
            return

        tab_data["tabla"].insert("", "end", values=(val_min, val_max, tipo, soporte))

        tab_data["entrada_min"].delete(0, tk.END)
        tab_data["entrada_max"].delete(0, tk.END)
        tab_data["entrada_soporte"].delete(0, tk.END)
        tab_data["tipo_var"].set("Temporal")

    def _editar_fila(self, tab_data):
        """Carga la fila seleccionada en los campos de entrada para edición."""
        seleccionado = tab_data["tabla"].selection()
        if not seleccionado:
            messagebox.showwarning("Advertencia", "Seleccione una fila para editar")
            return
        item_id = seleccionado[0]
        valores = tab_data["tabla"].item(item_id)["values"]

        # Abrir diálogo de edición
        win = tk.Toplevel(self.ventana)
        win.title("Editar Fila")
        win.geometry("460x200")
        win.grab_set()
        win.resizable(False, False)
        win.configure(bg=PALETTE["surface"])

        cols = tab_data["cols"]
        col_min, col_max = cols[0], cols[1]

        frame_ed = tk.Frame(win, bg=PALETTE["surface"])
        frame_ed.pack(padx=15, pady=15, fill="x")

        tk.Label(frame_ed, text=f"{col_min}:", bg=PALETTE["surface"]).grid(row=0, column=0, padx=5, pady=4, sticky="e")
        ed_min = tk.Entry(frame_ed, width=10)
        ed_min.grid(row=0, column=1, padx=5, pady=4)
        ed_min.insert(0, str(valores[0]))

        tk.Label(frame_ed, text=f"{col_max}:", bg=PALETTE["surface"]).grid(row=0, column=2, padx=5, pady=4, sticky="e")
        ed_max = tk.Entry(frame_ed, width=10)
        ed_max.grid(row=0, column=3, padx=5, pady=4)
        ed_max.insert(0, str(valores[1]))

        tk.Label(frame_ed, text="Tipo:", bg=PALETTE["surface"]).grid(row=1, column=0, padx=5, pady=4, sticky="e")
        tipo_var = tk.StringVar(value=str(valores[2]))
        ttk.Combobox(frame_ed, textvariable=tipo_var,
                     values=["Temporal", "Permanente"], state="readonly",
                     width=12).grid(row=1, column=1, padx=5, pady=4)

        tk.Label(frame_ed, text="Soporte:", bg=PALETTE["surface"]).grid(row=2, column=0, padx=5, pady=4, sticky="e")
        ed_soporte = tk.Entry(frame_ed, width=35)
        ed_soporte.grid(row=2, column=1, columnspan=3, padx=5, pady=4, sticky="ew")
        ed_soporte.insert(0, str(valores[3]))

        frame_ed.columnconfigure(3, weight=1)

        def _confirmar():
            new_min = ed_min.get().strip()
            new_max = ed_max.get().strip()
            new_soporte = ed_soporte.get().strip()
            if not new_min or not new_max or not new_soporte:
                messagebox.showwarning("Error", "Complete todos los campos", parent=win)
                return
            tab_data["tabla"].item(item_id, values=(
                new_min, new_max, tipo_var.get(), new_soporte
            ))
            win.destroy()

        frame_btn = tk.Frame(win, bg=PALETTE["surface"])
        frame_btn.pack(pady=8)
        _make_styled_btn(frame_btn, "✅ Confirmar", _confirmar, style="primary").pack(side="left", padx=8)
        _make_styled_btn(frame_btn, "✕ Cancelar", win.destroy, style="danger").pack(side="left", padx=8)
    
    def _eliminar_fila(self, tab_data):
        """Elimina la fila seleccionada"""
        seleccionado = tab_data["tabla"].selection()
        if seleccionado:
            tab_data["tabla"].delete(seleccionado)
    
    def _guardar_estandar(self, tab_data):
        """Guarda los estándares del sistema activo"""
        cols = tab_data["cols"]
        datos = []
        for fila in tab_data["tabla"].get_children():
            valores = tab_data["tabla"].item(fila)["values"]
            datos.append({
                cols[0]: valores[0],
                cols[1]: valores[1],
                "Tipo": valores[2],
                "Soporte": valores[3]
            })

        exito, mensaje = self.model.guardar_estandar_sostenimiento(
            datos, sistema=tab_data["sistema"]
        )
        messagebox.showinfo("Resultado", mensaje)


class VentanaLabores:
    """Ventana para gestionar el catálogo de labores"""

    def __init__(self, parent, model, callback_actualizar=None):
        self.model = model
        self.callback_actualizar = callback_actualizar
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Gestión de Labores")
        self.ventana.geometry("750x580")
        self.ventana.minsize(650, 450)
        self.ventana.configure(bg=PALETTE["surface"])
        self.ventana.resizable(True, True)
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self.ventana)

    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de gestión de labores"""
        # Header
        header = tk.Frame(self.ventana, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🏗 Gestión de Labores",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Frame para agregar nueva labor
        frame_agregar = ttk.LabelFrame(self.ventana, text="Nueva Labor", padding=10)
        frame_agregar.pack(fill="x", padx=15, pady=5)

        # Fila 0: Nombre de la labor y Tipo
        ttk.Label(frame_agregar, text="Nombre:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.nueva_labor_var = tk.StringVar()
        entrada_nombre = ttk.Entry(frame_agregar, textvariable=self.nueva_labor_var, width=30)
        entrada_nombre.grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        entrada_nombre.bind("<KeyRelease>", self._autodetectar_clasificacion)

        ttk.Label(frame_agregar, text="Tipo:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        self.tipo_var = tk.StringVar(value="Temporal")
        combo_tipo = ttk.Combobox(
            frame_agregar,
            textvariable=self.tipo_var,
            values=["Temporal", "Permanente"],
            state="readonly",
            width=12
        )
        combo_tipo.grid(row=0, column=3, sticky="ew", padx=5, pady=3)
        combo_tipo.bind("<<ComboboxSelected>>", self._on_tipo_cambiado)

        # Fila 1: GSI, RMR, Soporte
        ttk.Label(frame_agregar, text="GSI:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.gsi_var = tk.StringVar()
        ttk.Entry(frame_agregar, textvariable=self.gsi_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(frame_agregar, text="RMR:").grid(row=1, column=2, sticky="w", padx=5, pady=3)
        self.rmr_var = tk.StringVar()
        entrada_rmr = ttk.Entry(frame_agregar, textvariable=self.rmr_var, width=10)
        entrada_rmr.grid(row=1, column=3, sticky="w", padx=5, pady=3)
        entrada_rmr.bind("<KeyRelease>", self._calcular_soporte)

        ttk.Label(frame_agregar, text="Soporte:").grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.soporte_var = tk.StringVar()
        ttk.Entry(frame_agregar, textvariable=self.soporte_var, width=40).grid(row=2, column=1, columnspan=3, sticky="ew", padx=5, pady=3)

        # Fila 3: Fase (sin campo Clasificación KPI en el formulario)
        ttk.Label(frame_agregar, text="Fase:").grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.fase_var = tk.StringVar()
        combo_fase = ttk.Combobox(
            frame_agregar,
            textvariable=self.fase_var,
            values=["Explotación", "Desarrollo", "Preparación"],
            state="readonly",
            width=15
        )
        combo_fase.grid(row=3, column=1, sticky="w", padx=5, pady=3)

        # Conversión automática a mayúsculas para campos de texto
        def _a_mayusculas(var, *args):
            valor = var.get()
            mayus = valor.upper()
            if valor != mayus:
                var.set(mayus)

        self.nueva_labor_var.trace_add("write", lambda *a: _a_mayusculas(self.nueva_labor_var))
        self.gsi_var.trace_add("write", lambda *a: _a_mayusculas(self.gsi_var))
        self.soporte_var.trace_add("write", lambda *a: _a_mayusculas(self.soporte_var))

        frame_agregar.columnconfigure(1, weight=1)

        # Botones: Agregar, Gestionar Clasificaciones de labor, Gestionar KPI
        frame_botones_agregar = ttk.Frame(frame_agregar)
        frame_botones_agregar.grid(row=4, column=0, columnspan=4, pady=8)

        def _lplace(parent, text, command, style="primary"):
            b = _make_styled_btn(parent, text, command, style=style)
            b.pack(side="left", padx=5)
            return b

        _lplace(frame_botones_agregar, "➕ Agregar Labor",             self._agregar_labor,         "primary")
        _lplace(frame_botones_agregar, "⚙ Gestionar Clasificaciones",  self._abrir_clasificaciones,  "secondary")
        _lplace(frame_botones_agregar, "📊 Gestionar KPI",             self._abrir_gestion_kpi,      "secondary")

        # Frame para lista de labores
        frame_lista = ttk.LabelFrame(self.ventana, text="Labores Registradas", padding=10)
        frame_lista.pack(fill="both", expand=True, padx=15, pady=5)

        columnas = ["Labor", "GSI", "RMR", "Soporte", "Tipo", "Fase", "Clasificacion_KPI"]
        self.tabla_labores = ttk.Treeview(frame_lista, columns=columnas, show="headings", height=10)

        anchos = {"Labor": 150, "GSI": 55, "RMR": 55, "Soporte": 160, "Tipo": 85,
                  "Fase": 90, "Clasificacion_KPI": 110}
        for col in columnas:
            self.tabla_labores.heading(col, text=col.replace("_", " "))
            self.tabla_labores.column(col, anchor="center", width=anchos.get(col, 80))

        scrollbar_y = ttk.Scrollbar(frame_lista, orient="vertical", command=self.tabla_labores.yview)
        self.tabla_labores.configure(yscrollcommand=scrollbar_y.set)
        self.tabla_labores.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

        # Botones de acción
        frame_botones = tk.Frame(self.ventana, bg=PALETTE["surface"])
        frame_botones.pack(pady=10)

        def _lplace2(text, command, style="primary"):
            b = _make_styled_btn(frame_botones, text, command, style=style)
            b.pack(side="left", padx=5)
            return b

        _lplace2("🗑 Eliminar Seleccionada", self._eliminar_labor, "danger")
        _lplace2("✕ Cerrar",                self._cerrar,         "danger")

        self._cargar_labores()

    def _calcular_soporte(self, event):
        """Calcula el soporte automáticamente según RMR ingresado"""
        try:
            rmr_texto = self.rmr_var.get().strip()
            if not rmr_texto:
                return
            rmr = int(rmr_texto)
            tipo = self.tipo_var.get()
            soporte = self.model.recomendar_soporte(rmr, tipo=tipo)
            if soporte:
                self.soporte_var.set(soporte)
        except (ValueError, Exception):
            pass

    def _on_tipo_cambiado(self, event):
        """Recalcula soporte al cambiar el tipo."""
        self._calcular_soporte(event)

    def _actualizar_combo_kpi(self):
        """Mantiene compatibilidad; no se usa en el formulario pero puede llamarse internamente."""
        pass

    def _autodetectar_clasificacion(self, event):
        """Detecta automáticamente el tipo, la fase y la clasificación al escribir el nombre."""
        self._autodetectar_todo(event)

    def _autodetectar_todo(self, event):
        """
        Al escribir el nombre de la labor, detecta automáticamente:
        - El tipo (Temporal/Permanente) según el prefijo.
        - La fase (Explotación/Preparación/Desarrollo) según la clasificación detectada.
        """
        try:
            from utils.clasificaciones import cargar_clasificaciones
            nombre = self.nueva_labor_var.get().upper()
            clasificaciones = cargar_clasificaciones()
            for tipo, clases in clasificaciones.items():
                for kpi, datos in clases.items():
                    prefijo = datos.get("prefijo", "") if isinstance(datos, dict) else str(datos)
                    if prefijo and nombre.startswith(prefijo.upper()):
                        self.tipo_var.set(tipo)
                        fase = datos.get("fase", "") if isinstance(datos, dict) else ""
                        if fase:
                            self.fase_var.set(fase)
                        return
        except Exception:
            pass

    def _abrir_clasificaciones(self):
        """Abre la ventana de gestión de clasificaciones de labor (TAJO, VENTANA, etc.)."""
        VentanaClasificaciones(self.ventana, callback_actualizar=None)

    def _abrir_gestion_kpi(self):
        """Abre la ventana de gestión de clasificaciones KPI."""
        VentanaGestionKPI(self.ventana)

    def _cargar_labores(self):
        """Carga y muestra las labores guardadas en la tabla"""
        for item in self.tabla_labores.get_children():
            self.tabla_labores.delete(item)

        try:
            df = self.model._leer_labores_df()
            for _, row in df.iterrows():
                self.tabla_labores.insert("", "end", values=(
                    row.get("Labor", ""),
                    row.get("GSI", ""),
                    row.get("RMR", ""),
                    row.get("Soporte", ""),
                    row.get("Tipo", ""),
                    row.get("Fase", ""),
                    row.get("Clasificacion_KPI", ""),
                ))
        except Exception:
            pass

    def _agregar_labor(self):
        """Agrega una nueva labor con sus datos"""
        nombre = self.nueva_labor_var.get().strip()
        if not nombre:
            messagebox.showwarning("Advertencia", "Ingrese un nombre de labor", parent=self.ventana)
            return

        gsi = self.gsi_var.get().strip()
        rmr = self.rmr_var.get().strip()
        soporte = self.soporte_var.get().strip()
        tipo = self.tipo_var.get()
        fase = self.fase_var.get().strip()

        exito, mensaje = self.model.agregar_labor(
            nombre, gsi=gsi, rmr=rmr, soporte=soporte, tipo=tipo,
            fase=fase, clasificacion_kpi=""
        )
        if exito:
            self.nueva_labor_var.set("")
            self.gsi_var.set("")
            self.rmr_var.set("")
            self.soporte_var.set("")
            self.tipo_var.set("Temporal")
            self.fase_var.set("")
            self._cargar_labores()
            if self.callback_actualizar:
                self.callback_actualizar()
            messagebox.showinfo("Éxito", mensaje, parent=self.ventana)
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana)

    def _eliminar_labor(self):
        """Elimina la labor seleccionada en la tabla"""
        seleccion = self.tabla_labores.selection()
        if not seleccion:
            messagebox.showwarning("Advertencia", "Seleccione una labor para eliminar", parent=self.ventana)
            return

        labor = self.tabla_labores.item(seleccion[0])["values"][0]
        confirmar = messagebox.askyesno(
            "Confirmar",
            f"¿Desea eliminar la labor '{labor}'?\n\nEsto no eliminará los registros existentes en la bitácora.",
            parent=self.ventana
        )
        if confirmar:
            exito, mensaje = self.model.eliminar_labor(labor)
            if exito:
                self._cargar_labores()
                if self.callback_actualizar:
                    self.callback_actualizar()
                messagebox.showinfo("Éxito", mensaje, parent=self.ventana)
            else:
                messagebox.showerror("Error", mensaje, parent=self.ventana)

    def _cerrar(self):
        """Cierra la ventana"""
        self.ventana.destroy()


class VentanaClasificaciones(tk.Toplevel):
    """Ventana para gestionar las clasificaciones de labores (Temporal y Permanente)."""

    def __init__(self, parent, callback_actualizar=None):
        super().__init__(parent)
        self.callback_actualizar = callback_actualizar
        self.title("Gestionar Clasificaciones de Labor")
        self.geometry("600x520")
        self.minsize(500, 400)
        self.resizable(True, True)
        self.grab_set()
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        tk.Label(self, text="Clasificaciones de Labor",
                 font=("Segoe UI", 13, "bold")).pack(pady=8)

        # Frame superior: listas por tipo
        frame_listas = ttk.Frame(self)
        frame_listas.pack(fill="both", expand=True, padx=12, pady=4)

        for col_idx, tipo in enumerate(("Temporal", "Permanente")):
            lf = ttk.LabelFrame(frame_listas, text=tipo, padding=8)
            lf.grid(row=0, column=col_idx, sticky="nsew", padx=6, pady=4)
            frame_listas.columnconfigure(col_idx, weight=1)
            frame_listas.rowconfigure(0, weight=1)

            lb = tk.Listbox(lf, height=10, exportselection=False)
            sb = ttk.Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            setattr(self, f"_lb_{tipo.lower()}", lb)

        self._recargar_listas()

        # Frame inferior: agregar / eliminar
        frame_accion = ttk.LabelFrame(self, text="Agregar nueva clasificación", padding=10)
        frame_accion.pack(fill="x", padx=12, pady=6)

        ttk.Label(frame_accion, text="Nombre:").grid(row=0, column=0, sticky="w", padx=4)
        self._nombre_var = tk.StringVar()
        entrada_nombre = ttk.Entry(frame_accion, textvariable=self._nombre_var, width=12)
        entrada_nombre.grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(frame_accion, text="Prefijo:").grid(row=0, column=2, sticky="w", padx=4)
        self._prefijo_var = tk.StringVar()
        ttk.Entry(frame_accion, textvariable=self._prefijo_var, width=7).grid(row=0, column=3, padx=4)

        ttk.Label(frame_accion, text="Fase:").grid(row=0, column=4, sticky="w", padx=4)
        self._fase_nueva_var = tk.StringVar()
        ttk.Combobox(
            frame_accion, textvariable=self._fase_nueva_var,
            values=["Explotación", "Desarrollo", "Preparación", ""],
            state="readonly", width=12
        ).grid(row=0, column=5, padx=4)

        ttk.Label(frame_accion, text="Tipo:").grid(row=0, column=6, sticky="w", padx=4)
        self._tipo_nuevo_var = tk.StringVar(value="Temporal")
        ttk.Combobox(
            frame_accion, textvariable=self._tipo_nuevo_var,
            values=["Temporal", "Permanente"], state="readonly", width=10
        ).grid(row=0, column=7, padx=4)

        frame_accion.columnconfigure(1, weight=1)

        # Forzar mayúsculas
        for var in (self._nombre_var, self._prefijo_var):
            var.trace_add("write", lambda *a, v=var: v.set(v.get().upper()) if v.get() != v.get().upper() else None)

        frame_botones = ttk.Frame(self)
        frame_botones.pack(pady=8)

        ttk.Button(frame_botones, text="➕ Agregar",
                   command=self._agregar).pack(side="left", padx=6)
        ttk.Button(frame_botones, text="🗑 Eliminar seleccionada",
                   command=self._eliminar).pack(side="left", padx=6)
        ttk.Button(frame_botones, text="Cerrar",
                   command=self.destroy).pack(side="left", padx=6)

    def _recargar_listas(self):
        from utils.clasificaciones import cargar_clasificaciones
        clasificaciones = cargar_clasificaciones()
        for tipo in ("Temporal", "Permanente"):
            lb = getattr(self, f"_lb_{tipo.lower()}")
            lb.delete(0, tk.END)
            for nombre, datos in clasificaciones.get(tipo, {}).items():
                prefijo = datos.get("prefijo", "") if isinstance(datos, dict) else str(datos)
                fase = datos.get("fase", "") if isinstance(datos, dict) else ""
                lb.insert(tk.END, f"{nombre}  [{prefijo}]  {fase}")

    def _agregar(self):
        from utils.clasificaciones import cargar_clasificaciones, guardar_clasificaciones
        nombre = self._nombre_var.get().strip()
        prefijo = self._prefijo_var.get().strip()
        tipo = self._tipo_nuevo_var.get()
        fase = self._fase_nueva_var.get()
        if not nombre or not prefijo:
            messagebox.showwarning("Advertencia", "Ingrese nombre y prefijo", parent=self)
            return
        clasificaciones = cargar_clasificaciones()
        clasificaciones.setdefault(tipo, {})[nombre] = {"prefijo": prefijo, "fase": fase}
        if guardar_clasificaciones(clasificaciones):
            self._nombre_var.set("")
            self._prefijo_var.set("")
            self._fase_nueva_var.set("")
            self._recargar_listas()
            if self.callback_actualizar:
                self.callback_actualizar()
            messagebox.showinfo("Éxito", f"Clasificación '{nombre}' agregada", parent=self)
        else:
            messagebox.showerror("Error", "No se pudo guardar la clasificación", parent=self)

    def _eliminar(self):
        from utils.clasificaciones import cargar_clasificaciones, guardar_clasificaciones
        clasificaciones = cargar_clasificaciones()
        eliminado = False
        for tipo in ("Temporal", "Permanente"):
            lb = getattr(self, f"_lb_{tipo.lower()}")
            sel = lb.curselection()
            if sel:
                entrada = lb.get(sel[0])
                nombre = entrada.split("  [")[0].strip()
                mapa = clasificaciones.get(tipo, {})
                if nombre in mapa:
                    del mapa[nombre]
                    clasificaciones[tipo] = mapa
                    eliminado = True
                    break
        if not eliminado:
            messagebox.showwarning("Advertencia",
                                   "Seleccione una clasificación en alguna de las listas", parent=self)
            return
        if guardar_clasificaciones(clasificaciones):
            self._recargar_listas()
            if self.callback_actualizar:
                self.callback_actualizar()
        else:
            messagebox.showerror("Error", "No se pudo guardar los cambios", parent=self)


class VentanaGestionKPI(tk.Toplevel):
    """Ventana simple para gestionar clasificaciones KPI (archivo separado)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Gestionar Clasificaciones KPI")
        self.geometry("400x380")
        self.minsize(350, 300)
        self.resizable(True, True)
        self.grab_set()
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        tk.Label(self, text="Clasificaciones KPI",
                 font=("Segoe UI", 13, "bold")).pack(pady=8)
        tk.Label(self, text="Ej: Producción, Desarrollo, Exploración…",
                 font=("Segoe UI", 9), fg="gray").pack()

        frame_lista = ttk.LabelFrame(self, text="Clasificaciones existentes", padding=8)
        frame_lista.pack(fill="both", expand=True, padx=15, pady=8)

        self._listbox = tk.Listbox(frame_lista, height=10, exportselection=False)
        sb = ttk.Scrollbar(frame_lista, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._recargar()

        frame_add = ttk.Frame(self)
        frame_add.pack(fill="x", padx=15, pady=4)
        ttk.Label(frame_add, text="Nueva clasificación:").pack(side="left", padx=4)
        self._nueva_var = tk.StringVar()
        ttk.Entry(frame_add, textvariable=self._nueva_var, width=20).pack(side="left", padx=4)

        frame_btn = ttk.Frame(self)
        frame_btn.pack(pady=8)
        ttk.Button(frame_btn, text="➕ Agregar",
                   command=self._agregar).pack(side="left", padx=6)
        ttk.Button(frame_btn, text="🗑 Eliminar seleccionada",
                   command=self._eliminar).pack(side="left", padx=6)
        ttk.Button(frame_btn, text="Cerrar",
                   command=self.destroy).pack(side="left", padx=6)

    def _recargar(self):
        from utils.clasificaciones import cargar_clasificaciones_kpi
        self._listbox.delete(0, tk.END)
        for kpi in cargar_clasificaciones_kpi():
            self._listbox.insert(tk.END, kpi)

    def _agregar(self):
        from utils.clasificaciones import cargar_clasificaciones_kpi, guardar_clasificaciones_kpi
        nombre = self._nueva_var.get().strip()
        if not nombre:
            messagebox.showwarning("Advertencia", "Ingrese un nombre de clasificación", parent=self)
            return
        lista = cargar_clasificaciones_kpi()
        if nombre in lista:
            messagebox.showinfo("Info", "Esa clasificación ya existe", parent=self)
            return
        lista.append(nombre)
        if guardar_clasificaciones_kpi(lista):
            self._nueva_var.set("")
            self._recargar()
        else:
            messagebox.showerror("Error", "No se pudo guardar", parent=self)

    def _eliminar(self):
        from utils.clasificaciones import cargar_clasificaciones_kpi, guardar_clasificaciones_kpi
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("Advertencia", "Seleccione una clasificación", parent=self)
            return
        nombre = self._listbox.get(sel[0])
        lista = cargar_clasificaciones_kpi()
        if nombre in lista:
            lista.remove(nombre)
            if guardar_clasificaciones_kpi(lista):
                self._recargar()
            else:
                messagebox.showerror("Error", "No se pudo guardar", parent=self)


class VentanaSostenimiento(tk.Toplevel):
    """Ventana para registrar sostenimiento diario por labor y turno"""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Sostenimiento Diario")
        self.geometry("700x720")
        self.minsize(600, 550)
        self.configure(bg=PALETTE["surface"])
        self.resizable(True, True)
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _cargar_activos(self):
        """Carga los sostenimientos activos desde config."""
        try:
            from utils.config_manager import cargar_config
            config = cargar_config()
            return config.get("sostenimientos_activos", [])
        except Exception:
            return [
                {"display": "Shotcrete (m³)", "columna": "Shotcrete_m3", "tipo": "float"},
                {"display": "Pernos Helicoidales", "columna": "Pernos_Helicoidales", "tipo": "int"},
                {"display": "Splitsets", "columna": "Splitsets", "tipo": "int"},
                {"display": "Mesh Straps", "columna": "Mesh_Strap", "tipo": "int"},
                {"display": "Cable Bolting (m)", "columna": "Cable_Bolting", "tipo": "float"},
                {"display": "Marco de Acero", "columna": "Marco_Acero", "tipo": "int"},
            ]

    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🪨 Sostenimiento Diario",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        self._frame_datos = ttk.LabelFrame(self, text="Datos de Sostenimiento", padding=12)
        self._frame_datos.pack(fill="x", padx=15, pady=5)

        # Fecha (no editable)
        ttk.Label(self._frame_datos, text="Fecha:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Label(self._frame_datos, text=obtener_fecha_actual()).grid(row=0, column=1, sticky="w", pady=3)

        # Turno
        ttk.Label(self._frame_datos, text="Turno:").grid(row=1, column=0, sticky="w", pady=3)
        self.turno_var = tk.StringVar()
        combo_turno = ttk.Combobox(self._frame_datos, textvariable=self.turno_var,
                                   state="readonly", values=TURNOS, width=15)
        combo_turno.grid(row=1, column=1, sticky="w", pady=3)
        self.turno_var.set(_obtener_turno_automatico())

        # Labor
        ttk.Label(self._frame_datos, text="Labor:").grid(row=2, column=0, sticky="w", pady=3)
        self.labor_var = tk.StringVar()
        self.entrada_labor = ttk.Entry(self._frame_datos, textvariable=self.labor_var, width=30)
        self.entrada_labor.grid(row=2, column=1, sticky="ew", pady=3)
        self.lista_labores = self.model.obtener_labores_guardadas()
        self.entrada_labor.bind("<KeyRelease>", self._filtrar_labores)
        self.entrada_labor.bind("<FocusOut>", self._ocultar_lista)

        self.listbox_labor = tk.Listbox(self._frame_datos, height=4, exportselection=False)
        self.listbox_labor.grid(row=3, column=1, sticky="ew")
        self.listbox_labor.bind("<<ListboxSelect>>", self._seleccionar_labor)
        self.listbox_labor.grid_remove()

        # Campos numéricos dinámicos desde config
        self._activos = self._cargar_activos()
        self._vars_sost = {}  # columna -> (var, tipo)
        self._tipo_shotcrete_var = tk.StringVar()
        _TIPOS_SHOTCRETE = [
            "X1 - Lanzado para avance",
            "X5 - Lanzado para reforzamiento",
            "X6 - Lanzado sobre zona inestable",
            "X7 - Lanzado sobre malla",
            "X10 - Lanzado para resane",
        ]
        for i, sost in enumerate(self._activos):
            display = sost.get("display", sost.get("columna", ""))
            columna = sost.get("columna", "")
            tipo = sost.get("tipo", "int")
            row_idx = 4 + i
            ttk.Label(self._frame_datos, text=f"{display}:").grid(
                row=row_idx, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            self._vars_sost[columna] = (var, tipo)
            ttk.Entry(self._frame_datos, textvariable=var, width=12).grid(
                row=row_idx, column=1, sticky="w", pady=2)
            # Agregar Combobox de tipo de shotcrete junto al campo Shotcrete_m3
            if columna == "Shotcrete_m3":
                ttk.Combobox(
                    self._frame_datos, textvariable=self._tipo_shotcrete_var,
                    values=_TIPOS_SHOTCRETE, state="readonly", width=30
                ).grid(row=row_idx, column=2, sticky="w", padx=6, pady=2)

        obs_row = 4 + len(self._activos)
        # Observaciones
        ttk.Label(self._frame_datos, text="Observaciones:").grid(
            row=obs_row, column=0, sticky="nw", pady=3)
        self.obs_text = tk.Text(self._frame_datos, height=3, width=35, font=("Segoe UI", 10),
                                relief="flat", borderwidth=1,
                                highlightthickness=1, highlightbackground="#cccccc",
                                highlightcolor="#4a90d9", wrap="word")
        self.obs_text.grid(row=obs_row, column=1, sticky="ew", pady=3)

        self._frame_datos.columnconfigure(1, weight=1)

        # Botones
        frame_botones = tk.Frame(self, bg=PALETTE["surface"])
        frame_botones.pack(pady=10)

        def _splace(text, command, style="primary"):
            b = _make_styled_btn(frame_botones, text, command, style=style)
            b.pack(side="left", padx=6)
            return b

        _splace("💾 Guardar Sostenimiento",  self._guardar,              "primary")
        _splace("📋 Ver Historial",          self._abrir_historial,      "secondary")
        _splace("⚙ Gestionar Tipos",        self._abrir_gestionar_sost, "secondary")
        _splace("✕ Cerrar",                 self.destroy,               "danger")

    def _abrir_gestionar_sost(self):
        """Abre la ventana de gestión de sostenimientos con callback de actualización."""
        VentanaSostenimientos(self, on_actualizar=self._refrescar_formulario)

    def _refrescar_formulario(self):
        """Destruye y recrea el contenido de la ventana para reflejar cambios en sostenimientos."""
        for widget in self.winfo_children():
            widget.destroy()
        self._crear_interfaz()

    def _filtrar_labores(self, event):
        texto = self.labor_var.get()
        self.listbox_labor.delete(0, tk.END)
        resultados = [l for l in self.lista_labores if texto.lower() in l.lower()] if texto else self.lista_labores
        if resultados:
            for l in resultados:
                self.listbox_labor.insert(tk.END, l)
            self.listbox_labor.grid()
        else:
            self.listbox_labor.grid_remove()

    def _seleccionar_labor(self, event):
        sel = self.listbox_labor.curselection()
        if sel:
            self.labor_var.set(self.listbox_labor.get(sel[0]))
            self.listbox_labor.grid_remove()

    def _ocultar_lista(self, event):
        self.after(150, lambda: self.listbox_labor.grid_remove())

    def _guardar(self):
        def _num(val, tipo="int"):
            try:
                return float(val) if tipo == "float" else int(val)
            except (ValueError, TypeError):
                return 0

        datos = {
            "Fecha": obtener_fecha_actual(),
            "Turno": self.turno_var.get(),
            "Labor": self.labor_var.get().strip(),
            "Observaciones": self.obs_text.get("1.0", tk.END).strip(),
        }
        for columna, (var, tipo) in self._vars_sost.items():
            datos[columna] = _num(var.get(), tipo)

        # Guardar tipo de shotcrete (solo el código X1, X5, etc.)
        tipo_shotcrete_completo = self._tipo_shotcrete_var.get().strip()
        if tipo_shotcrete_completo and " - " in tipo_shotcrete_completo:
            datos["Tipo_Shotcrete"] = tipo_shotcrete_completo.split(" - ")[0]
        else:
            datos["Tipo_Shotcrete"] = tipo_shotcrete_completo

        if not datos["Turno"]:
            messagebox.showwarning("Advertencia", "Seleccione un turno", parent=self)
            return
        if not datos["Labor"]:
            messagebox.showwarning("Advertencia", "Ingrese una labor", parent=self)
            return

        exito, mensaje = self.model.guardar_sostenimiento(datos)
        if exito:
            messagebox.showinfo("Éxito", mensaje, parent=self)
            self._limpiar()
        elif "DUPLICADO" in mensaje:
            confirmar = messagebox.askyesno(
                "Registro duplicado",
                "Ya existe un registro de sostenimiento para esta labor en este turno y fecha.\n"
                "¿Desea guardar de todas formas?",
                parent=self
            )
            if confirmar:
                exito2, msg2 = self.model.guardar_sostenimiento_forzado(datos)
                if exito2:
                    messagebox.showinfo("Éxito", msg2, parent=self)
                    self._limpiar()
                else:
                    messagebox.showerror("Error", msg2, parent=self)
        else:
            messagebox.showerror("Error", mensaje, parent=self)

    def _limpiar(self):
        for var, _ in self._vars_sost.values():
            var.set("")
        self.obs_text.delete("1.0", tk.END)
        self.labor_var.set("")
        self._tipo_shotcrete_var.set("")

    def _abrir_historial(self):
        VentanaHistorialSostenimiento(self, self.model)


class VentanaHistorialSostenimiento(tk.Toplevel):
    """Subventana para ver el historial de sostenimiento diario"""

    _COLS_BASE = ["Fecha", "Turno", "Labor"]
    _COLS_FIN = ["Observaciones"]

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Historial de Sostenimiento")
        self.geometry("1050x560")
        self.minsize(850, 450)
        self.configure(bg=PALETTE["surface"])
        self._indices_originales = []
        self.COLUMNAS = self._obtener_columnas()
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _obtener_columnas(self):
        """Obtiene las columnas a mostrar (base + activas + observaciones)."""
        try:
            from utils.config_manager import cargar_config
            from utils.config import COLUMNAS_SOSTENIMIENTO
            config = cargar_config()
            activos = [s["columna"] for s in config.get("sostenimientos_activos", [])
                       if isinstance(s, dict) and "columna" in s]
            # Unión de las fijas del Excel y las activas
            cols_num = list(dict.fromkeys(
                [c for c in COLUMNAS_SOSTENIMIENTO
                 if c not in self._COLS_BASE and c not in self._COLS_FIN]
                + activos
            ))
            return self._COLS_BASE + cols_num + self._COLS_FIN
        except Exception:
            return [
                "Fecha", "Turno", "Labor", "Shotcrete_m3", "Pernos_Helicoidales",
                "Splitsets", "Mesh_Strap", "Cable_Bolting", "Marco_Acero", "Observaciones"
            ]

    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊 Historial de Sostenimiento",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Custom Treeview style (shared helper)
        _aplicar_estilo_treeview()

        frame_filtros = tk.Frame(self, bg=PALETTE["surface"])
        frame_filtros.pack(fill="x", padx=10, pady=8)

        ttk.Label(frame_filtros, text="Desde:").grid(row=0, column=0, padx=4)
        self.fecha_inicio = DateEntry(frame_filtros, date_pattern="dd/mm/yyyy", width=11)
        self.fecha_inicio.grid(row=0, column=1, padx=4)

        ttk.Label(frame_filtros, text="Hasta:").grid(row=0, column=2, padx=4)
        self.fecha_fin = DateEntry(frame_filtros, date_pattern="dd/mm/yyyy", width=11)
        self.fecha_fin.grid(row=0, column=3, padx=4)

        ttk.Label(frame_filtros, text="Labor:").grid(row=0, column=4, padx=4)
        self.labor_filtro = tk.StringVar()
        ttk.Entry(frame_filtros, textvariable=self.labor_filtro, width=20).grid(row=0, column=5, padx=4)

        _filt_btn = _make_styled_btn(frame_filtros, "🔍 Filtrar", self._cargar,
                                    style="primary", padx=10, pady=3)
        _filt_btn.grid(row=0, column=6, padx=8)

        # Tabla
        self.tabla = ttk.Treeview(self, columns=self.COLUMNAS, show="headings", height=15,
                                   style="Custom.Treeview")
        self.tabla.tag_configure("odd", background="#f7f9fc")
        self.tabla.tag_configure("even", background="#ffffff")
        anchos = {"Fecha": 80, "Turno": 60, "Labor": 120, "Shotcrete_m3": 80,
                  "Pernos_Helicoidales": 100, "Splitsets": 70, "Mesh_Strap": 80,
                  "Cable_Bolting": 90, "Marco_Acero": 80, "Observaciones": 150}
        for col in self.COLUMNAS:
            self.tabla.heading(col, text=col.replace("_", " "))
            self.tabla.column(col, width=anchos.get(col, 80), anchor="center")
        self.tabla.pack(fill="both", expand=True, padx=10, pady=5)

        sb = ttk.Scrollbar(self.tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        frame_btn = tk.Frame(self, bg=PALETTE["surface"])
        frame_btn.pack(pady=8)

        def _hsplace(text, command, style="primary"):
            b = _make_styled_btn(frame_btn, text, command, style=style, padx=10, pady=4)
            b.pack(side="left", padx=5)
            return b

        _hsplace("✏ Editar",          self._editar,   "primary")
        _hsplace("🗑 Eliminar",        self._eliminar, "danger")
        _hsplace("📊 Exportar Excel",  self._exportar, "secondary")
        _hsplace("✕ Cerrar",           self.destroy,   "danger")

        self._cargar()

    def _cargar(self):
        labor = self.labor_filtro.get().strip() or None
        df = self.model.obtener_sostenimiento(labor=labor)
        self._df = df.copy()
        self._indices_originales = list(df.index)

        for item in self.tabla.get_children():
            self.tabla.delete(item)
        for i, (_, row) in enumerate(df.iterrows()):
            tag = "odd" if i % 2 == 0 else "even"
            self.tabla.insert("", "end", values=[row.get(c, "") for c in self.COLUMNAS], tags=(tag,))

    def _obtener_indice(self):
        sel = self.tabla.selection()
        if not sel:
            messagebox.showwarning("Advertencia", "Seleccione un registro", parent=self)
            return None
        pos = self.tabla.index(sel[0])
        return self._indices_originales[pos] if pos < len(self._indices_originales) else None

    def _editar(self):
        indice = self._obtener_indice()
        if indice is None:
            return
        sel = self.tabla.selection()
        valores = self.tabla.item(sel[0])["values"]

        win = tk.Toplevel(self)
        win.title("Editar Sostenimiento")
        win.geometry("420x420")
        win.grab_set()

        entradas = {}
        for i, col in enumerate(self.COLUMNAS):
            ttk.Label(win, text=col.replace("_", " ") + ":").grid(row=i, column=0, sticky="w", padx=10, pady=3)
            if col == "Fecha":
                ttk.Label(win, text=str(valores[i])).grid(row=i, column=1, sticky="w", padx=10)
            elif col == "Observaciones":
                txt = tk.Text(win, height=3, width=30, font=("Segoe UI", 10))
                txt.grid(row=i, column=1, sticky="ew", padx=10, pady=3)
                txt.insert("1.0", str(valores[i]) if str(valores[i]) != "nan" else "")
                entradas[col] = txt
            else:
                var = tk.StringVar(value=str(valores[i]) if str(valores[i]) != "nan" else "")
                ttk.Entry(win, textvariable=var, width=20).grid(row=i, column=1, sticky="w", padx=10, pady=3)
                entradas[col] = var

        win.columnconfigure(1, weight=1)

        def _ok():
            nuevos = {}
            for col in self.COLUMNAS:
                if col == "Fecha":
                    continue
                elif col == "Observaciones":
                    nuevos[col] = entradas[col].get("1.0", tk.END).strip()
                else:
                    nuevos[col] = entradas[col].get().strip()
            exito, msg = self.model.editar_sostenimiento(indice, nuevos)
            if exito:
                messagebox.showinfo("Éxito", msg, parent=win)
                win.destroy()
                self._cargar()
            else:
                messagebox.showerror("Error", msg, parent=win)

        ttk.Button(win, text="Confirmar", command=_ok).grid(
            row=len(self.COLUMNAS), column=0, columnspan=2, pady=10)

    def _eliminar(self):
        indice = self._obtener_indice()
        if indice is None:
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este registro?", parent=self):
            exito, msg = self.model.eliminar_sostenimiento(indice)
            if exito:
                messagebox.showinfo("Éxito", msg, parent=self)
                self._cargar()
            else:
                messagebox.showerror("Error", msg, parent=self)

    def _exportar(self):
        df = self.model.obtener_sostenimiento()
        if df.empty:
            messagebox.showinfo("Info", "No hay datos para exportar", parent=self)
            return
        # Ordenar por labor numéricamente
        df = ordenar_df_por_labor(df)
        nombre = f"sostenimiento_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        exito, msg = self.model.exportar_historial_excel(df, nombre)
        if exito:
            messagebox.showinfo("Exportar", f"Archivo guardado:\n{nombre}", parent=self)
        else:
            messagebox.showerror("Error", msg, parent=self)


class VentanaDashboard(tk.Toplevel):
    """Dashboard de sostenimiento con 4 gráficos matplotlib"""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Dashboard de Sostenimiento")
        self.geometry("1000x740")
        self.minsize(900, 600)
        self.configure(bg=PALETTE["surface"])
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊 Dashboard de Sostenimiento",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Filtros superiores (fila 0)
        frame_filtros = tk.Frame(self, bg=PALETTE["surface"])
        frame_filtros.pack(fill="x", padx=10, pady=8)

        ttk.Label(frame_filtros, text="Desde:").grid(row=0, column=0, padx=4)
        self.fecha_inicio = DateEntry(frame_filtros, date_pattern="dd/mm/yyyy", width=11)
        self.fecha_inicio.grid(row=0, column=1, padx=4)

        ttk.Label(frame_filtros, text="Hasta:").grid(row=0, column=2, padx=4)
        self.fecha_fin = DateEntry(frame_filtros, date_pattern="dd/mm/yyyy", width=11)
        self.fecha_fin.grid(row=0, column=3, padx=4)

        ttk.Label(frame_filtros, text="Filtrar labor:").grid(row=0, column=4, padx=4)
        self._filtro_labor_var = tk.StringVar()
        self._entry_filtro_labor = ttk.Entry(frame_filtros, textvariable=self._filtro_labor_var, width=14)
        self._entry_filtro_labor.grid(row=0, column=5, padx=4)
        self._entry_filtro_labor.bind("<KeyRelease>", self._actualizar_combo_labores)

        ttk.Label(frame_filtros, text="Labor:").grid(row=0, column=6, padx=4)
        self._todas_labores = ["Todas"] + self.model.obtener_labores_guardadas()
        self.labor_var = tk.StringVar(value="Todas")
        self._combo_labores = ttk.Combobox(frame_filtros, textvariable=self.labor_var,
                                           values=self._todas_labores, width=18)
        self._combo_labores.grid(row=0, column=7, padx=4)

        # Filtro de sostenimiento (aplica a todas las gráficas)
        ttk.Label(frame_filtros, text="Sostenimiento:").grid(row=0, column=8, padx=4)
        self._sost_filter_var = tk.StringVar(value="Todos")
        _cols_sost_config = [
            s["columna"] for s in _cargar_config().get("sostenimientos_activos", [])
            if isinstance(s, dict) and "columna" in s
        ]
        if not _cols_sost_config:
            _cols_sost_config = [
                "Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
                "Mesh_Strap", "Cable_Bolting", "Marco_Acero"
            ]
        self._cols_sost_config = _cols_sost_config
        self._combo_sost_filter = ttk.Combobox(
            frame_filtros, textvariable=self._sost_filter_var,
            values=["Todos"] + _cols_sost_config, width=16
        )
        self._combo_sost_filter.grid(row=0, column=9, padx=4)
        self._combo_sost_filter.bind("<<ComboboxSelected>>", lambda e: self._actualizar())

        _act_btn = _make_styled_btn(frame_filtros, "🔄 Actualizar", self._actualizar,
                                   style="primary", padx=10, pady=3)
        _act_btn.grid(row=0, column=10, padx=10)

        # Segunda fila: exportación individual o todas
        frame_export = tk.Frame(self, bg=PALETTE["surface"])
        frame_export.pack(fill="x", padx=10, pady=(0, 4))

        _exp_all_btn = _make_styled_btn(frame_export, "🖼 Exportar Todas", self._exportar_png,
                                        style="secondary", padx=10, pady=3)
        _exp_all_btn.pack(side="left", padx=5)

        ttk.Label(frame_export, text="Gráfica:").pack(side="left", padx=(12, 4))
        self._export_graph_var = tk.StringVar(value="1 — Totales por Labor")
        _graph_options = [
            "1 — Totales por Labor",
            "2 — Tarjeta Sostenimiento",
            "3 — Sost. por Tipo de Labor",
            "4 — Sost. por Fase de Labor",
        ]
        ttk.Combobox(frame_export, textvariable=self._export_graph_var,
                     values=_graph_options, state="readonly", width=25).pack(side="left", padx=4)
        _exp_single_btn = _make_styled_btn(frame_export, "📷 Exportar Gráfica",
                                           self._exportar_grafica_individual,
                                           style="secondary", padx=10, pady=3)
        _exp_single_btn.pack(side="left", padx=5)

        # Frame para gráficos (canvas de matplotlib)
        self.frame_graficos = ttk.Frame(self)
        self.frame_graficos.pack(fill="both", expand=True, padx=10, pady=5)

        self._actualizar()

    def _actualizar_combo_labores(self, event=None):
        """Filtra el combobox de labores según el texto escrito en el filtro."""
        texto = self._filtro_labor_var.get().strip().lower()
        if texto:
            filtradas = ["Todas"] + [l for l in self._todas_labores if l != "Todas" and texto in l.lower()]
        else:
            filtradas = self._todas_labores
        self._combo_labores["values"] = filtradas
        if self.labor_var.get() not in filtradas:
            self.labor_var.set("Todas")

    def _actualizar(self):
        """Genera y actualiza los 4 gráficos"""
        try:
            import warnings
            import matplotlib
            import pandas as pd
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            matplotlib.rcParams['axes.unicode_minus'] = False
            warnings.filterwarnings("ignore", message="Glyph.*missing from font")
        except ImportError:
            tk.Label(self.frame_graficos,
                     text="matplotlib no está instalado.\nEjecute: pip install matplotlib").pack()
            return

        # Limpiar canvas anterior
        for widget in self.frame_graficos.winfo_children():
            widget.destroy()

        fi_str = self.fecha_inicio.get()
        ff_str = self.fecha_fin.get()
        labor_sel = self.labor_var.get()
        labor_filtro = None if labor_sel == "Todas" else labor_sel
        sost_filtro = self._sost_filter_var.get()

        try:
            df_totales = self.model.obtener_totales_sostenimiento(
                fecha_inicio=fi_str, fecha_fin=ff_str, labor=labor_filtro
            )
        except Exception:
            df_totales = None

        try:
            df_sost = self.model.obtener_sostenimiento(labor=labor_filtro)
            if not df_sost.empty and "Fecha" in df_sost.columns:
                df_sost["Fecha_dt"] = pd.to_datetime(df_sost["Fecha"], format="%d/%m/%Y", errors="coerce")
                inicio = datetime.strptime(fi_str, "%d/%m/%Y")
                fin = datetime.strptime(ff_str, "%d/%m/%Y")
                df_sost = df_sost[
                    (df_sost["Fecha_dt"] >= inicio) & (df_sost["Fecha_dt"] <= fin)
                ]
        except Exception:
            df_sost = None

        try:
            df_bit = self.model.obtener_bitacora()
        except Exception:
            df_bit = None

        matplotlib.rcParams.update({
            'font.size': 9,
            'axes.titlesize': 10,
            'axes.titleweight': 'bold',
            'axes.spines.top': False,
            'axes.spines.right': False,
            'axes.grid': True,
            'grid.alpha': 0.3,
            'figure.facecolor': '#f8fafc',
            'axes.facecolor': '#ffffff',
        })
        _DASHBOARD_COLORS = ["#1a6fc4", "#2d8a6e", "#f59e0b", "#d94f3d", "#8b5cf6", "#06b6d4"]
        fig = Figure(figsize=(12, 8), dpi=90, facecolor='#f8fafc')
        axes = [fig.add_subplot(2, 2, i + 1) for i in range(4)]

        COLS_NUM = list(dict.fromkeys(
            [s["columna"] for s in _cargar_config().get("sostenimientos_activos", [])
             if isinstance(s, dict) and "columna" in s]
            + ["Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
               "Mesh_Strap", "Cable_Bolting", "Marco_Acero"]
        ))

        # Gráfico 1: Barras agrupadas – totales por labor (con filtro de sostenimiento)
        ax1 = axes[0]
        ax1.set_title("Totales por Labor")
        if df_totales is not None and not df_totales.empty:
            if sost_filtro != "Todos" and sost_filtro in df_totales.columns:
                cols_presentes = [sost_filtro]
                ax1.set_title(f"Totales por Labor — {sost_filtro}")
            else:
                cols_presentes = [c for c in COLS_NUM if c in df_totales.columns]
            df_plot = df_totales.set_index("Labor")[cols_presentes]
            df_plot.plot(kind="bar", ax=ax1, legend=True)
            ax1.set_xlabel("Labor")
            ax1.set_ylabel("Cantidad")
            ax1.tick_params(axis="x", rotation=30)
        else:
            ax1.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax1.transAxes)

        # Determinar columna de sostenimiento para gráficos 2, 3, 4
        if sost_filtro != "Todos" and sost_filtro in (df_sost.columns if df_sost is not None else []):
            _sost_col = sost_filtro
            _sost_label = sost_filtro.replace("_", " ")
        else:
            _sost_col = "Shotcrete_m3"
            _sost_label = "Shotcrete (m³)"

        # Gráfico 2: Tarjeta visual con total del sostenimiento seleccionado
        ax2 = axes[1]
        ax2.axis("off")
        total_shot = 0.0
        if df_sost is not None and not df_sost.empty and _sost_col in df_sost.columns:
            try:
                total_shot = pd.to_numeric(df_sost[_sost_col], errors="coerce").fillna(0).sum()
            except Exception:
                total_shot = 0.0

        ax2.text(0.5, 0.82, f"{_sost_label} Total", ha="center", va="center",
                 transform=ax2.transAxes, fontsize=14, fontweight="bold")
        ax2.text(0.5, 0.55, f"{total_shot:,.1f}", ha="center", va="center",
                 transform=ax2.transAxes, fontsize=30, fontweight="bold", color="steelblue")
        ax2.text(0.5, 0.30, f"Período: {fi_str} –\n         {ff_str}",
                 ha="center", va="center", transform=ax2.transAxes, fontsize=10, color="gray")
        # Borde decorativo
        from matplotlib.patches import FancyBboxPatch
        ax2.add_patch(FancyBboxPatch((0.05, 0.10), 0.90, 0.82,
                                     boxstyle="round,pad=0.02",
                                     linewidth=1.5, edgecolor="steelblue",
                                     facecolor="#eaf4fb",
                                     transform=ax2.transAxes, clip_on=False))

        # Gráfico 3: Sostenimiento por tipo de labor (Temporal vs Permanente)
        ax3 = axes[2]
        ax3.set_title(f"{_sost_label} por Tipo de Labor")
        if df_sost is not None and not df_sost.empty and _sost_col in df_sost.columns:
            try:
                df_labores = self.model._leer_labores_df()
                if not df_labores.empty and "Tipo" in df_labores.columns:
                    mapa_tipo = df_labores.set_index("Labor")["Tipo"].to_dict()
                    df_sost_tipo = df_sost.copy()
                    df_sost_tipo["Tipo"] = df_sost_tipo["Labor"].map(mapa_tipo).fillna("Sin clasificar")
                    shot_tipo = df_sost_tipo.groupby("Tipo")[_sost_col].sum()
                    if not shot_tipo.empty and shot_tipo.sum() > 0:
                        ax3.pie(shot_tipo, labels=shot_tipo.index, autopct="%1.1f%%",
                                startangle=90)
                    else:
                        ax3.text(0.5, 0.5, f"Sin datos de {_sost_label} por tipo",
                                 ha="center", va="center", transform=ax3.transAxes)
                else:
                    ax3.text(0.5, 0.5, "Sin datos de tipo de labor",
                             ha="center", va="center", transform=ax3.transAxes)
            except Exception:
                ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                         ha="center", va="center", transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax3.transAxes)

        # Gráfico 4: Sostenimiento por fase de labor
        ax4 = axes[3]
        ax4.set_title(f"{_sost_label} por Fase de Labor")
        if df_sost is not None and not df_sost.empty and _sost_col in df_sost.columns:
            try:
                df_labores = self.model._leer_labores_df()
                fase_ok = (not df_labores.empty and "Fase" in df_labores.columns
                           and df_labores["Fase"].notna().any()
                           and df_labores["Fase"].astype(str).str.strip().ne("").any())
                if fase_ok:
                    mapa_fase = df_labores.set_index("Labor")["Fase"].to_dict()
                    df_sost_fase = df_sost.copy()
                    df_sost_fase["Fase"] = df_sost_fase["Labor"].map(mapa_fase).fillna("Sin fase")
                    shot_fase = df_sost_fase.groupby("Fase")[_sost_col].sum()
                    if not shot_fase.empty and shot_fase.sum() > 0:
                        shot_fase.plot(kind="bar", ax=ax4, color=["#4a90d9", "#e67e22", "#27ae60"])
                        ax4.set_xlabel("Fase")
                        ax4.set_ylabel("Cantidad")
                        ax4.tick_params(axis="x", rotation=20)
                    else:
                        ax4.text(0.5, 0.5, f"Sin datos de {_sost_label} por fase",
                                 ha="center", va="center", transform=ax4.transAxes)
                else:
                    ax4.text(0.5, 0.5, "Sin datos de fase disponibles",
                             ha="center", va="center", transform=ax4.transAxes)
            except Exception:
                ax4.text(0.5, 0.5, "Sin datos para el período seleccionado",
                         ha="center", va="center", transform=ax4.transAxes)
        else:
            ax4.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax4.transAxes)

        fig.tight_layout()

        # Close previous figure to free memory before storing the new one
        prev_fig = getattr(self, "_fig_actual", None)
        if prev_fig is not None:
            try:
                import matplotlib.pyplot as plt
                plt.close(prev_fig)
            except Exception as exc:  # noqa: BLE001 — plt.close can raise various errors
                pass
        self._fig_actual = fig
        self._axes_actual = axes
        canvas = FigureCanvasTkAgg(fig, master=self.frame_graficos)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _exportar_png(self):
        """Exporta el gráfico actual como archivo PNG."""
        fig = getattr(self, "_fig_actual", None)
        if fig is None:
            from tkinter import messagebox
            messagebox.showinfo("Sin gráfico", "Primero genere el gráfico con 'Actualizar'.")
            return
        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Exportar gráfico como PNG",
        )
        if ruta:
            fig.savefig(ruta, dpi=200, bbox_inches="tight")
            from tkinter import messagebox
            messagebox.showinfo("Exportado", f"Gráfico guardado en:\n{ruta}")

    def _exportar_grafica_individual(self):
        """Exporta una sola gráfica seleccionada como PNG."""
        from matplotlib.figure import Figure
        fig = getattr(self, "_fig_actual", None)
        axes = getattr(self, "_axes_actual", None)
        if fig is None or axes is None:
            messagebox.showinfo("Sin gráfico", "Primero genere el gráfico con 'Actualizar'.")
            return

        seleccion = self._export_graph_var.get()
        try:
            idx = int(seleccion.split(" ")[0]) - 1
        except (ValueError, IndexError):
            idx = 0
        if idx < 0 or idx >= len(axes):
            idx = 0

        from tkinter import filedialog
        ruta = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="Exportar gráfica individual como PNG",
        )
        if not ruta:
            return

        # Exportar solo el área del subplot seleccionado
        renderer = fig.canvas.get_renderer()
        extent = axes[idx].get_tightbbox(renderer).transformed(fig.dpi_scale_trans.inverted())
        fig.savefig(ruta, dpi=200, bbox_inches=extent)
        messagebox.showinfo("Exportado", f"Gráfica guardada en:\n{ruta}")


class VentanaConfiguracion(tk.Toplevel):
    """Panel de configuración de la aplicación"""

    def __init__(self, parent, callback_cerrar=None):
        super().__init__(parent)
        self.callback_cerrar = callback_cerrar
        self.title("Configuración")
        self.geometry("480x700")
        self.minsize(420, 550)
        self.resizable(True, True)
        self.configure(bg=PALETTE["surface"])
        self.grab_set()
        self._guardado = False
        self._crear_interfaz()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        from utils.config_manager import (
            cargar_config, CLASIFICACIONES_PREDEFINIDAS,
        )
        self._config = cargar_config()

        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚙ Configuración",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Scrollable content
        canvas = tk.Canvas(self, bg=PALETTE["surface"], highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # ── Turnos ──────────────────────────────────────────────────────
        frame_turnos = ttk.LabelFrame(content, text="Turnos disponibles", padding=10)
        frame_turnos.pack(fill="x", padx=15, pady=5)

        self.listbox_turnos = tk.Listbox(frame_turnos, height=3)
        for t in self._config.get("turnos", []):
            self.listbox_turnos.insert(tk.END, t)
        self.listbox_turnos.pack(fill="x")

        frame_turno_btns = ttk.Frame(frame_turnos)
        frame_turno_btns.pack(fill="x", pady=4)
        ttk.Button(frame_turno_btns, text="➕ Agregar turno",
                   command=self._agregar_turno).pack(side="left", padx=5)
        ttk.Button(frame_turno_btns, text="🗑 Eliminar seleccionado",
                   command=self._eliminar_turno).pack(side="left", padx=5)

        # Horarios de inicio de turno
        frame_horarios = ttk.Frame(frame_turnos)
        frame_horarios.pack(fill="x", pady=4)
        ttk.Label(frame_horarios, text="Inicio turno día:").pack(side="left", padx=5)
        self.turno_dia_inicio_var = tk.StringVar(
            value=self._config.get("turno_dia_inicio", "07:30"))
        ttk.Entry(frame_horarios, textvariable=self.turno_dia_inicio_var, width=7).pack(
            side="left", padx=2)
        ttk.Label(frame_horarios, text="Inicio turno noche:").pack(side="left", padx=(12, 5))
        self.turno_noche_inicio_var = tk.StringVar(
            value=self._config.get("turno_noche_inicio", "19:30"))
        ttk.Entry(frame_horarios, textvariable=self.turno_noche_inicio_var, width=7).pack(
            side="left", padx=2)
        ttk.Label(frame_turnos,
                  text="ℹ El turno noche que cruza medianoche pertenece a la fecha en que inició.",
                  font=("Segoe UI", 8), foreground=PALETTE["text_muted"]).pack(
            anchor="w", pady=(2, 0))

        # ── Clasificaciones activas ─────────────────────────────────────
        frame_clasif = ttk.LabelFrame(content, text="Clasificaciones de sostenimiento", padding=10)
        frame_clasif.pack(fill="x", padx=15, pady=5)

        ttk.Label(frame_clasif, text="Seleccione los sistemas de clasificación activos:").pack(
            anchor="w", pady=(0, 5))

        activas = set(self._config.get("clasificaciones_activas", ["RMR"]))
        personalizadas = self._config.get("clasificaciones_personalizadas", [])
        todas = list(CLASIFICACIONES_PREDEFINIDAS) + [
            {"id": c["id"], "nombre": c["nombre"], "predefinida": False}
            for c in personalizadas if isinstance(c, dict) and "id" in c
        ]

        self._clasif_vars = {}
        for clas in todas:
            var = tk.BooleanVar(value=(clas["id"] in activas))
            self._clasif_vars[clas["id"]] = var
            ttk.Checkbutton(frame_clasif, text=clas["nombre"], variable=var).pack(
                anchor="w", padx=10, pady=1)

        # Añadir clasificación personalizada
        frame_custom_clasif = ttk.Frame(frame_clasif)
        frame_custom_clasif.pack(fill="x", pady=5)
        ttk.Label(frame_custom_clasif, text="Nueva:").pack(side="left", padx=2)
        self._nueva_clasif_id = tk.StringVar()
        ttk.Entry(frame_custom_clasif, textvariable=self._nueva_clasif_id, width=10).pack(
            side="left", padx=2)
        ttk.Label(frame_custom_clasif, text="Nombre:").pack(side="left", padx=2)
        self._nueva_clasif_nombre = tk.StringVar()
        ttk.Entry(frame_custom_clasif, textvariable=self._nueva_clasif_nombre, width=18).pack(
            side="left", padx=2)
        ttk.Button(frame_custom_clasif, text="➕",
                   command=lambda: self._agregar_clasificacion(frame_clasif)).pack(side="left", padx=4)

        # ── Backup automático ───────────────────────────────────────────
        frame_backup = ttk.LabelFrame(content, text="Respaldo Automático", padding=8)
        frame_backup.pack(fill="x", padx=15, pady=4)
        self.backup_var = tk.BooleanVar(value=self._config.get("backup_automatico", True))
        ttk.Checkbutton(frame_backup, text="Activar respaldo automático al guardar",
                        variable=self.backup_var).pack(anchor="w")

        # ── Color de fondo ──────────────────────────────────────────────
        frame_color = ttk.LabelFrame(content, text="Color de fondo (hex)", padding=8)
        frame_color.pack(fill="x", padx=15, pady=4)
        self.color_var = tk.StringVar(value=self._config.get("theme_color", WINDOW_BG_COLOR))
        ttk.Entry(frame_color, textvariable=self.color_var, width=15).pack(side="left", padx=5)
        ttk.Button(frame_color, text="Previsualizar",
                   command=self._previsualizar_color).pack(side="left", padx=5)

        # ── Contraseña de edición ───────────────────────────────────────
        frame_pwd = ttk.LabelFrame(content, text="Contraseña para editar registros >24h", padding=8)
        frame_pwd.pack(fill="x", padx=15, pady=4)
        self.pwd_var = tk.StringVar(value=self._config.get("password_edicion", "admin1234"))
        self._pwd_entry = ttk.Entry(frame_pwd, textvariable=self.pwd_var, width=20, show="*")
        self._pwd_entry.pack(side="left", padx=5)

        def _toggle_pwd():
            if self._pwd_entry.cget("show") == "*":
                self._pwd_entry.config(show="")
                btn_mostrar.config(text="🙈 Ocultar")
            else:
                self._pwd_entry.config(show="*")
                btn_mostrar.config(text="👁 Mostrar")

        btn_mostrar = ttk.Button(frame_pwd, text="👁 Mostrar", command=_toggle_pwd)
        btn_mostrar.pack(side="left")

        # ── Botones finales ─────────────────────────────────────────────
        frame_btns = tk.Frame(content, bg=PALETTE["surface"])
        frame_btns.pack(pady=12)

        def _cfgplace(text, command, style="primary"):
            b = _make_styled_btn(frame_btns, text, command, style=style, padx=14, pady=6)
            b.pack(side="left", padx=10)
            return b

        _cfgplace("💾 Guardar configuración", self._guardar,   "primary")
        _cfgplace("✕ Cancelar",               self._cancelar, "danger")

    def _agregar_clasificacion(self, parent_frame):
        """Añade una clasificación personalizada"""
        import re
        from utils.config_manager import CLASIFICACIONES_PREDEFINIDAS
        cid = self._nueva_clasif_id.get().strip()
        nombre = self._nueva_clasif_nombre.get().strip()
        if not cid or not nombre:
            messagebox.showwarning("Advertencia", "Ingrese ID y nombre.", parent=self)
            return
        cid = re.sub(r"[^a-zA-Z0-9_]", "_", cid).upper()
        # Validar que no colisione con predefinidas o existentes
        ids_predefinidas = {c["id"] for c in CLASIFICACIONES_PREDEFINIDAS}
        if cid in ids_predefinidas:
            messagebox.showwarning("Advertencia",
                                   f"'{cid}' es una clasificación predefinida.", parent=self)
            return
        if cid in self._clasif_vars:
            messagebox.showinfo("Info", "Esa clasificación ya existe.", parent=self)
            return
        # Añadir a personalizadas en config
        personalizadas = self._config.get("clasificaciones_personalizadas", [])
        personalizadas.append({"id": cid, "nombre": nombre})
        self._config["clasificaciones_personalizadas"] = personalizadas
        # Añadir checkbox
        var = tk.BooleanVar(value=True)
        self._clasif_vars[cid] = var
        ttk.Checkbutton(parent_frame, text=nombre, variable=var).pack(
            anchor="w", padx=10, pady=1)
        self._nueva_clasif_id.set("")
        self._nueva_clasif_nombre.set("")

    def _agregar_turno(self):
        win = tk.Toplevel(self)
        win.title("Nuevo turno")
        win.geometry("280x100")
        win.grab_set()
        ttk.Label(win, text="Nombre del turno:").pack(pady=8)
        var = tk.StringVar()
        ttk.Entry(win, textvariable=var, width=20).pack()
        def _ok():
            nombre = var.get().strip()
            if nombre:
                self.listbox_turnos.insert(tk.END, nombre)
            win.destroy()
        ttk.Button(win, text="Agregar", command=_ok).pack(pady=5)

    def _eliminar_turno(self):
        sel = self.listbox_turnos.curselection()
        if sel:
            self.listbox_turnos.delete(sel[0])

    def _previsualizar_color(self):
        try:
            self.configure(bg=self.color_var.get())
        except Exception:
            messagebox.showwarning("Color inválido", "El código de color no es válido.", parent=self)

    def _guardar(self):
        from utils.config_manager import guardar_config
        self._config["turnos"] = list(self.listbox_turnos.get(0, tk.END))
        self._config["turno_dia_inicio"] = self.turno_dia_inicio_var.get().strip()
        self._config["turno_noche_inicio"] = self.turno_noche_inicio_var.get().strip()
        self._config["backup_automatico"] = self.backup_var.get()
        self._config["theme_color"] = self.color_var.get()
        self._config["password_edicion"] = self.pwd_var.get()
        # Guardar clasificaciones activas
        self._config["clasificaciones_activas"] = [
            cid for cid, var in self._clasif_vars.items() if var.get()
        ]
        if guardar_config(self._config):
            self._guardado = True
            messagebox.showinfo("Configuración", "Configuración guardada correctamente.", parent=self)
            self.destroy()
            if self.callback_cerrar:
                self.callback_cerrar()
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuración.", parent=self)

    def _cancelar(self):
        self.destroy()


# ── Funciones auxiliares globales ────────────────────────────────────────────

def _aplicar_modo_oscuro(root, activar: bool):
    """Aplica o desactiva el modo oscuro en toda la interfaz, incluyendo
    todas las ventanas Toplevel que estén abiertas en ese momento."""
    if activar:
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        btn_bg = "#313244"
        card_bg = "#2a2a3c"
        card_border = "#3b3b50"
        entry_bg = "#313244"
        status_bg = "#1a1a2a"
        status_fg = "#8b8fa3"
    else:
        bg = WINDOW_BG_COLOR
        fg = "#222222"
        btn_bg = "#e0e0e0"
        card_bg = PALETTE["card_bg"]
        card_border = PALETTE["card_border"]
        entry_bg = "#ffffff"
        status_bg = "#e8edf2"
        status_fg = PALETTE["text_muted"]

    style = ttk.Style()
    try:
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=btn_bg, foreground=fg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TCombobox", fieldbackground=entry_bg, foreground=fg,
                        background=btn_bg, selectbackground=PALETTE["primary"],
                        selectforeground="#ffffff")
        style.configure("TEntry", fieldbackground=entry_bg, foreground=fg)
        style.configure("Treeview", background=card_bg, foreground=fg,
                        fieldbackground=card_bg)
        style.configure("Treeview.Heading", background=btn_bg, foreground=fg)
        style.configure("Custom.Treeview", background=card_bg, foreground=fg,
                        fieldbackground=card_bg)
        style.configure("Custom.Treeview.Heading",
                        background=PALETTE["sidebar_bg"], foreground="#ffffff")
        style.map("TButton", background=[("active", btn_bg)])
        style.map("TCombobox",
                  fieldbackground=[("readonly", entry_bg)],
                  foreground=[("readonly", fg)])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.map("TCheckbutton", background=[("active", bg)])
        style.configure("TScrollbar", background=btn_bg, troughcolor=bg)
    except Exception:
        pass

    # Aplicar a la ventana raíz y a todos los Toplevel abiertos
    _ventanas = [root] + [
        w for w in root.winfo_children()
        if isinstance(w, tk.Toplevel) and w.winfo_exists()
    ]
    for ventana in _ventanas:
        try:
            ventana.configure(bg=bg)
            _actualizar_widgets_colores(ventana, bg, fg, card_bg, card_border,
                                        entry_bg, status_bg, status_fg)
        except Exception:
            pass


# Colores que deben conservarse siempre (sidebar, headers oscuros)
_COLORES_PRESERVADOS = {
    PALETTE["sidebar_bg"].lower(),
    PALETTE["sidebar_active"].lower(),
}

# Colores de botones de acción que no deben cambiar
_COLORES_BOTONES_ACCION = {
    PALETTE["primary"].lower(),
    PALETTE["primary_hover"].lower(),
    PALETTE["secondary"].lower(),
    PALETTE["secondary_hover"].lower(),
    PALETTE["danger"].lower(),
    PALETTE["danger_hover"].lower(),
    PALETTE["accent"].lower(),
}


def _actualizar_widgets_colores(widget, bg, fg, card_bg="#ffffff",
                                card_border="#dde3ec", entry_bg="#ffffff",
                                status_bg="#e8edf2", status_fg="#6b7280"):
    """Recorre widgets de tkinter (no ttk) y actualiza colores,
    preservando los que tienen fondo de sidebar/header (siempre oscuros)."""
    try:
        widget_class = widget.winfo_class()

        # Verificar si el widget tiene un color que debe conservarse (sidebar/header)
        try:
            current_bg = widget.cget("bg")
            current_bg_lower = str(current_bg).lower()
        except Exception:
            current_bg_lower = ""

        is_preserved = current_bg_lower in _COLORES_PRESERVADOS

        if not is_preserved:
            if widget_class == "Button":
                # Preservar botones de acción (primarios, secundarios, peligro)
                if current_bg_lower not in _COLORES_BOTONES_ACCION:
                    try:
                        widget.configure(bg=bg, fg=fg)
                    except Exception:
                        pass

            elif widget_class in ("Label", "Frame"):
                # Detectar cards (frames con card_bg or card_border backgrounds)
                is_card_border = current_bg_lower in (
                    PALETTE["card_border"].lower(), "#dde3ec"
                )
                is_card_bg = current_bg_lower in (
                    PALETTE["card_bg"].lower(), "#ffffff"
                )
                is_status = current_bg_lower == "#e8edf2"

                if is_card_border:
                    try:
                        widget.configure(bg=card_border)
                    except Exception:
                        pass
                elif is_status:
                    try:
                        widget.configure(bg=status_bg)
                        if widget_class == "Label":
                            widget.configure(fg=status_fg)
                    except Exception:
                        pass
                elif is_card_bg:
                    try:
                        widget.configure(bg=card_bg)
                        if widget_class == "Label":
                            widget.configure(fg=fg)
                    except Exception:
                        pass
                else:
                    try:
                        widget.configure(bg=bg)
                    except Exception:
                        pass
                    if widget_class == "Label":
                        try:
                            widget.configure(fg=fg)
                        except Exception:
                            pass

            elif widget_class == "Listbox":
                try:
                    widget.configure(bg=card_bg, fg=fg,
                                     selectbackground=PALETTE["primary"],
                                     selectforeground="#ffffff")
                except Exception:
                    pass

            elif widget_class == "Text":
                try:
                    widget.configure(bg=entry_bg, fg=fg,
                                     insertbackground=fg,
                                     highlightbackground=card_border)
                except Exception:
                    pass

            elif widget_class == "Canvas":
                try:
                    widget.configure(bg=bg)
                except Exception:
                    pass

        # Siempre recurrir en los hijos (incluso si el widget padre está preservado)
        for child in widget.winfo_children():
            _actualizar_widgets_colores(child, bg, fg, card_bg, card_border,
                                        entry_bg, status_bg, status_fg)
    except Exception:
        pass


def _mostrar_vista_previa(parent, df, titulo: str, callback_confirmar):
    """
    Muestra una ventana de vista previa con los registros del DataFrame.
    Llama a callback_confirmar() si el usuario confirma.
    """
    win = tk.Toplevel(parent)
    win.title(titulo)
    win.geometry("860x400")
    win.grab_set()

    ttk.Label(win, text=titulo, font=("Segoe UI", 11, "bold")).pack(pady=8)
    ttk.Label(win, text=f"Se incluirán {len(df)} registro(s) en el PDF.").pack()

    cols = list(df.columns)
    tree = ttk.Treeview(win, columns=cols, show="headings", height=12)
    for col in cols:
        tree.heading(col, text=col)
        tree.column(col, anchor="center", width=max(80, len(col) * 8))
    tree.pack(fill="both", expand=True, padx=10, pady=8)

    sb = ttk.Scrollbar(tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")

    for _, row in df.iterrows():
        tree.insert("", "end", values=list(row))

    frame_btn = ttk.Frame(win)
    frame_btn.pack(pady=8)

    def _confirmar():
        win.destroy()
        callback_confirmar()

    ttk.Button(frame_btn, text="✅ Confirmar y Generar PDF",
               command=_confirmar).pack(side="left", padx=10)
    ttk.Button(frame_btn, text="❌ Cancelar",
               command=win.destroy).pack(side="left", padx=10)


# ── Nuevas clases ─────────────────────────────────────────────────────────────

class VentanaRegistroFotografico(tk.Toplevel):
    """Ventana para gestionar el registro fotográfico vinculado a labores.

    Permite seleccionar una labor, ver las imágenes asociadas y abrir el
    anotador para añadir o editar imágenes de esa labor.
    """

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Registro Fotográfico por Labor")
        self.geometry("860x540")
        self.minsize(700, 400)
        self.resizable(True, True)
        self.configure(bg=PALETTE["surface"])
        self._registros_labor: list[dict] = []
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    # ---------------------------------------------------------------- UI

    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📷 Registro Fotográfico por Labor",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        # Selector de labor
        top = tk.Frame(self, bg=PALETTE["surface"])
        top.pack(fill="x", padx=14, pady=10)

        tk.Label(top, text="Seleccionar Labor:", font=("Segoe UI", 9),
                 bg=PALETTE["surface"]).pack(side="left", padx=(0, 6))

        self._labor_var = tk.StringVar()
        labores = self.model.obtener_labores_guardadas()
        self._combo_labor = ttk.Combobox(top, textvariable=self._labor_var,
                                         values=labores, width=28, state="readonly")
        self._combo_labor.pack(side="left")
        self._combo_labor.bind("<<ComboboxSelected>>", self._on_labor_seleccionada)

        btn_buscar = _make_styled_btn(top, "🔍 Cargar imágenes", self._cargar_imagenes,
                                      style="primary", padx=10, pady=4)
        btn_buscar.pack(side="left", padx=8)

        # Tabla de registros con imagen
        cols = ["Fecha", "Turno", "Imagen"]
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=10,
                                   style="Custom.Treeview")
        for col in cols:
            self._tree.heading(col, text=col)
        self._tree.column("Fecha", width=110, anchor="center")
        self._tree.column("Turno", width=80, anchor="center")
        self._tree.column("Imagen", width=400, anchor="w")
        self._tree.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        sb = ttk.Scrollbar(self._tree, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_doble_click)

        # Botones inferiores
        frame_btns = tk.Frame(self, bg=PALETTE["surface"])
        frame_btns.pack(pady=8)

        _make_styled_btn(frame_btns, "🖼 Ver / Anotar imagen seleccionada",
                         self._abrir_imagen_seleccionada, style="secondary",
                         padx=10, pady=5).pack(side="left", padx=6)
        _make_styled_btn(frame_btns, "📷 Nueva imagen para la labor",
                         self._nueva_imagen_labor, style="primary",
                         padx=10, pady=5).pack(side="left", padx=6)
        _make_styled_btn(frame_btns, "✕ Cerrar", self.destroy,
                         style="danger", padx=10, pady=5).pack(side="left", padx=6)

    # ---------------------------------------------------------------- lógica

    def _on_labor_seleccionada(self, _event=None):
        self._cargar_imagenes()

    def _cargar_imagenes(self):
        """Carga los registros con imagen para la labor seleccionada."""
        labor = self._labor_var.get().strip()
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._registros_labor.clear()

        if not labor:
            return

        try:
            import pandas as pd
            df = self.model.obtener_bitacora()
            if df.empty:
                return
            df_labor = df[df["Labor"] == labor].copy()
            if "imagen_path" not in df_labor.columns:
                return
            df_con_img = df_labor[
                df_labor["imagen_path"].notna() &
                (df_labor["imagen_path"].astype(str).str.strip() != "")
            ]
            for _, row in df_con_img.iterrows():
                from pathlib import Path
                img_path = str(row.get("imagen_path", ""))
                nombre_img = Path(img_path).name if img_path else "—"
                self._registros_labor.append(dict(row))
                self._tree.insert("", "end",
                                  values=(row.get("Fecha", ""),
                                          row.get("Turno", ""),
                                          nombre_img))
            if not df_con_img.empty:
                pass
            elif df_labor.empty:
                pass
        except Exception:
            pass

    def _registro_seleccionado(self) -> dict | None:
        sel = self._tree.selection()
        if not sel:
            return None
        idx = self._tree.index(sel[0])
        if idx < len(self._registros_labor):
            return self._registros_labor[idx]
        return None

    def _abrir_imagen_seleccionada(self):
        """Abre el anotador con la imagen del registro seleccionado."""
        reg = self._registro_seleccionado()
        if reg is None:
            from tkinter import messagebox
            messagebox.showwarning("Sin selección",
                                   "Seleccione un registro de la lista.", parent=self)
            return
        img_path = reg.get("imagen_path", "")
        labor = reg.get("Labor", "")
        VentanaAnotador(self, image_path=img_path if img_path else None,
                        labor_name=labor)

    def _on_doble_click(self, _event):
        """Doble clic en la tabla abre el anotador."""
        self._abrir_imagen_seleccionada()

    def _nueva_imagen_labor(self):
        """Abre el anotador en blanco para la labor seleccionada."""
        labor = self._labor_var.get().strip()
        if not labor:
            from tkinter import messagebox
            messagebox.showwarning("Sin labor",
                                   "Seleccione una labor primero.", parent=self)
            return
        VentanaAnotador(self, labor_name=labor)


class VentanaSostenimientos(tk.Toplevel):
    """
    Ventana para gestionar la lista de sostenimientos activos.
    Muestra checkboxes de la lista predeterminada + campo para añadir custom.
    Los activos se guardan en config.json como 'sostenimientos_activos'.
    """

    def __init__(self, parent, on_actualizar=None):
        super().__init__(parent)
        self._on_actualizar = on_actualizar
        self.title("Gestionar Sostenimientos")
        self.geometry("480x600")
        self.minsize(400, 450)
        self.resizable(True, True)
        self.configure(bg=PALETTE["surface"])
        self.grab_set()
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        from utils.config_manager import cargar_config
        self._config = cargar_config()

        catalogo = self._config.get("sostenimientos_catalogo", [])
        activos_columnas = {s["columna"] for s in self._config.get("sostenimientos_activos", [])
                            if isinstance(s, dict)}

        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚙ Gestionar Tipos de Sostenimiento",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        frame_lista = ttk.LabelFrame(self, text="Seleccionar sostenimientos activos", padding=10)
        frame_lista.pack(fill="both", expand=True, padx=15, pady=5)

        canvas = tk.Canvas(frame_lista, height=300)
        sb = ttk.Scrollbar(frame_lista, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self._check_vars = {}
        self._catalogo_items = list(catalogo)

        for item in self._catalogo_items:
            col = item["columna"]
            var = tk.BooleanVar(value=(col in activos_columnas))
            self._check_vars[col] = (var, item)
            ttk.Checkbutton(inner, text=item["display"], variable=var).pack(anchor="w", padx=5, pady=2)

        # Añadir sostenimiento personalizado
        frame_custom = ttk.LabelFrame(self, text="Añadir sostenimiento personalizado", padding=8)
        frame_custom.pack(fill="x", padx=15, pady=5)

        ttk.Label(frame_custom, text="Nombre:").grid(row=0, column=0, padx=5)
        self._custom_display_var = tk.StringVar()
        ttk.Entry(frame_custom, textvariable=self._custom_display_var, width=22).grid(row=0, column=1, padx=5)

        ttk.Label(frame_custom, text="Tipo:").grid(row=0, column=2, padx=4)
        self._custom_tipo_var = tk.StringVar(value="int")
        ttk.Combobox(frame_custom, textvariable=self._custom_tipo_var,
                     values=["int", "float"], width=6, state="readonly").grid(row=0, column=3, padx=4)

        ttk.Button(frame_custom, text="➕ Añadir",
                   command=lambda: self._anadir_custom(inner, activos_columnas)).grid(
            row=1, column=0, columnspan=4, pady=6)

        # Botones
        frame_btns = tk.Frame(self, bg=PALETTE["surface"])
        frame_btns.pack(pady=10)

        def _sostplace(text, command, style="primary"):
            b = _make_styled_btn(frame_btns, text, command, style=style, padx=14, pady=6)
            b.pack(side="left", padx=10)
            return b

        _sostplace("💾 Guardar",  self._guardar, "primary")
        _sostplace("✕ Cancelar", self.destroy,   "danger")

        self._inner_frame = inner

    def _anadir_custom(self, inner, activos_columnas):
        """Añade un sostenimiento personalizado al catálogo y a los checkboxes."""
        display = self._custom_display_var.get().strip()
        if not display:
            messagebox.showwarning("Advertencia", "Ingrese un nombre.", parent=self)
            return
        tipo = self._custom_tipo_var.get()
        # Generar nombre de columna seguro
        import re
        col = re.sub(r"[^a-zA-Z0-9]", "_", display)
        if col in self._check_vars:
            messagebox.showinfo("Info", "Ese sostenimiento ya existe.", parent=self)
            return
        item = {"display": display, "columna": col, "tipo": tipo}
        self._catalogo_items.append(item)
        var = tk.BooleanVar(value=True)
        self._check_vars[col] = (var, item)
        ttk.Checkbutton(inner, text=display, variable=var).pack(anchor="w", padx=5, pady=2)
        self._custom_display_var.set("")

    def _guardar(self):
        from utils.config_manager import guardar_config
        self._config["sostenimientos_catalogo"] = self._catalogo_items
        activos = [item for col, (var, item) in self._check_vars.items() if var.get()]
        self._config["sostenimientos_activos"] = activos
        if guardar_config(self._config):
            messagebox.showinfo("Guardado", "Sostenimientos guardados correctamente.",
                                parent=self)
            self.destroy()
            if self._on_actualizar:
                self._on_actualizar()
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuración.", parent=self)


class VentanaReportePeriodo(tk.Toplevel):
    """Ventana para generar un reporte PDF consolidado por período."""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Reporte de Período")
        self.geometry("420x240")
        self.minsize(380, 200)
        self.resizable(True, True)
        self.configure(bg=PALETTE["surface"])
        self.grab_set()
        self._crear_interfaz()
        _aplicar_modo_oscuro_si_activo(self)

    def _crear_interfaz(self):
        # Header
        header = tk.Frame(self, bg=PALETTE["sidebar_bg"], height=48)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📅 Reporte por Período",
                 font=("Segoe UI", 13, "bold"), fg="#ffffff",
                 bg=PALETTE["sidebar_bg"]).pack(fill="x", pady=12, padx=16)

        frame_f = tk.Frame(self, bg=PALETTE["surface"])
        frame_f.pack(pady=10)

        ttk.Label(frame_f, text="Desde:").grid(row=0, column=0, padx=8)
        self.fi = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        self.fi.grid(row=0, column=1, padx=8)

        ttk.Label(frame_f, text="Hasta:").grid(row=0, column=2, padx=8)
        self.ff = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        self.ff.grid(row=0, column=3, padx=8)

        frame_btn = tk.Frame(self, bg=PALETTE["surface"])
        frame_btn.pack(pady=12)

        def _rpplace(text, command, style="primary"):
            b = _make_styled_btn(frame_btn, text, command, style=style, padx=14, pady=6)
            b.pack(side="left", padx=8)
            return b

        _rpplace("🔍 Vista Previa y Generar", self._previsualizar, "primary")
        _rpplace("✕ Cerrar",                  self.destroy,        "danger")

    def _previsualizar(self):
        fi_str = self.fi.get()
        ff_str = self.ff.get()
        df = self.model.buscar_registros("", fi_str, ff_str)
        if df.empty:
            messagebox.showinfo("Info", "No hay registros en el período seleccionado.", parent=self)
            return

        _mostrar_vista_previa(
            self,
            df,
            titulo=f"Reporte Período {fi_str} — {ff_str}",
            callback_confirmar=lambda: self._generar_pdf(df, fi_str, ff_str)
        )

    def _generar_pdf(self, df, fi_str, ff_str):
        """Genera PDF del período con diseño visual mejorado."""
        from utils.config_manager import obtener_clasificaciones_activas

        # Ordenar por labor numéricamente
        df = ordenar_df_por_labor(df)

        fi_arch = fi_str.replace("/", "-")
        ff_arch = ff_str.replace("/", "-")
        nombre = f"reporte_periodo_{fi_arch}_{ff_arch}.pdf"

        try:
            activas = obtener_clasificaciones_activas()
            estilos = _crear_estilos_pdf()

            # Columnas a mostrar según clasificaciones activas
            cols_clasificacion = [c for c in ["GSI", "RMR"] if c in activas and c in df.columns]
            cols_mostrar = ["Fecha", "Turno", "Labor"] + cols_clasificacion + ["Soporte", "Observaciones"]
            cols_mostrar = [c for c in cols_mostrar if c in df.columns]

            ancho_base = {"Fecha": 60, "Turno": 42, "Labor": 85,
                          "GSI": 34, "RMR": 34,
                          "Soporte": 125, "Observaciones": 125}
            col_widths = [ancho_base.get(c, 60) for c in cols_mostrar]

            clasificaciones_texto = " · ".join(activas) if activas else "Sin clasificación"
            lineas_info = [
                f"<b>Período:</b> {fi_str} al {ff_str}",
                f"<b>Total de registros:</b> {len(df)}",
                f"<b>Clasificaciones activas:</b> {clasificaciones_texto}",
                f"<b>Generado:</b> {obtener_fecha_actual()}",
            ]

            pdf = SimpleDocTemplate(
                nombre,
                pagesize=landscape(letter),
                leftMargin=2*cm, rightMargin=2*cm,
                topMargin=2*cm, bottomMargin=2*cm,
            )
            elementos = []

            # Encabezado
            elementos += _construir_bloque_header_pdf(
                estilos, "📅  REPORTE DE PERÍODO — GEOMECÁNICA", lineas_info
            )

            # Tabla principal de registros
            encabezado = cols_mostrar[:]
            datos_tabla = [encabezado]
            for _, row in df.iterrows():
                fila = []
                for col in cols_mostrar:
                    val = str(row[col]) if str(row[col]) != "nan" else ""
                    if col in ("Soporte", "Observaciones"):
                        fila.append(Paragraph(val, estilos["normal"]))
                    else:
                        fila.append(val)
                datos_tabla.append(fila)

            tabla = Table(datos_tabla, colWidths=col_widths, repeatRows=1)
            tabla.setStyle(_tabla_estilo_principal(col_widths, encabezado))
            elementos.append(tabla)
            elementos.append(Spacer(1, 18))

            # Sección de estadísticas
            elementos.append(Paragraph("Estadísticas del Período", estilos["seccion"]))
            elementos.append(HRFlowable(width="100%", thickness=0.5, color=_PDF_GRID))
            elementos.append(Spacer(1, 6))

            try:
                import pandas as pd
                stat_rows = [["Indicador", "Valor"]]

                if "Labor" in df.columns and not df["Labor"].empty:
                    top = df["Labor"].value_counts().idxmax()
                    stat_rows.append(["Labor con más registros", str(top)])

                if "Turno" in df.columns:
                    for t, n in df["Turno"].value_counts().items():
                        stat_rows.append([f"Registros turno {t}", str(n)])

                if len(stat_rows) > 1:
                    tbl_stat = Table(stat_rows, colWidths=[200, 120])
                    tbl_stat.setStyle(TableStyle([
                        ("BACKGROUND",  (0, 0), (-1, 0), _PDF_SUBHEADER),
                        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE",    (0, 0), (-1, -1), 8),
                        ("ALIGN",       (0, 1), (-1, -1), "CENTER"),
                        ("ALIGN",       (0, 0), (0, -1), "LEFT"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
                        ("GRID",        (0, 0), (-1, -1), 0.4, _PDF_GRID),
                        ("TOPPADDING",  (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    elementos.append(tbl_stat)
                    elementos.append(Spacer(1, 14))

                # Totales de sostenimiento
                df_s2 = self.model.obtener_totales_sostenimiento(
                    fecha_inicio=fi_str, fecha_fin=ff_str
                )
                if not df_s2.empty:
                    elementos.append(Paragraph("Totales de Sostenimiento por Labor", estilos["seccion"]))
                    elementos.append(HRFlowable(width="100%", thickness=0.5, color=_PDF_GRID))
                    elementos.append(Spacer(1, 6))
                    cols_s = list(df_s2.columns)
                    datos_s = [cols_s]
                    for _, row in df_s2.iterrows():
                        datos_s.append([str(row[c]) if str(row[c]) != "nan" else "" for c in cols_s])
                    # Distribute widths evenly
                    total_w = sum(col_widths)
                    w_per = max(50, total_w // max(len(cols_s), 1))
                    tabla_s = Table(datos_s, colWidths=[w_per] * len(cols_s), repeatRows=1)
                    tabla_s.setStyle(TableStyle([
                        ("BACKGROUND",  (0, 0), (-1, 0), _PDF_ACCENT),
                        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
                        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE",    (0, 0), (-1, -1), 7),
                        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PDF_ROW_EVEN, _PDF_ROW_ODD]),
                        ("GRID",        (0, 0), (-1, -1), 0.4, _PDF_GRID),
                        ("TOPPADDING",  (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    elementos.append(tabla_s)
            except Exception:
                pass

            pdf.build(elementos, onFirstPage=_pie_pagina, onLaterPages=_pie_pagina)
            messagebox.showinfo("PDF generado",
                                f"Reporte guardado como:\n{nombre}", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}", parent=self)

