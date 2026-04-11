"""
Diálogo de login para la aplicación de escritorio (Tkinter).
"""
import tkinter as tk
from tkinter import messagebox
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.auth import inicializar_tabla_usuarios, autenticar_usuario
from src.utils.config import PALETTE


class LoginDialog:
    """Ventana de login modal para la app de escritorio."""

    def __init__(self, parent: tk.Tk | None = None):
        self.result: dict | None = None

        # Crear ventana toplevel o root
        if parent:
            self.win = tk.Toplevel(parent)
            self.win.transient(parent)
            self.win.grab_set()
        else:
            self.win = tk.Tk()

        self.win.title("Bitácora Geomecánica — Iniciar Sesión")
        self.win.resizable(False, False)
        self.win.configure(bg=PALETTE["surface"])

        # Centrar ventana
        w, h = 380, 340
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        # Inicializar tabla de usuarios (crea admin por defecto si no existe)
        inicializar_tabla_usuarios()

        self._build_ui()

        # Atajo Enter para login
        self.win.bind("<Return>", lambda e: self._login())

    def _build_ui(self):
        bg = PALETTE["surface"]
        header_bg = PALETTE["sidebar_bg"]

        # Header
        header = tk.Frame(self.win, bg=header_bg, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="⛰ Bitácora Geomecánica",
            bg=header_bg, fg="#ffffff",
            font=("Segoe UI", 14, "bold"),
        ).pack(pady=(20, 2))
        tk.Label(
            header, text="Plataforma de gestión minera",
            bg=header_bg, fg=PALETTE["sidebar_text"],
            font=("Segoe UI", 9),
        ).pack()

        # Body
        body = tk.Frame(self.win, bg=bg, padx=30, pady=20)
        body.pack(fill="both", expand=True)

        # Usuario
        tk.Label(body, text="Usuario", bg=bg, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_user = tk.Entry(body, font=("Segoe UI", 11))
        self.entry_user.pack(fill="x", ipady=4, pady=(0, 12))
        self.entry_user.focus_set()

        # Contraseña
        tk.Label(body, text="Contraseña", bg=bg, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_pass = tk.Entry(body, font=("Segoe UI", 11), show="●")
        self.entry_pass.pack(fill="x", ipady=4, pady=(0, 16))

        # Botón login
        btn = tk.Button(
            body, text="  Iniciar Sesión  ",
            bg=PALETTE["primary"], fg="#ffffff",
            activebackground=PALETTE["primary_hover"], activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), bd=0, cursor="hand2",
            command=self._login,
        )
        btn.pack(fill="x", ipady=6)

        # Info
        tk.Label(
            body, text="Por defecto: admin / admin1234",
            bg=bg, fg=PALETTE["text_muted"], font=("Segoe UI", 8),
        ).pack(pady=(8, 0))

    def _login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        if not username or not password:
            messagebox.showwarning("Campos requeridos", "Ingrese usuario y contraseña.", parent=self.win)
            return
        user = autenticar_usuario(username, password)
        if user:
            self.result = user
            self.win.destroy()
        else:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.", parent=self.win)
            self.entry_pass.delete(0, "end")
            self.entry_pass.focus_set()

    def run(self) -> dict | None:
        """Ejecuta el diálogo y devuelve el usuario autenticado o None."""
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.mainloop()
        return self.result

    def _on_close(self):
        self.result = None
        self.win.destroy()
