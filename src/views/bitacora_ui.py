"""
Interfaz gráfica de la Bitácora Geomecánica
Separada de la lógica de datos
"""
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
from tkcalendar import DateEntry
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from models.bitacora_model import BitacoraModel
from utils.config import (
    APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_BG_COLOR, TURNOS
)
from utils.helpers import (
    obtener_fecha_actual, validar_rmr, validar_gsi,
    validar_campos_obligatorios, _obtener_turno_automatico
)
from utils.config_manager import cargar_config as _cargar_config

_SECONDS_IN_24H = 86400


class BitacoraApp:
    """Aplicación principal de la Bitácora Geomecánica"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
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
        """Crea la interfaz gráfica principal"""
        # Estilo
        style = ttk.Style()
        style.theme_use("clam")
        
        # Título
        titulo = tk.Label(
            self.root,
            text=APP_NAME,
            font=("Segoe UI", 18, "bold"),
            bg=WINDOW_BG_COLOR
        )
        titulo.pack(pady=10)
        
        # Subtítulo
        subtitulo = tk.Label(
            self.root,
            text="Registro de condiciones del macizo rocoso",
            font=("Segoe UI", 10),
            bg=WINDOW_BG_COLOR
        )
        subtitulo.pack()
        
        # Frame principal
        frame_principal = ttk.Frame(self.root, padding=20)
        frame_principal.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Fecha
        ttk.Label(frame_principal, text="Fecha").grid(row=0, column=0, sticky="w")
        ttk.Label(
            frame_principal,
            text=obtener_fecha_actual()
        ).grid(row=0, column=1, sticky="w")
        
        # Turno
        ttk.Label(frame_principal, text="Turno").grid(row=1, column=0, sticky="w")
        combo_turno = ttk.Combobox(
            frame_principal,
            textvariable=self.turno_var,
            state="readonly",
            values=TURNOS
        )
        combo_turno.grid(row=1, column=1, sticky="ew")
        self.turno_var.set(_obtener_turno_automatico())
        
        # Labor — Entry para buscar/filtrar
        ttk.Label(frame_principal, text="Labor").grid(row=2, column=0, sticky="w")
        self.entrada_labor = ttk.Entry(frame_principal, textvariable=self.labor_var)
        self.entrada_labor.grid(row=2, column=1, sticky="ew")
        self.entrada_labor.bind("<KeyRelease>", self._filtrar_labores)
        self.entrada_labor.bind("<FocusIn>", self._filtrar_labores)
        self.entrada_labor.bind("<FocusOut>", self._ocultar_lista)

        # Listbox desplegable para mostrar sugerencias filtradas
        self.lista_filtrada = tk.Listbox(frame_principal, height=5, exportselection=False)
        self.lista_filtrada.grid(row=3, column=1, sticky="ew")
        self.lista_filtrada.bind("<<ListboxSelect>>", self._seleccionar_labor_lista)
        self.lista_filtrada.grid_remove()  # Oculta por defecto

        # Último registro / info de labor
        self.label_ultimo = ttk.Label(
            frame_principal,
            text="",
            foreground="gray"
        )
        self.label_ultimo.grid(row=3, column=0, sticky="w", pady=2)

        # GSI
        ttk.Label(frame_principal, text="GSI").grid(row=4, column=0, sticky="w")
        self.entrada_gsi = ttk.Entry(frame_principal)
        self.entrada_gsi.grid(row=4, column=1, sticky="ew")

        # RMR
        ttk.Label(frame_principal, text="RMR").grid(row=5, column=0, sticky="w")
        self.entrada_rmr = ttk.Entry(frame_principal)
        self.entrada_rmr.grid(row=5, column=1, sticky="ew")
        self.entrada_rmr.bind("<KeyRelease>", self._calcular_soporte)

        # Soporte recomendado
        ttk.Label(frame_principal, text="Soporte recomendado").grid(row=6, column=0, sticky="w")
        self.entrada_soporte = ttk.Entry(frame_principal)
        self.entrada_soporte.grid(row=6, column=1, sticky="ew")

        # Observaciones
        ttk.Label(frame_principal, text="Observaciones").grid(row=7, column=0, sticky="nw")
        self.entrada_obs = tk.Text(
            frame_principal,
            height=5,
            width=30,
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#cccccc",
            highlightcolor="#4a90d9",
            wrap="word"
        )
        self.entrada_obs.grid(row=7, column=1, sticky="ew")
        
        frame_principal.columnconfigure(1, weight=1)
        
        # Frame de botones: fila 0 (guardar), fila 1 (4 botones), fila 2 (3 botones)
        frame_botones = ttk.Frame(self.root)
        frame_botones.pack(pady=(5, 10))

        # Fila 1: Botón principal de guardar
        ttk.Button(
            frame_botones,
            text="💾  Guardar Registro",
            command=self._guardar_datos,
            width=25
        ).grid(row=0, column=0, columnspan=4, pady=(0, 8), padx=5)

        # Fila 2: 4 botones secundarios
        ttk.Button(
            frame_botones,
            text="📋 Ver Historial",
            command=self._abrir_historial,
            width=18
        ).grid(row=1, column=0, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="📄 Reporte PDF",
            command=self._generar_reporte,
            width=18
        ).grid(row=1, column=1, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="🔩 Estándar Sosten.",
            command=self._abrir_estandar,
            width=18
        ).grid(row=1, column=2, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="🏗 Gestionar Labores",
            command=self._abrir_gestion_labores,
            width=18
        ).grid(row=1, column=3, padx=4, pady=2)

        # Fila 3: Nuevos botones
        ttk.Button(
            frame_botones,
            text="🪨 Sostenimiento Diario",
            command=self._abrir_sostenimiento,
            width=18
        ).grid(row=2, column=0, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="📊 Dashboard",
            command=self._abrir_dashboard,
            width=18
        ).grid(row=2, column=1, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="⚙ Configuración",
            command=self._abrir_configuracion,
            width=18
        ).grid(row=2, column=2, padx=4, pady=2)

        ttk.Button(
            frame_botones,
            text="🗂 Gestionar Sost.",
            command=self._abrir_sostenimientos,
            width=18
        ).grid(row=2, column=3, padx=4, pady=2)

        # Fila 4: Reporte Período y Modo Oscuro
        ttk.Button(
            frame_botones,
            text="📅 Reporte Período",
            command=self._abrir_reporte_periodo,
            width=18
        ).grid(row=3, column=0, padx=4, pady=2)

        self.btn_oscuro = ttk.Button(
            frame_botones,
            text="🌙 Modo Oscuro",
            command=self._toggle_modo_oscuro,
            width=18
        )
        self.btn_oscuro.grid(row=3, column=1, padx=4, pady=2)
    
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
            "Observaciones": ValidadorBitacora.sanitizar_entrada(self.entrada_obs.get("1.0", tk.END))
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
        """Calcula automáticamente el soporte según RMR"""
        try:
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

            soporte = self.model.recomendar_soporte(rmr, tipo=tipo)
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

        VentanaConfiguracion(self.root, _al_cerrar)

    def _abrir_sostenimientos(self):
        """Abre la ventana de gestión de sostenimientos"""
        VentanaSostenimientos(self.root)

    def _abrir_reporte_periodo(self):
        """Abre la ventana de reporte por período"""
        VentanaReportePeriodo(self.root, self.model)

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
        """Genera PDF con registros del día"""
        fecha_archivo = datetime.now().strftime("%d-%m-%Y")
        nombre_archivo = f"reporte_geomecanica_{fecha_archivo}.pdf"
        
        pdf = SimpleDocTemplate(nombre_archivo, pagesize=letter)
        estilos = getSampleStyleSheet()
        elementos = []
        
        # Título
        titulo = Paragraph("REPORTE DIARIO GEOMECÁNICA", estilos['Title'])
        elementos.append(titulo)
        elementos.append(Spacer(1, 10))
        
        # Tabla
        datos = [df.columns.tolist()]
        for _, row in df.iterrows():
            fila = [
                row["Fecha"], row["Turno"], row["Labor"],
                row["GSI"], row["RMR"],
                Paragraph(str(row["Soporte"]), estilos["Normal"]),
                Paragraph(str(row["Observaciones"]), estilos["Normal"])
            ]
            datos.append(fila)
        
        tabla = Table(datos, colWidths=[60, 50, 80, 40, 40, 120, 130])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        elementos.append(tabla)
        elementos.append(Spacer(1, 40))
        
        # Firmas
        firma_tabla = Table([
            ["_______________________", "_______________________"],
            ["Geomecánica", "Supervisor"]
        ])
        firma_tabla.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        elementos.append(firma_tabla)
        
        pdf.build(elementos)
        messagebox.showinfo("PDF", f"Reporte diario generado: {nombre_archivo}")


class VentanaHistorial:
    """Ventana para ver historial de registros"""
    
    def __init__(self, parent, model):
        self.model = model
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Historial de Labores")
        self.ventana.geometry("900x600")
        self.ventana.configure(bg=WINDOW_BG_COLOR)
        self._df_actual = None
        self._indices_originales = []
        self._todos_registros = None  # cache para búsqueda global
        
        self._crear_interfaz()
    
    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de historial"""
        # Frame de búsqueda
        frame_busqueda = ttk.Frame(self.ventana)
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
        frame_global = ttk.Frame(self.ventana)
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
            height=14
        )
        
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, anchor="center")
        
        self.tabla.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        # Botones
        frame_botones = ttk.Frame(self.ventana)
        frame_botones.pack(pady=8)
        
        ttk.Button(
            frame_botones,
            text="✏ Editar seleccionado",
            command=self._editar_registro
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="🗑 Eliminar seleccionado",
            command=self._eliminar_registro
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="📊 Exportar a Excel",
            command=self._exportar_excel
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="Exportar PDF",
            command=self._exportar_pdf
        ).pack(side="left", padx=4)

        self.btn_deshacer = ttk.Button(
            frame_botones,
            text="↩ Deshacer",
            command=self._deshacer
        )
        self.btn_deshacer.pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="📦 Archivar Período",
            command=self._archivar_periodo
        ).pack(side="left", padx=4)

        ttk.Button(
            frame_botones,
            text="Cerrar",
            command=self.ventana.destroy
        ).pack(side="left", padx=4)
        
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
        
        for _, row in df.iterrows():
            self.tabla.insert("", "end", values=list(row))

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

        for _, row in df_filtrado.iterrows():
            self.tabla.insert("", "end", values=list(row))

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

        nombre_archivo = f"historial_geomecanica_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
        exito, mensaje = self.model.exportar_historial_excel(df, nombre_archivo)
        if exito:
            messagebox.showinfo("Exportar Excel", f"Archivo exportado:\n{nombre_archivo}", parent=self.ventana)
        else:
            messagebox.showerror("Error", mensaje, parent=self.ventana)
    
    def _exportar_pdf(self):
        """Exporta historial a PDF"""
        labor = self.buscar_var.get()
        fecha_inicio = self.fecha_inicio_var.get()
        fecha_fin = self.fecha_fin_var.get()
        
        df = self.model.buscar_registros(labor, fecha_inicio, fecha_fin)
        
        if df.empty:
            messagebox.showinfo("Info", "No hay datos para exportar")
            return
        
        labor_real = df["Labor"].iloc[0]
        nombre = f"historial_labor_{labor_real}.pdf".replace(" ", "_")
        
        pdf = SimpleDocTemplate(nombre, pagesize=letter)
        estilos = getSampleStyleSheet()
        elementos = []
        
        titulo = Paragraph("HISTORIAL DE LABORES - GEOMECÁNICA", estilos["Title"])
        elementos.append(titulo)
        elementos.append(Spacer(1, 10))
        
        fecha_texto = Paragraph(
            f"Fecha de exportación: {obtener_fecha_actual()}",
            estilos['Normal']
        )
        elementos.append(fecha_texto)
        elementos.append(Spacer(1, 20))
        
        subtitulo = Paragraph(f"Labor: {labor_real}", estilos["Heading2"])
        elementos.append(subtitulo)
        elementos.append(Spacer(1, 20))
        
        datos = [df.columns.tolist()]
        for _, row in df.iterrows():
            fila = [
                row["Fecha"], row["Turno"], row["Labor"],
                row["GSI"], row["RMR"],
                Paragraph(str(row["Soporte"]), estilos["Normal"]),
                Paragraph(str(row["Observaciones"]), estilos["Normal"])
            ]
            datos.append(fila)
        
        tabla = Table(datos, colWidths=[60, 50, 80, 40, 40, 120, 130])
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 1, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke)
        ]))
        
        elementos.append(tabla)
        pdf.build(elementos)
        
        messagebox.showinfo("PDF", f"Historial exportado:\n{nombre}")


class VentanaEstandar:
    """Ventana para editar estándares de sostenimiento"""
    
    def __init__(self, parent, model):
        self.model = model
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Estándar de Sostenimiento")
        self.ventana.geometry("700x400")
        
        self._crear_interfaz()
    
    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de estándar"""
        columnas = ["RMR_min", "RMR_max", "Tipo", "Soporte"]

        self.tabla = ttk.Treeview(self.ventana, columns=columnas, show="headings")

        anchos = {"RMR_min": 80, "RMR_max": 80, "Tipo": 120, "Soporte": 250}
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=anchos.get(col, 100), anchor="center")

        self.tabla.pack(pady=10, fill="both", expand=True, padx=10)

        # Cargar datos existentes
        df = self.model.obtener_estandar_sostenimiento()
        for _, row in df.iterrows():
            tipo_val = row.get("Tipo", "") if "Tipo" in df.columns else ""
            self.tabla.insert("", "end", values=(
                row["RMR_min"], row["RMR_max"], tipo_val, row["Soporte"]
            ))

        # Frame de inputs
        frame_inputs = tk.Frame(self.ventana)
        frame_inputs.pack(pady=10)

        tk.Label(frame_inputs, text="RMR min").grid(row=0, column=0, padx=5)
        self.entrada_min = tk.Entry(frame_inputs, width=8)
        self.entrada_min.grid(row=0, column=1, padx=5)

        tk.Label(frame_inputs, text="RMR max").grid(row=0, column=2, padx=5)
        self.entrada_max = tk.Entry(frame_inputs, width=8)
        self.entrada_max.grid(row=0, column=3, padx=5)

        tk.Label(frame_inputs, text="Tipo").grid(row=0, column=4, padx=5)
        self.tipo_estandar_var = tk.StringVar(value="Temporal")
        ttk.Combobox(
            frame_inputs,
            textvariable=self.tipo_estandar_var,
            values=["Temporal", "Permanente"],
            state="readonly",
            width=12
        ).grid(row=0, column=5, padx=5)

        tk.Label(frame_inputs, text="Soporte").grid(row=0, column=6, padx=5)
        self.entrada_soporte = tk.Entry(frame_inputs, width=25)
        self.entrada_soporte.grid(row=0, column=7, padx=5)

        # Frame de botones
        frame_botones = tk.Frame(self.ventana)
        frame_botones.pack(pady=10)

        tk.Button(frame_botones, text="Agregar", command=self._agregar_fila).pack(side="left", padx=5)
        tk.Button(frame_botones, text="Eliminar", command=self._eliminar_fila).pack(side="left", padx=5)
        tk.Button(frame_botones, text="Guardar estándar", command=self._guardar_estandar).pack(side="left", padx=5)
    
    def _agregar_fila(self):
        """Agrega una fila a la tabla"""
        rmr_min = self.entrada_min.get()
        rmr_max = self.entrada_max.get()
        tipo = self.tipo_estandar_var.get()
        soporte = self.entrada_soporte.get()

        if not rmr_min or not rmr_max or not soporte:
            messagebox.showwarning("Error", "Complete todos los campos")
            return

        self.tabla.insert("", "end", values=(rmr_min, rmr_max, tipo, soporte))

        self.entrada_min.delete(0, tk.END)
        self.entrada_max.delete(0, tk.END)
        self.entrada_soporte.delete(0, tk.END)
        self.tipo_estandar_var.set("Temporal")
    
    def _eliminar_fila(self):
        """Elimina la fila seleccionada"""
        seleccionado = self.tabla.selection()
        if seleccionado:
            self.tabla.delete(seleccionado)
    
    def _guardar_estandar(self):
        """Guarda los estándares"""
        datos = []
        for fila in self.tabla.get_children():
            valores = self.tabla.item(fila)["values"]
            datos.append({
                "RMR_min": valores[0],
                "RMR_max": valores[1],
                "Tipo": valores[2],
                "Soporte": valores[3]
            })

        exito, mensaje = self.model.guardar_estandar_sostenimiento(datos)
        messagebox.showinfo("Resultado", mensaje)


class VentanaLabores:
    """Ventana para gestionar el catálogo de labores"""

    def __init__(self, parent, model, callback_actualizar=None):
        self.model = model
        self.callback_actualizar = callback_actualizar
        self.ventana = tk.Toplevel(parent)
        self.ventana.title("Gestión de Labores")
        self.ventana.geometry("750x550")
        self.ventana.configure(bg=WINDOW_BG_COLOR)
        self.ventana.resizable(True, True)
        self._crear_interfaz()

    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de gestión de labores"""
        tk.Label(
            self.ventana,
            text="Gestión de Labores",
            font=("Segoe UI", 14, "bold"),
            bg=WINDOW_BG_COLOR
        ).pack(pady=10)

        # Frame para agregar nueva labor
        frame_agregar = ttk.LabelFrame(self.ventana, text="Nueva Labor", padding=10)
        frame_agregar.pack(fill="x", padx=15, pady=5)

        # Fila 0: Nombre de la labor y Tipo
        ttk.Label(frame_agregar, text="Nombre:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.nueva_labor_var = tk.StringVar()
        ttk.Entry(frame_agregar, textvariable=self.nueva_labor_var, width=30).grid(row=0, column=1, sticky="ew", padx=5, pady=3)

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
        combo_tipo.bind("<<ComboboxSelected>>", self._calcular_soporte)

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

        # Botón Agregar
        ttk.Button(
            frame_agregar,
            text="➕ Agregar Labor",
            command=self._agregar_labor
        ).grid(row=3, column=0, columnspan=4, pady=8)

        # Frame para lista de labores
        frame_lista = ttk.LabelFrame(self.ventana, text="Labores Registradas", padding=10)
        frame_lista.pack(fill="both", expand=True, padx=15, pady=5)

        columnas = ["Labor", "GSI", "RMR", "Soporte", "Tipo"]
        self.tabla_labores = ttk.Treeview(frame_lista, columns=columnas, show="headings", height=10)

        anchos = {"Labor": 180, "GSI": 60, "RMR": 60, "Soporte": 200, "Tipo": 100}
        for col in columnas:
            self.tabla_labores.heading(col, text=col)
            self.tabla_labores.column(col, anchor="center", width=anchos.get(col, 100))

        scrollbar_y = ttk.Scrollbar(frame_lista, orient="vertical", command=self.tabla_labores.yview)
        self.tabla_labores.configure(yscrollcommand=scrollbar_y.set)
        self.tabla_labores.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

        # Botones de acción
        frame_botones = ttk.Frame(self.ventana)
        frame_botones.pack(pady=10)

        ttk.Button(
            frame_botones,
            text="🗑 Eliminar Seleccionada",
            command=self._eliminar_labor
        ).pack(side="left", padx=5)

        ttk.Button(
            frame_botones,
            text="Cerrar",
            command=self._cerrar
        ).pack(side="left", padx=5)

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
                    row.get("Tipo", "")
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

        exito, mensaje = self.model.agregar_labor(nombre, gsi=gsi, rmr=rmr, soporte=soporte, tipo=tipo)
        if exito:
            self.nueva_labor_var.set("")
            self.gsi_var.set("")
            self.rmr_var.set("")
            self.soporte_var.set("")
            self.tipo_var.set("Temporal")
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

class VentanaSostenimiento(tk.Toplevel):
    """Ventana para registrar sostenimiento diario por labor y turno"""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Sostenimiento Diario")
        self.geometry("700x640")
        self.configure(bg=WINDOW_BG_COLOR)
        self.resizable(True, True)
        self._crear_interfaz()

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
        tk.Label(
            self, text="Registro de Sostenimiento Diario",
            font=("Segoe UI", 14, "bold"), bg=WINDOW_BG_COLOR
        ).pack(pady=8)

        frame = ttk.LabelFrame(self, text="Datos de Sostenimiento", padding=12)
        frame.pack(fill="x", padx=15, pady=5)

        # Fecha (no editable)
        ttk.Label(frame, text="Fecha:").grid(row=0, column=0, sticky="w", pady=3)
        ttk.Label(frame, text=obtener_fecha_actual()).grid(row=0, column=1, sticky="w", pady=3)

        # Turno
        ttk.Label(frame, text="Turno:").grid(row=1, column=0, sticky="w", pady=3)
        self.turno_var = tk.StringVar()
        combo_turno = ttk.Combobox(frame, textvariable=self.turno_var,
                                   state="readonly", values=TURNOS, width=15)
        combo_turno.grid(row=1, column=1, sticky="w", pady=3)
        self.turno_var.set(_obtener_turno_automatico())

        # Labor
        ttk.Label(frame, text="Labor:").grid(row=2, column=0, sticky="w", pady=3)
        self.labor_var = tk.StringVar()
        self.entrada_labor = ttk.Entry(frame, textvariable=self.labor_var, width=30)
        self.entrada_labor.grid(row=2, column=1, sticky="ew", pady=3)
        self.lista_labores = self.model.obtener_labores_guardadas()
        self.entrada_labor.bind("<KeyRelease>", self._filtrar_labores)
        self.entrada_labor.bind("<FocusOut>", self._ocultar_lista)

        self.listbox_labor = tk.Listbox(frame, height=4, exportselection=False)
        self.listbox_labor.grid(row=3, column=1, sticky="ew")
        self.listbox_labor.bind("<<ListboxSelect>>", self._seleccionar_labor)
        self.listbox_labor.grid_remove()

        # Campos numéricos dinámicos desde config
        self._activos = self._cargar_activos()
        self._vars_sost = {}  # columna -> (var, tipo)
        for i, sost in enumerate(self._activos):
            display = sost.get("display", sost.get("columna", ""))
            columna = sost.get("columna", "")
            tipo = sost.get("tipo", "int")
            row_idx = 4 + i
            ttk.Label(frame, text=f"{display}:").grid(row=row_idx, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            self._vars_sost[columna] = (var, tipo)
            ttk.Entry(frame, textvariable=var, width=12).grid(row=row_idx, column=1, sticky="w", pady=2)

        obs_row = 4 + len(self._activos)
        # Observaciones
        ttk.Label(frame, text="Observaciones:").grid(row=obs_row, column=0, sticky="nw", pady=3)
        self.obs_text = tk.Text(frame, height=3, width=35, font=("Segoe UI", 10),
                                relief="flat", borderwidth=1,
                                highlightthickness=1, highlightbackground="#cccccc",
                                highlightcolor="#4a90d9", wrap="word")
        self.obs_text.grid(row=obs_row, column=1, sticky="ew", pady=3)

        frame.columnconfigure(1, weight=1)

        # Botones
        frame_botones = ttk.Frame(self)
        frame_botones.pack(pady=10)

        ttk.Button(frame_botones, text="💾 Guardar Sostenimiento",
                   command=self._guardar).pack(side="left", padx=8)
        ttk.Button(frame_botones, text="📋 Ver Historial Sostenimiento",
                   command=self._abrir_historial).pack(side="left", padx=8)
        ttk.Button(frame_botones, text="Cerrar", command=self.destroy).pack(side="left", padx=8)

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
        self.geometry("1050x520")
        self._indices_originales = []
        self.COLUMNAS = self._obtener_columnas()
        self._crear_interfaz()

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
        frame_filtros = ttk.Frame(self)
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

        ttk.Button(frame_filtros, text="🔍 Filtrar", command=self._cargar).grid(row=0, column=6, padx=8)

        # Tabla
        self.tabla = ttk.Treeview(self, columns=self.COLUMNAS, show="headings", height=15)
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

        frame_btn = ttk.Frame(self)
        frame_btn.pack(pady=8)
        ttk.Button(frame_btn, text="✏ Editar", command=self._editar).pack(side="left", padx=5)
        ttk.Button(frame_btn, text="🗑 Eliminar", command=self._eliminar).pack(side="left", padx=5)
        ttk.Button(frame_btn, text="📊 Exportar a Excel", command=self._exportar).pack(side="left", padx=5)
        ttk.Button(frame_btn, text="Cerrar", command=self.destroy).pack(side="left", padx=5)

        self._cargar()

    def _cargar(self):
        labor = self.labor_filtro.get().strip() or None
        df = self.model.obtener_sostenimiento(labor=labor)
        self._df = df.copy()
        self._indices_originales = list(df.index)

        for item in self.tabla.get_children():
            self.tabla.delete(item)
        for _, row in df.iterrows():
            self.tabla.insert("", "end", values=[row.get(c, "") for c in self.COLUMNAS])

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
        self.geometry("1000x700")
        self._crear_interfaz()

    def _crear_interfaz(self):
        # Filtros superiores
        frame_filtros = ttk.Frame(self)
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

        ttk.Button(frame_filtros, text="🔄 Actualizar",
                   command=self._actualizar).grid(row=0, column=8, padx=10)

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
            import matplotlib
            import pandas as pd
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
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

        fig = Figure(figsize=(12, 8), dpi=90)
        axes = [fig.add_subplot(2, 2, i + 1) for i in range(4)]

        COLS_NUM = list(dict.fromkeys(
            [s["columna"] for s in _cargar_config().get("sostenimientos_activos", [])
             if isinstance(s, dict) and "columna" in s]
            + ["Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
               "Mesh_Strap", "Cable_Bolting", "Marco_Acero"]
        ))

        # Gráfico 1: Barras agrupadas – totales por labor
        ax1 = axes[0]
        ax1.set_title("Totales por Labor")
        if df_totales is not None and not df_totales.empty:
            cols_presentes = [c for c in COLS_NUM if c in df_totales.columns]
            df_plot = df_totales.set_index("Labor")[cols_presentes]
            df_plot.plot(kind="bar", ax=ax1, legend=True)
            ax1.set_xlabel("Labor")
            ax1.set_ylabel("Cantidad")
            ax1.tick_params(axis="x", rotation=30)
        else:
            ax1.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax1.transAxes)

        # Gráfico 2: Línea temporal – Shotcrete diario
        ax2 = axes[1]
        ax2.set_title("Evolución Diaria de Shotcrete (m³)")
        if df_sost is not None and not df_sost.empty and "Shotcrete_m3" in df_sost.columns:
            try:
                df_sost["Shotcrete_m3"] = pd.to_numeric(df_sost["Shotcrete_m3"], errors="coerce").fillna(0)
                diario = df_sost.groupby("Fecha_dt")["Shotcrete_m3"].sum().sort_index()
                ax2.plot(diario.index, diario.values, marker="o")
                ax2.set_xlabel("Fecha")
                ax2.set_ylabel("m³")
                ax2.tick_params(axis="x", rotation=30)
            except Exception:
                ax2.text(0.5, 0.5, "Sin datos para el período seleccionado",
                         ha="center", va="center", transform=ax2.transAxes)
        else:
            ax2.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax2.transAxes)

        # Gráfico 3: Pie – distribución de pernos por labor
        ax3 = axes[2]
        ax3.set_title("Distribución de Pernos por Labor")
        if df_totales is not None and not df_totales.empty:
            try:
                pernos_cols = [c for c in ["Pernos_Helicoidales", "Splitsets"] if c in df_totales.columns]
                if pernos_cols:
                    df_totales["Total_Pernos"] = df_totales[pernos_cols].sum(axis=1)
                    positivos = df_totales[df_totales["Total_Pernos"] > 0]
                    if not positivos.empty:
                        ax3.pie(positivos["Total_Pernos"], labels=positivos["Labor"], autopct="%1.1f%%")
                    else:
                        ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                                 ha="center", va="center", transform=ax3.transAxes)
                else:
                    ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                             ha="center", va="center", transform=ax3.transAxes)
            except Exception:
                ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                         ha="center", va="center", transform=ax3.transAxes)
        else:
            ax3.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax3.transAxes)

        # Gráfico 4: Barras – RMR promedio por labor
        ax4 = axes[3]
        ax4.set_title("RMR Promedio por Labor")
        if df_bit is not None and not df_bit.empty and "RMR" in df_bit.columns:
            try:
                df_bit["RMR_num"] = pd.to_numeric(df_bit["RMR"], errors="coerce")
                rmr_prom = df_bit.dropna(subset=["RMR_num"]).groupby("Labor")["RMR_num"].mean()
                if not rmr_prom.empty:
                    rmr_prom.plot(kind="bar", ax=ax4, color="steelblue")
                    ax4.set_xlabel("Labor")
                    ax4.set_ylabel("RMR Promedio")
                    ax4.tick_params(axis="x", rotation=30)
                else:
                    ax4.text(0.5, 0.5, "Sin datos para el período seleccionado",
                             ha="center", va="center", transform=ax4.transAxes)
            except Exception:
                ax4.text(0.5, 0.5, "Sin datos para el período seleccionado",
                         ha="center", va="center", transform=ax4.transAxes)
        else:
            ax4.text(0.5, 0.5, "Sin datos para el período seleccionado",
                     ha="center", va="center", transform=ax4.transAxes)

        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.frame_graficos)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


class VentanaConfiguracion(tk.Toplevel):
    """Panel de configuración de la aplicación"""

    def __init__(self, parent, callback_cerrar=None):
        super().__init__(parent)
        self.callback_cerrar = callback_cerrar
        self.title("Configuración")
        self.geometry("400x500")
        self.resizable(False, False)
        self.grab_set()
        self._guardado = False
        self._crear_interfaz()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

    def _crear_interfaz(self):
        from utils.config_manager import cargar_config
        self._config = cargar_config()

        tk.Label(self, text="Configuración", font=("Segoe UI", 14, "bold")).pack(pady=10)

        # Turnos
        frame_turnos = ttk.LabelFrame(self, text="Turnos disponibles", padding=10)
        frame_turnos.pack(fill="x", padx=15, pady=5)

        self.listbox_turnos = tk.Listbox(frame_turnos, height=4)
        for t in self._config.get("turnos", []):
            self.listbox_turnos.insert(tk.END, t)
        self.listbox_turnos.pack(fill="x")

        frame_turno_btns = ttk.Frame(frame_turnos)
        frame_turno_btns.pack(fill="x", pady=5)
        ttk.Button(frame_turno_btns, text="➕ Agregar turno",
                   command=self._agregar_turno).pack(side="left", padx=5)
        ttk.Button(frame_turno_btns, text="🗑 Eliminar seleccionado",
                   command=self._eliminar_turno).pack(side="left", padx=5)

        # Backup automático
        frame_backup = ttk.LabelFrame(self, text="Respaldo Automático", padding=10)
        frame_backup.pack(fill="x", padx=15, pady=5)
        self.backup_var = tk.BooleanVar(value=self._config.get("backup_automatico", True))
        ttk.Checkbutton(frame_backup, text="Activar respaldo automático al guardar",
                        variable=self.backup_var).pack(anchor="w")

        # Color de fondo
        frame_color = ttk.LabelFrame(self, text="Color de fondo (hex)", padding=10)
        frame_color.pack(fill="x", padx=15, pady=5)
        self.color_var = tk.StringVar(value=self._config.get("theme_color", WINDOW_BG_COLOR))
        ttk.Entry(frame_color, textvariable=self.color_var, width=15).pack(side="left", padx=5)
        ttk.Button(frame_color, text="Previsualizar",
                   command=self._previsualizar_color).pack(side="left", padx=5)

        # Botones finales
        frame_btns = ttk.Frame(self)
        frame_btns.pack(pady=15)
        ttk.Button(frame_btns, text="💾 Guardar configuración",
                   command=self._guardar).pack(side="left", padx=10)
        ttk.Button(frame_btns, text="Cancelar",
                   command=self._cancelar).pack(side="left", padx=10)

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
        self._config["backup_automatico"] = self.backup_var.get()
        self._config["theme_color"] = self.color_var.get()
        if guardar_config(self._config):
            self._guardado = True
            messagebox.showinfo("Configuración", "Configuración guardada correctamente.", parent=self)
            self.destroy()
            if self.callback_cerrar:
                self.callback_cerrar()
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuración.", parent=self)

    def _crear_interfaz(self):
        from utils.config_manager import cargar_config
        self._config = cargar_config()

        tk.Label(self, text="Configuración", font=("Segoe UI", 14, "bold")).pack(pady=10)

        # Turnos
        frame_turnos = ttk.LabelFrame(self, text="Turnos disponibles", padding=10)
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

        # Backup automático
        frame_backup = ttk.LabelFrame(self, text="Respaldo Automático", padding=8)
        frame_backup.pack(fill="x", padx=15, pady=4)
        self.backup_var = tk.BooleanVar(value=self._config.get("backup_automatico", True))
        ttk.Checkbutton(frame_backup, text="Activar respaldo automático al guardar",
                        variable=self.backup_var).pack(anchor="w")

        # Color de fondo
        frame_color = ttk.LabelFrame(self, text="Color de fondo (hex)", padding=8)
        frame_color.pack(fill="x", padx=15, pady=4)
        self.color_var = tk.StringVar(value=self._config.get("theme_color", WINDOW_BG_COLOR))
        ttk.Entry(frame_color, textvariable=self.color_var, width=15).pack(side="left", padx=5)
        ttk.Button(frame_color, text="Previsualizar",
                   command=self._previsualizar_color).pack(side="left", padx=5)

        # Contraseña de edición
        frame_pwd = ttk.LabelFrame(self, text="Contraseña para editar registros >24h", padding=8)
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

        # Botones finales
        frame_btns = ttk.Frame(self)
        frame_btns.pack(pady=12)
        ttk.Button(frame_btns, text="💾 Guardar configuración",
                   command=self._guardar).pack(side="left", padx=10)
        ttk.Button(frame_btns, text="Cancelar",
                   command=self._cancelar).pack(side="left", padx=10)

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
        self._config["backup_automatico"] = self.backup_var.get()
        self._config["theme_color"] = self.color_var.get()
        self._config["password_edicion"] = self.pwd_var.get()
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
    """Aplica o desactiva el modo oscuro en toda la interfaz."""
    if activar:
        bg = "#1e1e2e"
        fg = "#cdd6f4"
        btn_bg = "#313244"
        style_name = "Oscuro.TFrame"
    else:
        bg = WINDOW_BG_COLOR
        fg = "#222222"
        btn_bg = "#e0e0e0"
        style_name = "Claro.TFrame"

    style = ttk.Style()
    try:
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=btn_bg, foreground=fg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TCombobox", fieldbackground=bg, foreground=fg)
        style.configure("TEntry", fieldbackground=bg, foreground=fg)
        style.configure("Treeview", background=bg, foreground=fg, fieldbackground=bg)
        style.configure("Treeview.Heading", background=btn_bg, foreground=fg)
        style.map("TButton", background=[("active", btn_bg)])
    except Exception:
        pass

    try:
        root.configure(bg=bg)
        _actualizar_widgets_colores(root, bg, fg)
    except Exception:
        pass


def _actualizar_widgets_colores(widget, bg, fg):
    """Recorre widgets de tkinter (no ttk) y actualiza colores."""
    try:
        widget_class = widget.winfo_class()
        if widget_class in ("Label", "Frame", "Listbox", "Text", "Canvas"):
            try:
                widget.configure(bg=bg)
            except Exception:
                pass
            try:
                widget.configure(fg=fg)
            except Exception:
                pass
        for child in widget.winfo_children():
            _actualizar_widgets_colores(child, bg, fg)
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

class VentanaSostenimientos(tk.Toplevel):
    """
    Ventana para gestionar la lista de sostenimientos activos.
    Muestra checkboxes de la lista predeterminada + campo para añadir custom.
    Los activos se guardan en config.json como 'sostenimientos_activos'.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Gestionar Sostenimientos")
        self.geometry("480x560")
        self.resizable(False, False)
        self.grab_set()
        self._crear_interfaz()

    def _crear_interfaz(self):
        from utils.config_manager import cargar_config
        self._config = cargar_config()

        catalogo = self._config.get("sostenimientos_catalogo", [])
        activos_columnas = {s["columna"] for s in self._config.get("sostenimientos_activos", [])
                            if isinstance(s, dict)}

        tk.Label(self, text="Gestionar Sostenimientos",
                 font=("Segoe UI", 13, "bold")).pack(pady=10)

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
        frame_btns = ttk.Frame(self)
        frame_btns.pack(pady=10)
        ttk.Button(frame_btns, text="💾 Guardar",
                   command=self._guardar).pack(side="left", padx=10)
        ttk.Button(frame_btns, text="Cancelar",
                   command=self.destroy).pack(side="left", padx=10)

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
            messagebox.showinfo("Guardado", "Sostenimientos guardados correctamente.\n"
                                "Reinicie la ventana de Sostenimiento Diario para ver los cambios.",
                                parent=self)
            self.destroy()
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuración.", parent=self)


class VentanaReportePeriodo(tk.Toplevel):
    """Ventana para generar un reporte PDF consolidado por período."""

    def __init__(self, parent, model):
        super().__init__(parent)
        self.model = model
        self.title("Reporte de Período")
        self.geometry("400x200")
        self.resizable(False, False)
        self.grab_set()
        self._crear_interfaz()

    def _crear_interfaz(self):
        tk.Label(self, text="Reporte de Período",
                 font=("Segoe UI", 13, "bold")).pack(pady=10)

        frame_f = ttk.Frame(self)
        frame_f.pack(pady=5)

        ttk.Label(frame_f, text="Desde:").grid(row=0, column=0, padx=8)
        self.fi = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        self.fi.grid(row=0, column=1, padx=8)

        ttk.Label(frame_f, text="Hasta:").grid(row=0, column=2, padx=8)
        self.ff = DateEntry(frame_f, date_pattern="dd/mm/yyyy", width=12)
        self.ff.grid(row=0, column=3, padx=8)

        frame_btn = ttk.Frame(self)
        frame_btn.pack(pady=15)
        ttk.Button(frame_btn, text="🔍 Vista Previa y Generar",
                   command=self._previsualizar).pack(side="left", padx=8)
        ttk.Button(frame_btn, text="Cerrar", command=self.destroy).pack(side="left", padx=8)

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
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

        fi_arch = fi_str.replace("/", "-")
        ff_arch = ff_str.replace("/", "-")
        nombre = f"reporte_periodo_{fi_arch}_{ff_arch}.pdf"

        try:
            pdf = SimpleDocTemplate(nombre, pagesize=letter)
            estilos = getSampleStyleSheet()
            elementos = []

            elementos.append(Paragraph("REPORTE DE PERÍODO — GEOMECÁNICA", estilos["Title"]))
            elementos.append(Spacer(1, 6))
            elementos.append(Paragraph(f"Período: {fi_str} al {ff_str}", estilos["Normal"]))
            elementos.append(Paragraph(f"Total de registros: {len(df)}", estilos["Normal"]))
            elementos.append(Spacer(1, 12))

            # Tabla principal
            datos_tabla = [df.columns.tolist()]
            for _, row in df.iterrows():
                fila = []
                for col in df.columns:
                    val = str(row[col]) if str(row[col]) != "nan" else ""
                    if col in ("Soporte", "Observaciones"):
                        fila.append(Paragraph(val, estilos["Normal"]))
                    else:
                        fila.append(val)
                datos_tabla.append(fila)

            anchos = [60, 50, 80, 40, 40, 120, 130]
            tabla = Table(datos_tabla, colWidths=anchos[:len(df.columns)])
            tabla.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]))
            elementos.append(tabla)
            elementos.append(Spacer(1, 16))

            # Estadísticas de sostenimiento
            elementos.append(Paragraph("Estadísticas del Período", estilos["Heading2"]))
            elementos.append(Spacer(1, 6))

            try:
                import pandas as pd
                # Distribución por turno
                if "Turno" in df.columns:
                    turnos = df["Turno"].value_counts()
                    elementos.append(Paragraph("Distribución por turno:", estilos["Normal"]))
                    for t, n in turnos.items():
                        elementos.append(Paragraph(f"  • {t}: {n} registros", estilos["Normal"]))
                    elementos.append(Spacer(1, 6))

                # Labor con más registros
                if "Labor" in df.columns:
                    top = df["Labor"].value_counts().idxmax()
                    elementos.append(Paragraph(f"Labor con más registros: {top}", estilos["Normal"]))
                    elementos.append(Spacer(1, 6))

                # Datos de sostenimiento del período
                df_sost = self.model.buscar_registros("", "", "")
                if not df_sost.empty:
                    # Obtener sostenimiento en el mismo período
                    df_s2 = self.model.obtener_totales_sostenimiento(
                        fecha_inicio=fi_str, fecha_fin=ff_str
                    )
                    if not df_s2.empty:
                        elementos.append(Paragraph("Totales de Sostenimiento por Labor:", estilos["Heading3"]))
                        cols_s = list(df_s2.columns)
                        datos_s = [cols_s]
                        for _, row in df_s2.iterrows():
                            datos_s.append([str(row[c]) for c in cols_s])
                        tabla_s = Table(datos_s)
                        tabla_s.setStyle(TableStyle([
                            ("BACKGROUND", (0, 0), (-1, 0), colors.steelblue),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ]))
                        elementos.append(tabla_s)
            except Exception:
                pass

            pdf.build(elementos)
            messagebox.showinfo("PDF generado",
                                f"Reporte guardado como:\n{nombre}", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el PDF:\n{e}", parent=self)
