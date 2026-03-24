"""
Punto de entrada de la aplicación Bitácora Geomecánica
"""
import tkinter as tk
from views.bitacora_ui import BitacoraApp


def main():
    """Función principal que inicia la aplicación"""
    root = tk.Tk()
    app = BitacoraApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()