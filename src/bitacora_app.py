import tkinter as tk
from tkinter import messagebox, ttk
import pandas as pd
import os
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from tkcalendar import DateEntry

archivo = "bitacora_geomecanica.xlsx"

# ---------------------------------------------------------
# CREAR ARCHIVO SI NO EXISTE
# ---------------------------------------------------------

def inicializar_excel():

    if not os.path.exists(archivo):

        bitacora = pd.DataFrame(columns=[
            "Fecha","Turno","Labor","GSI","RMR","Soporte","Observaciones"
        ])

        estandar = pd.DataFrame(columns=[
            "RMR_min","RMR_max","Soporte"
        ])

        with pd.ExcelWriter(archivo) as writer:
            bitacora.to_excel(writer, sheet_name="Bitacora", index=False)
            estandar.to_excel(writer, sheet_name="Estandar_Sostenimiento", index=False)

# ---------------------------------------------------------
# GUARDAR REGISTRO
# ---------------------------------------------------------

def guardar_datos():

    fecha = datetime.now().strftime("%d/%m/%Y")
    turno = turno_var.get()
    labor = labor_var.get()
    gsi = entrada_gsi.get()
    rmr = entrada_rmr.get()
    soporte = entrada_soporte.get()
    observaciones = entrada_obs.get("1.0", tk.END).strip()

    if labor == "":
        messagebox.showwarning("Error", "Ingrese o seleccione una labor")
        return

    datos = {
        "Fecha":[fecha],
        "Turno":[turno],
        "Labor":[labor],
        "GSI":[gsi],
        "RMR":[rmr],
        "Soporte":[soporte],
        "Observaciones":[observaciones]
    }

    df_nuevo = pd.DataFrame(datos)

    df = pd.read_excel(archivo, sheet_name="Bitacora")

    df = pd.concat([df, df_nuevo], ignore_index=True)

    with pd.ExcelWriter(archivo, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name="Bitacora", index=False)

    messagebox.showinfo("Guardado", "Registro guardado")

    limpiar_campos()
    actualizar_labores()

# ---------------------------------------------------------
# LIMPIAR CAMPOS
# ---------------------------------------------------------

def limpiar_campos():

    entrada_gsi.delete(0, tk.END)
    entrada_rmr.delete(0, tk.END)
    entrada_soporte.delete(0, tk.END)
    entrada_obs.delete("1.0", tk.END)

# ---------------------------------------------------------
# ACTUALIZAR LABORES
# ---------------------------------------------------------

def actualizar_labores():

    global lista_labores

    df = pd.read_excel(archivo, sheet_name="Bitacora")

    lista_labores = sorted(df["Labor"].dropna().unique())


# -------------------
#filtrar labores

def filtrar_labores(event):

    texto = labor_var.get().lower()

    # limpiar lista
    lista_filtrada.delete(0, tk.END)

    # si no hay texto no mostrar nada
    if texto == "":
        return

    resultados = []

    for labor in lista_labores:

        if texto in labor.lower():
            resultados.append(labor)

    # mostrar máximo 5 resultados
    resultados = resultados[:5]

    for labor in resultados:
        lista_filtrada.insert(tk.END, labor)

#Seleccionar labor
#------------------

def seleccionar_labor(event):

    seleccion = lista_filtrada.curselection()

    if not seleccion:
        return

    labor = lista_filtrada.get(seleccion[0])

    labor_var.set(labor)

    lista_filtrada.delete(0, tk.END)

    cargar_ultimo_registro(labor)

# ---------------------------------------------------------
# HISTORIAL
# ---------------------------------------------------------

def ver_historial():

    ventana_historial = tk.Toplevel()
    ventana_historial.title("Historial de Labores")
    ventana_historial.geometry("900x500")
    ventana_historial.configure(bg="#f2f4f7")

    # -------------------------------
    # FRAME BUSQUEDA
    # -------------------------------

    frame_busqueda = ttk.Frame(ventana_historial)
    frame_busqueda.pack(pady=10, padx=10, fill="x")

    for i in range(6):
        frame_busqueda.columnconfigure(i, weight=1)

    # Variables
    buscar_var = tk.StringVar()
    fecha_inicio_var = tk.StringVar()
    fecha_fin_var = tk.StringVar()

    # Fila 0
    ttk.Label(frame_busqueda, text="Buscar Labor:").grid(row=0, column=0, padx=5, pady=5)

    entrada_buscar = ttk.Entry(frame_busqueda, textvariable=buscar_var, width=25)
    entrada_buscar.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(frame_busqueda, text="Desde:").grid(row=0, column=2, padx=5, pady=5)

    entrada_inicio = DateEntry(
    frame_busqueda,
    textvariable=fecha_inicio_var,
    date_pattern="dd/mm/yyyy",
    width=12
    )
    entrada_inicio.grid(row=0, column=3, padx=5, pady=5)

    entrada_inicio.bind("<<DateEntrySelected>>", lambda e: buscar_labor())

    ttk.Label(frame_busqueda, text="Hasta:").grid(row=0, column=4, padx=5, pady=5)

    entrada_fin = DateEntry(
    frame_busqueda,
    textvariable=fecha_fin_var,
    date_pattern="dd/mm/yyyy",
    width=12
    )
    entrada_fin.grid(row=0, column=5, padx=5, pady=5)

    entrada_fin.bind("<<DateEntrySelected>>", lambda e: buscar_labor())

    # -------------------------------
    # TABLA HISTORIAL
    # -------------------------------

    columnas = ["Fecha","Turno","Labor","GSI","RMR","Soporte","Observaciones"]

    tabla = ttk.Treeview(
        ventana_historial,
        columns=columnas,
        show="headings",
        height=18
    )

    for col in columnas:
        tabla.heading(col, text=col)
        tabla.column(col, anchor="center")

    tabla.pack(fill="both", expand=True, padx=10, pady=10)

    # Scrollbar
    scrollbar = ttk.Scrollbar(tabla, orient="vertical", command=tabla.yview)
    tabla.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # -------------------------------
    # FUNCION BUSCAR
    # -------------------------------

    def buscar_labor():

        labor = buscar_var.get()
        fecha_inicio = fecha_inicio_var.get()
        fecha_fin = fecha_fin_var.get()

        df = pd.read_excel(archivo, sheet_name="Bitacora")

        df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")

        if labor != "":
            df = df[df["Labor"].str.contains(labor, case=False, na=False)]

        if fecha_inicio != "" and fecha_fin != "":

            inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
            fin = datetime.strptime(fecha_fin, "%d/%m/%Y")

            df = df[(df["Fecha"] >= inicio) & (df["Fecha"] <= fin)]

        df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")

        for fila in tabla.get_children():
            tabla.delete(fila)

        for _, row in df.iterrows():
            tabla.insert("", "end", values=list(row))

    # actualizar en tiempo real
    entrada_buscar.bind("<KeyRelease>", lambda e: buscar_labor())

    # -------------------------------
    # BOTONES
    # -------------------------------

    frame_botones = ttk.Frame(ventana_historial)
    frame_botones.pack(pady=10)

    ttk.Button(
        frame_botones,
        text="Exportar PDF",
        command=lambda: exportar_historial_pdf(
            buscar_var.get(),
            fecha_inicio_var.get(),
            fecha_fin_var.get()
        )
    ).pack(side="left", padx=10)

    ttk.Button(
        frame_botones,
        text="Cerrar",
        command=ventana_historial.destroy
    ).pack(side="left", padx=10)

    buscar_labor()

# ---------------------------------------------------------
# RECOMENDAR SOPORTE SEGÚN RMR
# ---------------------------------------------------------

def recomendar_soporte(rmr):

    df = pd.read_excel(archivo, sheet_name="Estandar_Sostenimiento")

    for i in range(len(df)):

        rmr_min = int(df.loc[i,"RMR_min"])
        rmr_max = int(df.loc[i,"RMR_max"])

        if rmr_min <= rmr <= rmr_max:

            return df.loc[i,"Soporte"]

    return ""

# ---------------------------------------------------------
# CALCULAR SOPORTE AUTOMÁTICO
# ---------------------------------------------------------

def calcular_soporte(event):

    try:

        rmr = int(entrada_rmr.get())

        soporte = recomendar_soporte(rmr)

        entrada_soporte.delete(0, tk.END)
        entrada_soporte.insert(0, soporte)

    except:
        pass

# ---------------------------------------------------------
# EDITAR ESTÁNDAR DE SOSTENIMIENTO
# ---------------------------------------------------------

def editar_estandar():

    ventana_estandar = tk.Toplevel()
    ventana_estandar.title("Estándar de Sostenimiento")
    ventana_estandar.geometry("550x350")

    columnas = ["RMR_min", "RMR_max", "Soporte"]

    tabla = ttk.Treeview(ventana_estandar, columns=columnas, show="headings")

    for col in columnas:
        tabla.heading(col, text=col)
        tabla.column(col, width=150)

    tabla.pack(pady=10)

    # Cargar datos existentes
    df = pd.read_excel(archivo, sheet_name="Estandar_Sostenimiento")

    for _, row in df.iterrows():
        tabla.insert("", "end", values=list(row))

    # --------------------------------------------------
    # CAMPOS PARA INGRESAR DATOS
    # --------------------------------------------------

    frame_inputs = tk.Frame(ventana_estandar)
    frame_inputs.pack(pady=10)

    tk.Label(frame_inputs, text="RMR min").grid(row=0, column=0)
    entrada_min = tk.Entry(frame_inputs, width=10)
    entrada_min.grid(row=0, column=1)

    tk.Label(frame_inputs, text="RMR max").grid(row=0, column=2)
    entrada_max = tk.Entry(frame_inputs, width=10)
    entrada_max.grid(row=0, column=3)

    tk.Label(frame_inputs, text="Soporte").grid(row=0, column=4)
    entrada_soporte = tk.Entry(frame_inputs, width=25)
    entrada_soporte.grid(row=0, column=5)

    # --------------------------------------------------

    def agregar_fila():

        rmr_min = entrada_min.get()
        rmr_max = entrada_max.get()
        soporte = entrada_soporte.get()

        if rmr_min == "" or rmr_max == "" or soporte == "":
            messagebox.showwarning("Error","Complete todos los campos")
            return

        tabla.insert("", "end", values=(rmr_min, rmr_max, soporte))

        entrada_min.delete(0, tk.END)
        entrada_max.delete(0, tk.END)
        entrada_soporte.delete(0, tk.END)

    def eliminar_fila():

        seleccionado = tabla.selection()

        if seleccionado:
            tabla.delete(seleccionado)

    def guardar_estandar():

        datos = []

        for fila in tabla.get_children():

            valores = tabla.item(fila)["values"]

            datos.append(valores)

        df_nuevo = pd.DataFrame(datos, columns=columnas)

        with pd.ExcelWriter(archivo, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
            df_nuevo.to_excel(writer, sheet_name="Estandar_Sostenimiento", index=False)

        messagebox.showinfo("Guardado","Estándar guardado correctamente")

    # --------------------------------------------------

    frame_botones = tk.Frame(ventana_estandar)
    frame_botones.pack(pady=10)

    tk.Button(frame_botones, text="Agregar", command=agregar_fila).pack(side="left", padx=5)
    tk.Button(frame_botones, text="Eliminar", command=eliminar_fila).pack(side="left", padx=5)
    tk.Button(frame_botones, text="Guardar estándar", command=guardar_estandar).pack(side="left", padx=5)

# ---------------------------------------------------------
# REPORTE PDF
# ---------------------------------------------------------

def generar_reporte():

    df = pd.read_excel(archivo, sheet_name="Bitacora")

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    fecha_archivo = datetime.now().strftime("%d-%m-%Y")

    df_hoy = df[df["Fecha"] == fecha_hoy]

    if df_hoy.empty:
        messagebox.showinfo("Info", "No hay registros hoy")
        return

    pdf = SimpleDocTemplate(
        f"reporte_geomecanica_{fecha_archivo}.pdf",
        pagesize=letter
    )

    estilos = getSampleStyleSheet()

    elementos = []

    titulo = Paragraph("REPORTE DIARIO GEOMECÁNICA", estilos['Title'])
    elementos.append(titulo)

    elementos.append(Spacer(1, 10))

    # ------------------------------------------------
    # TABLA CON LOS REGISTROS DEL DÍA
    # ------------------------------------------------

    datos = [df_hoy.columns.tolist()]

    for _, row in df_hoy.iterrows():

        fila = [
            row["Fecha"],
            row["Turno"],
            row["Labor"],
            row["GSI"],
            row["RMR"],
            Paragraph(str(row["Soporte"]), estilos["Normal"]),
            Paragraph(str(row["Observaciones"]), estilos["Normal"])
        ]

        datos.append(fila)

    tabla = Table(datos, colWidths=[60,50,80,40,40,120,130])

    tabla.setStyle(TableStyle([

        ("BACKGROUND", (0,0), (-1,0), colors.darkblue),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),

        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),

        ("FONTNAME", (0,0),(-1,0),"Helvetica-Bold"),

        ("BOTTOMPADDING",(0,0),(-1,0),10),

        ("BACKGROUND",(0,1),(-1,-1),colors.whitesmoke),

        ("GRID",(0,0),(-1,-1),1,colors.grey)

    ]))

    elementos.append(tabla)

    elementos.append(Spacer(1, 40))


    # ------------------------------------------------
    # FIRMAS
    # ------------------------------------------------

    firma_tabla = Table([
        ["_______________________", "_______________________"],
        ["Geomecánica", "Supervisor"]
    ])

    firma_tabla.setStyle(TableStyle([
        ("ALIGN",(0,0),(-1,-1),"CENTER")
    ]))

    elementos.append(firma_tabla)


    # ------------------------------------------------
    # CREAR PDF
    # ------------------------------------------------

    pdf.build(elementos)

    messagebox.showinfo("PDF", "Reporte diario generado")

    subtitulo = Paragraph("Proyecto Minero El Roble", estilos['Heading2'])
    elementos.append(subtitulo)

    fecha_texto = Paragraph(f"Fecha: {fecha_hoy}", estilos['Normal'])
    elementos.append(fecha_texto)

    elementos.append(Spacer(1, 20))

def exportar_historial_pdf(labor, fecha_inicio=None, fecha_fin=None):

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    df = pd.read_excel(archivo, sheet_name="Bitacora")

    # convertir fechas a formato datetime
    df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")

    # filtrar labor
    if labor != "":
        df = df[df["Labor"].str.contains(labor, case=False, na=False)]

    # filtrar fechas
    if fecha_inicio and fecha_fin:

        inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
        fin = datetime.strptime(fecha_fin, "%d/%m/%Y")

        df = df[(df["Fecha"] >= inicio) & (df["Fecha"] <= fin)]

    if df.empty:
        messagebox.showinfo("Info", "No hay datos para exportar")
        return

    # obtener nombre real de la labor
    labor_real = df["Labor"].iloc[0]

    nombre = f"historial_labor_{labor_real}.pdf".replace(" ","_")

    pdf = SimpleDocTemplate(
        nombre,
        pagesize=letter
    )

    estilos = getSampleStyleSheet()

    elementos = []

    titulo = Paragraph("HISTORIAL DE LABORES - GEOMECÁNICA", estilos["Title"])
    elementos.append(titulo)

    elementos.append(Spacer(1,10))

    fecha_texto = Paragraph(f"Fecha de exportación: {fecha_hoy}", estilos['Normal'])
    elementos.append(fecha_texto)

    elementos.append(Spacer(1,20))

    subtitulo = Paragraph(f"Labor: {labor_real}", estilos["Heading2"])
    elementos.append(subtitulo)

    elementos.append(Spacer(1,20))

    # volver a texto para el PDF
    df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")

    datos = [df.columns.tolist()]

    for _, row in df.iterrows():

        fila = [
            row["Fecha"],
            row["Turno"],
            row["Labor"],
            row["GSI"],
            row["RMR"],
            Paragraph(str(row["Soporte"]), estilos["Normal"]),
            Paragraph(str(row["Observaciones"]), estilos["Normal"])
        ]

        datos.append(fila)

    tabla = Table(datos, colWidths=[60,50,80,40,40,120,130])

    tabla.setStyle(TableStyle([

        ("BACKGROUND",(0,0),(-1,0),colors.darkblue),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),

        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),

        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),

        ("GRID",(0,0),(-1,-1),1,colors.grey),

        ("BACKGROUND",(0,1),(-1,-1),colors.whitesmoke)

    ]))

    elementos.append(tabla)

    pdf.build(elementos)

    messagebox.showinfo("PDF", f"Historial exportado:\n{nombre}")

    

# ---------------------------------------------------------
# CARGAR ÚLTIMO REGISTRO DE LA LABOR
# ---------------------------------------------------------

def cargar_ultimo_registro(labor):

    df = pd.read_excel(archivo, sheet_name="Bitacora")

    df_labor = df[df["Labor"] == labor]

    if df_labor.empty:
        return

    ultimo = df_labor.iloc[-1]

    entrada_gsi.delete(0, tk.END)
    entrada_gsi.insert(0, ultimo["GSI"])

    entrada_rmr.delete(0, tk.END)
    entrada_rmr.insert(0, ultimo["RMR"])

    entrada_soporte.delete(0, tk.END)
    entrada_soporte.insert(0, ultimo["Soporte"])

    label_ultimo.config(
        text=f"Último registro: {ultimo['Fecha']} | Turno {ultimo['Turno']} | RMR {ultimo['RMR']}"
    )

# ---------------------------------------------------------
# INTERFAZ MODERNA
# ---------------------------------------------------------

inicializar_excel()

ventana = tk.Tk()
ventana.title("Bitácora Geomecánica")
ventana.geometry("650x650")
ventana.configure(bg="#f2f4f7")

style = ttk.Style()
style.theme_use("clam")

titulo = tk.Label(
    ventana,
    text="BITÁCORA GEOMECÁNICA",
    font=("Segoe UI",18,"bold"),
    bg="#f2f4f7"
)
titulo.pack(pady=10)

subtitulo = tk.Label(
    ventana,
    text="Registro de condiciones del macizo rocoso",
    font=("Segoe UI",10),
    bg="#f2f4f7"
)
subtitulo.pack()

frame_principal = ttk.Frame(ventana, padding=20)
frame_principal.pack(fill="both", expand=True, padx=20, pady=10)

ttk.Label(frame_principal,text="Fecha").grid(row=0,column=0,sticky="w")
ttk.Label(frame_principal,text=datetime.now().strftime("%d/%m/%Y")).grid(row=0,column=1,sticky="w")

ttk.Label(frame_principal,text="Turno").grid(row=1,column=0,sticky="w")

turno_var = tk.StringVar()

combo_turno = ttk.Combobox(
    frame_principal,
    textvariable=turno_var,
    state="readonly"
)

combo_turno["values"]=["Día","Noche"]
combo_turno.grid(row=1,column=1,sticky="ew")

ttk.Label(frame_principal,text="Labor").grid(row=2,column=0,sticky="w")

labor_var = tk.StringVar()

entrada_labor = ttk.Entry(frame_principal,textvariable=labor_var)
entrada_labor.grid(row=2,column=1,sticky="ew")

entrada_labor.bind("<KeyRelease>",filtrar_labores)

lista_filtrada = tk.Listbox(frame_principal,height=5)
lista_filtrada.grid(row=3,column=1,sticky="ew")

lista_filtrada.bind("<<ListboxSelect>>",seleccionar_labor)

label_ultimo = ttk.Label(frame_principal,text="",foreground="gray")
label_ultimo.grid(row=4,column=1,sticky="w",pady=5)

ttk.Label(frame_principal,text="GSI").grid(row=5,column=0,sticky="w")

entrada_gsi = ttk.Entry(frame_principal)
entrada_gsi.grid(row=5,column=1,sticky="ew")

ttk.Label(frame_principal,text="RMR").grid(row=6,column=0,sticky="w")

entrada_rmr = ttk.Entry(frame_principal)
entrada_rmr.grid(row=6,column=1,sticky="ew")

entrada_rmr.bind("<KeyRelease>",calcular_soporte)

ttk.Label(frame_principal,text="Soporte recomendado").grid(row=7,column=0,sticky="w")

entrada_soporte = ttk.Entry(frame_principal)
entrada_soporte.grid(row=7,column=1,sticky="ew")

ttk.Label(frame_principal,text="Observaciones").grid(row=8,column=0,sticky="nw")

entrada_obs = tk.Text(frame_principal,height=5,width=30)
entrada_obs.grid(row=8,column=1,sticky="ew")

frame_principal.columnconfigure(1,weight=1)

frame_botones = ttk.Frame(ventana)
frame_botones.pack(pady=10)

ttk.Button(
    frame_botones,
    text="Guardar Registro",
    command=guardar_datos
).grid(row=0,column=0,padx=5,pady=5)

ttk.Button(
    frame_botones,
    text="Ver Historial",
    command=ver_historial
).grid(row=0,column=1,padx=5,pady=5)

ttk.Button(
    frame_botones,
    text="Reporte Diario PDF",
    command=generar_reporte
).grid(row=0,column=2,padx=5,pady=5)

ttk.Button(
    frame_botones,
    text="Estándar de Sostenimiento",
    command=editar_estandar
).grid(row=0,column=3,padx=5,pady=5)

actualizar_labores()

ventana.mainloop()