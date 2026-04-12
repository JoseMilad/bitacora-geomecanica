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
from src.utils.config import PALETTE, APP_VERSION


class WelcomeScreen:
    """Pantalla de bienvenida que se muestra al iniciar la aplicación."""

    def __init__(self):
        self.result = None
        self.win = tk.Tk()
        self.win.title("Bitácora Geomecánica")
        self.win.resizable(False, False)
        self.win.configure(bg=PALETTE["sidebar_bg"])

        w, h = 500, 400
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        bg = PALETTE["sidebar_bg"]

        # Contenido centrado
        container = tk.Frame(self.win, bg=bg)
        container.pack(expand=True, fill="both")

        # Icono y título
        tk.Label(
            container, text="⛰", bg=bg, fg=PALETTE["accent"],
            font=("Segoe UI", 48),
        ).pack(pady=(40, 5))

        tk.Label(
            container, text="Bitácora Geomecánica",
            bg=bg, fg="#ffffff",
            font=("Segoe UI", 22, "bold"),
        ).pack(pady=(0, 5))

        tk.Label(
            container, text="Plataforma de gestión minera",
            bg=bg, fg=PALETTE["sidebar_text"],
            font=("Segoe UI", 10),
        ).pack(pady=(0, 25))

        # Features
        features_frame = tk.Frame(container, bg=bg)
        features_frame.pack(pady=(0, 25))

        features = [
            "📋 Registro de Bitácora",
            "🪨 Sostenimiento Diario",
            "📊 Dashboard & Reportes",
            "📷 Registro Fotográfico",
        ]
        for i, feat in enumerate(features):
            row, col = divmod(i, 2)
            lbl = tk.Label(
                features_frame, text=feat,
                bg="#2a3a5c", fg="#c8d6e5",
                font=("Segoe UI", 9),
                padx=12, pady=4,
            )
            lbl.grid(row=row, column=col, padx=4, pady=3, sticky="ew")

        # Botón ingresar
        btn = tk.Button(
            container, text="  Ingresar  ",
            bg=PALETTE["primary"], fg="#ffffff",
            activebackground=PALETTE["primary_hover"], activeforeground="#ffffff",
            font=("Segoe UI", 12, "bold"), bd=0, cursor="hand2",
            command=self._ingresar,
        )
        btn.pack(ipady=8, ipadx=20)

        # Versión
        tk.Label(
            container, text=f"v{APP_VERSION}",
            bg=bg, fg=PALETTE["sidebar_text"],
            font=("Segoe UI", 8),
        ).pack(pady=(15, 0))

    def _ingresar(self):
        self.result = True
        self.win.destroy()

    def run(self) -> bool:
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.mainloop()
        return self.result is not None

    def _on_close(self):
        self.result = None
        self.win.destroy()


def main():
    """Función principal que inicia la aplicación"""
    # Registrar inicio
    LoggerBitacora.registrar_inicio_app()

    try:
        # Mostrar pantalla de bienvenida
        welcome = WelcomeScreen()
        if not welcome.run():
            LoggerBitacora.registrar_cierre_app()
            return

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