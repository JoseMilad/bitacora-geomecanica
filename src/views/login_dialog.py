"""
Diálogo de login para la aplicación de escritorio (Tkinter).
Incluye pestaña de registro de nuevos usuarios.
"""
import tkinter as tk
from tkinter import messagebox
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.auth import inicializar_tabla_usuarios, autenticar_usuario, crear_usuario
from src.utils.config import PALETTE


class LoginDialog:
    """Ventana de login modal para la app de escritorio con registro de usuarios."""

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
        w, h = 420, 460
        x = (self.win.winfo_screenwidth() - w) // 2
        y = (self.win.winfo_screenheight() - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")

        # Inicializar tabla de usuarios (crea admin por defecto si no existe)
        inicializar_tabla_usuarios()

        self._modo = "login"  # "login" o "registro"
        self._build_ui()

        # Atajo Enter para login
        self.win.bind("<Return>", lambda e: self._submit())

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

        # Contenedor de pestañas (login / registro)
        self._tab_frame = tk.Frame(self.win, bg=bg)
        self._tab_frame.pack(fill="x", padx=30, pady=(10, 0))

        self._btn_tab_login = tk.Button(
            self._tab_frame, text="Iniciar Sesión",
            bg=PALETTE["primary"], fg="#ffffff",
            activebackground=PALETTE["primary_hover"], activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2",
            command=lambda: self._switch_mode("login"),
        )
        self._btn_tab_login.pack(side="left", fill="x", expand=True, ipady=4)

        self._btn_tab_registro = tk.Button(
            self._tab_frame, text="Registrarse",
            bg=PALETTE["card_border"], fg=PALETTE["text_primary"],
            activebackground=PALETTE["primary"], activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"), bd=0, cursor="hand2",
            command=lambda: self._switch_mode("registro"),
        )
        self._btn_tab_registro.pack(side="left", fill="x", expand=True, ipady=4)

        # Body container
        self._body_container = tk.Frame(self.win, bg=bg)
        self._body_container.pack(fill="both", expand=True)

        self._build_login_body()
        self._build_registro_body()

        # Mostrar login por defecto
        self._show_login()

    def _build_login_body(self):
        bg = PALETTE["surface"]
        self._login_body = tk.Frame(self._body_container, bg=bg, padx=30, pady=15)

        tk.Label(self._login_body, text="Usuario", bg=bg, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_user = tk.Entry(self._login_body, font=("Segoe UI", 11))
        self.entry_user.pack(fill="x", ipady=4, pady=(0, 10))

        tk.Label(self._login_body, text="Contraseña", bg=bg, font=("Segoe UI", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_pass = tk.Entry(self._login_body, font=("Segoe UI", 11), show="●")
        self.entry_pass.pack(fill="x", ipady=4, pady=(0, 14))

        btn = tk.Button(
            self._login_body, text="  Iniciar Sesión  ",
            bg=PALETTE["primary"], fg="#ffffff",
            activebackground=PALETTE["primary_hover"], activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), bd=0, cursor="hand2",
            command=self._login,
        )
        btn.pack(fill="x", ipady=6)

        tk.Label(
            self._login_body, text="Por defecto: admin / admin1234",
            bg=bg, fg=PALETTE["text_muted"], font=("Segoe UI", 8),
        ).pack(pady=(8, 0))

    def _build_registro_body(self):
        bg = PALETTE["surface"]
        self._registro_body = tk.Frame(self._body_container, bg=bg, padx=30, pady=15)

        tk.Label(self._registro_body, text="Nombre completo", bg=bg,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_reg_nombre = tk.Entry(self._registro_body, font=("Segoe UI", 11))
        self.entry_reg_nombre.pack(fill="x", ipady=4, pady=(0, 8))

        tk.Label(self._registro_body, text="Usuario", bg=bg,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_reg_user = tk.Entry(self._registro_body, font=("Segoe UI", 11))
        self.entry_reg_user.pack(fill="x", ipady=4, pady=(0, 8))

        tk.Label(self._registro_body, text="Contraseña", bg=bg,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_reg_pass = tk.Entry(self._registro_body, font=("Segoe UI", 11), show="●")
        self.entry_reg_pass.pack(fill="x", ipady=4, pady=(0, 8))

        tk.Label(self._registro_body, text="Confirmar contraseña", bg=bg,
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.entry_reg_pass2 = tk.Entry(self._registro_body, font=("Segoe UI", 11), show="●")
        self.entry_reg_pass2.pack(fill="x", ipady=4, pady=(0, 12))

        btn = tk.Button(
            self._registro_body, text="  Crear Cuenta  ",
            bg=PALETTE["secondary"], fg="#ffffff",
            activebackground=PALETTE["secondary_hover"], activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"), bd=0, cursor="hand2",
            command=self._registrar,
        )
        btn.pack(fill="x", ipady=6)

    def _switch_mode(self, modo: str):
        self._modo = modo
        if modo == "login":
            self._show_login()
        else:
            self._show_registro()

    def _show_login(self):
        self._registro_body.pack_forget()
        self._login_body.pack(fill="both", expand=True)
        self._btn_tab_login.config(bg=PALETTE["primary"], fg="#ffffff")
        self._btn_tab_registro.config(bg=PALETTE["card_border"], fg=PALETTE["text_primary"])
        self.entry_user.focus_set()

    def _show_registro(self):
        self._login_body.pack_forget()
        self._registro_body.pack(fill="both", expand=True)
        self._btn_tab_registro.config(bg=PALETTE["primary"], fg="#ffffff")
        self._btn_tab_login.config(bg=PALETTE["card_border"], fg=PALETTE["text_primary"])
        self.entry_reg_nombre.focus_set()

    def _submit(self):
        if self._modo == "login":
            self._login()
        else:
            self._registrar()

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

    def _registrar(self):
        nombre = self.entry_reg_nombre.get().strip()
        username = self.entry_reg_user.get().strip()
        password = self.entry_reg_pass.get()
        password2 = self.entry_reg_pass2.get()

        if not username or not password:
            messagebox.showwarning("Campos requeridos", "Ingrese usuario y contraseña.", parent=self.win)
            return
        if password != password2:
            messagebox.showwarning("Error", "Las contraseñas no coinciden.", parent=self.win)
            return
        if len(password) < 4:
            messagebox.showwarning("Error", "La contraseña debe tener al menos 4 caracteres.", parent=self.win)
            return

        ok, msg = crear_usuario(username, password, nombre=nombre, rol="usuario")
        if ok:
            messagebox.showinfo("Registro exitoso", f"{msg}\nAhora puede iniciar sesión.", parent=self.win)
            # Limpiar campos y cambiar a login
            self.entry_reg_nombre.delete(0, "end")
            self.entry_reg_user.delete(0, "end")
            self.entry_reg_pass.delete(0, "end")
            self.entry_reg_pass2.delete(0, "end")
            self._switch_mode("login")
            self.entry_user.insert(0, username)
            self.entry_pass.focus_set()
        else:
            messagebox.showerror("Error", msg, parent=self.win)

    def run(self) -> dict | None:
        """Ejecuta el diálogo y devuelve el usuario autenticado o None."""
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.mainloop()
        return self.result

    def _on_close(self):
        self.result = None
        self.win.destroy()
