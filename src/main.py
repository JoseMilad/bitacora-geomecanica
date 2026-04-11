"""
Punto de entrada de la aplicación Bitácora Geomecánica
"""
import tkinter as tk
import sys
from pathlib import Path

# Agregar la ruta del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.views.bitacora_ui import BitacoraApp
from src.views.login_dialog import LoginDialog
from src.utils.logger import LoggerBitacora


def main():
    """Función principal que inicia la aplicación"""
    # Registrar inicio
    LoggerBitacora.registrar_inicio_app()

    try:
        # Mostrar diálogo de login
        login = LoginDialog()
        user = login.run()
        if not user:
            # El usuario cerró la ventana sin iniciar sesión
            LoggerBitacora.registrar_cierre_app()
            return

        root = tk.Tk()
        app = BitacoraApp(root)

        # Almacenar info del usuario en la app
        app._usuario_actual = user
        # Actualizar barra de estado si tiene el método
        if hasattr(app, "_barra_estado"):
            app._barra_estado.config(
                text=f"  Usuario: {user.get('nombre') or user.get('username')}  |  Rol: {user.get('rol', 'usuario')}"
            )

        root.mainloop()
    except Exception as e:
        LoggerBitacora.registrar_error("MAIN", e)
        raise
    finally:
        # Registrar cierre
        LoggerBitacora.registrar_cierre_app()


if __name__ == "__main__":
    main()