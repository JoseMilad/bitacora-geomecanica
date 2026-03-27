"""
Sistema de notificaciones toast no bloqueantes.
"""
import tkinter as tk


def mostrar_toast(root, mensaje, tipo="info", duracion=3000):
    """Muestra una notificación toast en la esquina inferior derecha.

    Args:
        root: Ventana raíz de tkinter.
        mensaje: Texto a mostrar.
        tipo: "info" | "success" | "error" | "warning".
        duracion: Milisegundos antes de desaparecer (default 3000).
    """
    COLORES = {
        "info":    {"bg": "#1a6fc4", "fg": "#ffffff"},
        "success": {"bg": "#10b981", "fg": "#ffffff"},
        "error":   {"bg": "#d94f3d", "fg": "#ffffff"},
        "warning": {"bg": "#f59e0b", "fg": "#1a202c"},
    }
    esquema = COLORES.get(tipo, COLORES["info"])

    toast = tk.Toplevel(root)
    toast.overrideredirect(True)          # Sin decoraciones
    toast.attributes("-topmost", True)    # Siempre encima
    toast.configure(bg=esquema["bg"])

    lbl = tk.Label(
        toast,
        text=mensaje,
        bg=esquema["bg"],
        fg=esquema["fg"],
        font=("Segoe UI", 10),
        padx=16,
        pady=10,
        wraplength=300,
        justify="left",
    )
    lbl.pack()

    # Posicionar en esquina inferior derecha
    toast.update_idletasks()
    ancho = toast.winfo_reqwidth()
    alto  = toast.winfo_reqheight()
    x = root.winfo_x() + root.winfo_width() - ancho - 20
    y = root.winfo_y() + root.winfo_height() - alto  - 40
    toast.geometry(f"+{x}+{y}")

    toast.after(duracion, toast.destroy)
