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
    validar_campos_obligatorios
)


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
        
        # Frame de botones reorganizado
        frame_botones = ttk.Frame(self.root)
        frame_botones.pack(pady=(5, 10))

        # Fila 1: Botón principal de guardar
        ttk.Button(
            frame_botones,
            text="💾  Guardar Registro",
            command=self._guardar_datos,
            width=25
        ).grid(row=0, column=0, columnspan=4, pady=(0, 8), padx=5)

        # Fila 2: Botones secundarios
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
        ventana = VentanaHistorial(self.root, self.model)
    
    def _abrir_estandar(self):
        """Abre ventana de estándar de sostenimiento"""
        ventana = VentanaEstandar(self.root, self.model)
    
    def _generar_reporte(self):
        """Genera reporte PDF del día"""
        df = self.model.obtener_bitacora()
        fecha_hoy = obtener_fecha_actual()
        
        df_hoy = df[df["Fecha"] == fecha_hoy]
        
        if df_hoy.empty:
            messagebox.showinfo("Info", "No hay registros hoy")
            return
        
        self._generar_pdf_diario(df_hoy, fecha_hoy)
    
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
        self.ventana.geometry("900x500")
        self.ventana.configure(bg=WINDOW_BG_COLOR)
        
        self._crear_interfaz()
    
    def _crear_interfaz(self):
        """Crea la interfaz de la ventana de historial"""
        # Frame de búsqueda
        frame_busqueda = ttk.Frame(self.ventana)
        frame_busqueda.pack(pady=10, padx=10, fill="x")
        
        for i in range(6):
            frame_busqueda.columnconfigure(i, weight=1)
        
        # Variables
        self.buscar_var = tk.StringVar()
        self.fecha_inicio_var = tk.StringVar()
        self.fecha_fin_var = tk.StringVar()
        
        # Búsqueda
        ttk.Label(frame_busqueda, text="Buscar Labor:").grid(row=0, column=0, padx=5, pady=5)
        entrada_buscar = ttk.Entry(frame_busqueda, textvariable=self.buscar_var, width=25)
        entrada_buscar.grid(row=0, column=1, padx=5, pady=5)
        entrada_buscar.bind("<KeyRelease>", lambda e: self._buscar_labor())
        
        ttk.Label(frame_busqueda, text="Desde:").grid(row=0, column=2, padx=5, pady=5)
        entrada_inicio = DateEntry(
            frame_busqueda,
            textvariable=self.fecha_inicio_var,
            date_pattern="dd/mm/yyyy",
            width=12
        )
        entrada_inicio.grid(row=0, column=3, padx=5, pady=5)
        entrada_inicio.bind("<<DateEntrySelected>>", lambda e: self._buscar_labor())
        
        ttk.Label(frame_busqueda, text="Hasta:").grid(row=0, column=4, padx=5, pady=5)
        entrada_fin = DateEntry(
            frame_busqueda,
            textvariable=self.fecha_fin_var,
            date_pattern="dd/mm/yyyy",
            width=12
        )
        entrada_fin.grid(row=0, column=5, padx=5, pady=5)
        entrada_fin.bind("<<DateEntrySelected>>", lambda e: self._buscar_labor())
        
        # Tabla
        columnas = ["Fecha", "Turno", "Labor", "GSI", "RMR", "Soporte", "Observaciones"]
        self.tabla = ttk.Treeview(
            self.ventana,
            columns=columnas,
            show="headings",
            height=18
        )
        
        for col in columnas:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, anchor="center")
        
        self.tabla.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(self.tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
        # Botones
        frame_botones = ttk.Frame(self.ventana)
        frame_botones.pack(pady=10)
        
        ttk.Button(
            frame_botones,
            text="Exportar PDF",
            command=self._exportar_pdf
        ).pack(side="left", padx=10)
        
        ttk.Button(
            frame_botones,
            text="Cerrar",
            command=self.ventana.destroy
        ).pack(side="left", padx=10)
        
        self._buscar_labor()
    
    def _buscar_labor(self):
        """Busca registros según filtros"""
        labor = self.buscar_var.get()
        fecha_inicio = self.fecha_inicio_var.get()
        fecha_fin = self.fecha_fin_var.get()
        
        df = self.model.buscar_registros(labor, fecha_inicio, fecha_fin)
        
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        
        for _, row in df.iterrows():
            self.tabla.insert("", "end", values=list(row))
    
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