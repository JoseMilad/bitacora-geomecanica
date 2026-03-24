"""
Punto de entrada de la aplicación Bitácora Geomecánica
"""
import tkinter as tk
import sys
from pathlib import Path

# Agregar la ruta del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.views.bitacora_ui import BitacoraApp
from src.utils.logger import LoggerBitacora


def main():
    """Función principal que inicia la aplicación"""
    # Registrar inicio
    LoggerBitacora.registrar_inicio_app()
    
    try:
        root = tk.Tk()
        app = BitacoraApp(root)
        root.mainloop()
    except Exception as e:
        LoggerBitacora.registrar_error("MAIN", e)
        raise
    finally:
        # Registrar cierre
        LoggerBitacora.registrar_cierre_app()


if __name__ == "__main__":
    main()