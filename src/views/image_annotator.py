"""
Herramienta de anotación de imágenes para la Bitácora Geomecánica.

Permite cargar imágenes, dibujar líneas, trazos a mano alzada y círculos
sobre ellas, y guardar el resultado compuesto en ``data/images/``.
"""

import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageTk

from utils.config import DATA_DIR, PALETTE

# ── Constantes de dibujo ────────────────────────────────────────────
DRAW_COLOR = "#ff0000"
LINE_WIDTH = 2
CANVAS_BG = "#ffffff"
IMAGES_DIR = DATA_DIR / "images"

# Herramientas disponibles
_TOOLS = ("line", "pencil", "circle")


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convierte un color hexadecimal a tupla RGB."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


# ── Clase principal ─────────────────────────────────────────────────


class VentanaAnotador(tk.Toplevel):
    """Ventana modal para anotar imágenes con herramientas de dibujo.

    Parameters
    ----------
    parent : tk.Widget
        Widget padre sobre el cual se abre la ventana modal.
    image_path : str | Path | None
        Ruta opcional de una imagen existente para cargar al abrir.
    callback : callable | None
        Función que recibe la ruta del archivo guardado al completar
        la operación de guardado.
    """

    # ------------------------------------------------------------------ init
    def __init__(self, parent, *, image_path=None, callback=None):
        super().__init__(parent)
        self.title("Anotador de Imágenes")
        self.configure(bg=PALETTE["surface"])

        # Estado interno
        self._callback = callback
        self._pil_image: Image.Image | None = None
        self._tk_image: ImageTk.PhotoImage | None = None
        self._image_path: Path | None = None
        self._scale: float = 1.0
        self._offset_x: int = 0
        self._offset_y: int = 0
        self._active_tool: str | None = None
        self._drawing = False
        self._start_x: int = 0
        self._start_y: int = 0
        self._preview_id: int | None = None
        self._pencil_points: list[tuple[int, int]] = []
        self.annotations: list[dict] = []

        # Construir la interfaz
        self._build_toolbar()
        self._build_canvas()

        # Configurar como ventana modal
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.minsize(700, 500)

        # Cargar imagen si se proporcionó una ruta
        if image_path is not None:
            self._load_image(Path(image_path))

        # Diccionario de botones de herramienta (se llena en _build_toolbar)
        # ya está construido arriba; centrar ventana después de renderizar
        self.update_idletasks()
        self._center_window()

    # ─────────────────────────────────── construcción de la interfaz

    def _build_toolbar(self):
        """Crea la barra de herramientas superior."""
        toolbar = tk.Frame(self, bg=PALETTE["sidebar_bg"], pady=6, padx=6)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        buttons_cfg = [
            ("📂 Cargar Imagen", self._on_load_image, None),
            ("📏 Línea", lambda: self._select_tool("line"), "line"),
            ("✏️ Lápiz", lambda: self._select_tool("pencil"), "pencil"),
            ("⭕ Círculo", lambda: self._select_tool("circle"), "circle"),
            ("💾 Guardar Anotaciones", self._on_save, None),
        ]

        self._tool_buttons: dict[str, tk.Button] = {}

        for text, command, tool_key in buttons_cfg:
            btn = tk.Button(
                toolbar,
                text=text,
                command=command,
                bg=PALETTE["primary"],
                fg="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                cursor="hand2",
                padx=10,
                pady=4,
                activebackground=PALETTE["primary_hover"],
                activeforeground="#ffffff",
            )
            btn.pack(side=tk.LEFT, padx=3)

            # Efecto hover estándar del proyecto
            normal_bg = PALETTE["primary"]
            hover_bg = PALETTE["primary_hover"]
            btn.bind("<Enter>", lambda e, b=btn, h=hover_bg: b.configure(bg=h))
            btn.bind(
                "<Leave>",
                lambda e, b=btn, n=normal_bg: b.configure(
                    bg=PALETTE["accent"] if self._is_active(b) else n
                ),
            )

            if tool_key is not None:
                self._tool_buttons[tool_key] = btn

    def _build_canvas(self):
        """Crea el lienzo de dibujo."""
        frame = tk.Frame(self, bg=PALETTE["card_border"], bd=1, relief="solid")
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.canvas = tk.Canvas(frame, bg=CANVAS_BG, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bindear eventos de ratón
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Redibujar al cambiar tamaño
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    # ─────────────────────────────────── utilidades de ventana

    def _center_window(self):
        """Centra la ventana en la pantalla."""
        w, h = 900, 650
        self.geometry(f"{w}x{h}")
        sx = self.winfo_screenwidth()
        sy = self.winfo_screenheight()
        x = (sx - w) // 2
        y = (sy - h) // 2
        self.geometry(f"+{x}+{y}")

    def _on_close(self):
        """Cierra la ventana modal liberando el grab."""
        self.grab_release()
        self.destroy()

    # ─────────────────────────────────── selección de herramientas

    def _is_active(self, btn: tk.Button) -> bool:
        """Devuelve True si *btn* es la herramienta activa."""
        for key, b in self._tool_buttons.items():
            if b is btn and key == self._active_tool:
                return True
        return False

    def _select_tool(self, tool: str):
        """Activa una herramienta de dibujo y resalta su botón."""
        self._active_tool = tool

        for key, btn in self._tool_buttons.items():
            if key == tool:
                btn.configure(bg=PALETTE["accent"])
            else:
                btn.configure(bg=PALETTE["primary"])

    # ─────────────────────────────────── carga de imagen

    def _on_load_image(self):
        """Abre un diálogo para seleccionar una imagen."""
        filepath = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar imagen",
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png"),
                ("JPEG", "*.jpg *.jpeg"),
                ("PNG", "*.png"),
            ],
        )
        if filepath:
            self._load_image(Path(filepath))

    def _load_image(self, path: Path):
        """Carga una imagen desde *path*, la copia a ``data/images/`` y la
        muestra en el lienzo escalada proporcionalmente."""
        if not path.is_file():
            messagebox.showerror(
                "Error", f"No se encontró el archivo:\n{path}", parent=self
            )
            return

        # Copiar al directorio de imágenes del proyecto (si no viene de ahí)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        dest = IMAGES_DIR / path.name
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)

        self._image_path = dest
        self._pil_image = Image.open(dest).convert("RGBA")

        # Limpiar anotaciones previas
        self.annotations.clear()

        self._render_image()

    def _render_image(self):
        """Escala y dibuja la imagen actual en el lienzo."""
        if self._pil_image is None:
            return

        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            return

        iw, ih = self._pil_image.size
        self._scale = min(cw / iw, ch / ih)
        new_w = int(iw * self._scale)
        new_h = int(ih * self._scale)

        # Centrar la imagen en el lienzo
        self._offset_x = (cw - new_w) // 2
        self._offset_y = (ch - new_h) // 2

        resized = self._pil_image.resize((new_w, new_h), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.create_image(
            self._offset_x, self._offset_y, anchor=tk.NW, image=self._tk_image
        )

        # Redibujar las anotaciones existentes sobre el lienzo
        self._redraw_annotations()

    def _on_canvas_resize(self, _event):
        """Re-escala la imagen cuando cambia el tamaño del lienzo."""
        self._render_image()

    # ─────────────────────────────────── coordenadas imagen ↔ lienzo

    def _canvas_to_image(self, cx: int, cy: int) -> tuple[int, int]:
        """Convierte coordenadas de lienzo a coordenadas de imagen original."""
        ix = int((cx - self._offset_x) / self._scale)
        iy = int((cy - self._offset_y) / self._scale)
        return ix, iy

    def _image_to_canvas(self, ix: int, iy: int) -> tuple[float, float]:
        """Convierte coordenadas de imagen original a coordenadas de lienzo."""
        cx = ix * self._scale + self._offset_x
        cy = iy * self._scale + self._offset_y
        return cx, cy

    # ─────────────────────────────────── eventos de ratón

    def _on_press(self, event):
        """Inicia una operación de dibujo."""
        if self._active_tool is None or self._pil_image is None:
            return

        self._drawing = True
        self._start_x = event.x
        self._start_y = event.y

        if self._active_tool == "pencil":
            self._pencil_points = [(event.x, event.y)]

    def _on_motion(self, event):
        """Actualiza la previsualización mientras se arrastra el ratón."""
        if not self._drawing or self._active_tool is None:
            return

        if self._active_tool == "line":
            self._preview_line(event)
        elif self._active_tool == "pencil":
            self._preview_pencil(event)
        elif self._active_tool == "circle":
            self._preview_circle(event)

    def _on_release(self, event):
        """Finaliza la operación de dibujo y registra la anotación."""
        if not self._drawing or self._active_tool is None:
            return

        self._drawing = False

        if self._active_tool == "line":
            self._finalize_line(event)
        elif self._active_tool == "pencil":
            self._finalize_pencil(event)
        elif self._active_tool == "circle":
            self._finalize_circle(event)

        # Limpiar la previsualización
        self._preview_id = None

    # ── Línea ────────────────────────────────────────────────────────

    def _preview_line(self, event):
        """Dibuja la previsualización de una línea."""
        if self._preview_id is not None:
            self.canvas.delete(self._preview_id)
        self._preview_id = self.canvas.create_line(
            self._start_x,
            self._start_y,
            event.x,
            event.y,
            fill=DRAW_COLOR,
            width=LINE_WIDTH,
        )

    def _finalize_line(self, event):
        """Registra la línea como anotación en coordenadas de imagen."""
        ix0, iy0 = self._canvas_to_image(self._start_x, self._start_y)
        ix1, iy1 = self._canvas_to_image(event.x, event.y)
        self.annotations.append(
            {"tool": "line", "coords": [ix0, iy0, ix1, iy1], "color": DRAW_COLOR}
        )

    # ── Lápiz ────────────────────────────────────────────────────────

    def _preview_pencil(self, event):
        """Dibuja un segmento adicional del trazo libre."""
        last = self._pencil_points[-1]
        self.canvas.create_line(
            last[0],
            last[1],
            event.x,
            event.y,
            fill=DRAW_COLOR,
            width=LINE_WIDTH,
        )
        self._pencil_points.append((event.x, event.y))

    def _finalize_pencil(self, event):
        """Registra el trazo libre como anotación en coordenadas de imagen."""
        self._pencil_points.append((event.x, event.y))
        img_points = [
            self._canvas_to_image(px, py) for px, py in self._pencil_points
        ]
        # Aplanar a lista de coordenadas [x0,y0,x1,y1,...]
        flat: list[int] = []
        for pt in img_points:
            flat.extend(pt)
        self.annotations.append(
            {"tool": "pencil", "coords": flat, "color": DRAW_COLOR}
        )
        self._pencil_points.clear()

    # ── Círculo ──────────────────────────────────────────────────────

    def _preview_circle(self, event):
        """Dibuja la previsualización de un círculo."""
        if self._preview_id is not None:
            self.canvas.delete(self._preview_id)
        r = self._radius(self._start_x, self._start_y, event.x, event.y)
        self._preview_id = self.canvas.create_oval(
            self._start_x - r,
            self._start_y - r,
            self._start_x + r,
            self._start_y + r,
            outline=DRAW_COLOR,
            width=LINE_WIDTH,
        )

    def _finalize_circle(self, event):
        """Registra el círculo como anotación en coordenadas de imagen."""
        r_canvas = self._radius(self._start_x, self._start_y, event.x, event.y)
        cx, cy = self._canvas_to_image(self._start_x, self._start_y)
        r_img = int(r_canvas / self._scale) if self._scale else 0
        self.annotations.append(
            {"tool": "circle", "coords": [cx, cy, r_img], "color": DRAW_COLOR}
        )

    @staticmethod
    def _radius(x0, y0, x1, y1) -> float:
        """Calcula la distancia euclídea (radio) entre dos puntos."""
        return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5

    # ─────────────────────────────────── redibujo de anotaciones

    def _redraw_annotations(self):
        """Redibuja todas las anotaciones almacenadas sobre el lienzo."""
        for ann in self.annotations:
            color = ann["color"]
            coords = ann["coords"]

            if ann["tool"] == "line":
                cx0, cy0 = self._image_to_canvas(coords[0], coords[1])
                cx1, cy1 = self._image_to_canvas(coords[2], coords[3])
                self.canvas.create_line(
                    cx0, cy0, cx1, cy1, fill=color, width=LINE_WIDTH
                )

            elif ann["tool"] == "pencil":
                points = list(zip(coords[::2], coords[1::2]))
                for i in range(len(points) - 1):
                    cx0, cy0 = self._image_to_canvas(*points[i])
                    cx1, cy1 = self._image_to_canvas(*points[i + 1])
                    self.canvas.create_line(
                        cx0, cy0, cx1, cy1, fill=color, width=LINE_WIDTH
                    )

            elif ann["tool"] == "circle":
                cx, cy = self._image_to_canvas(coords[0], coords[1])
                r = coords[2] * self._scale
                self.canvas.create_oval(
                    cx - r, cy - r, cx + r, cy + r,
                    outline=color, width=LINE_WIDTH,
                )

    # ─────────────────────────────────── guardado

    def _on_save(self):
        """Compone la imagen con las anotaciones y la guarda en disco."""
        if self._pil_image is None:
            messagebox.showwarning(
                "Sin imagen",
                "Cargue una imagen antes de guardar.",
                parent=self,
            )
            return

        composite = self._compose_image()

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = self._image_path.stem if self._image_path else "imagen"
        filename = f"annotated_{timestamp}_{original_name}.png"
        save_path = IMAGES_DIR / filename

        composite.save(str(save_path), "PNG")

        messagebox.showinfo(
            "Guardado",
            f"Imagen anotada guardada en:\n{save_path}",
            parent=self,
        )

        if self._callback is not None:
            self._callback(str(save_path))

    def _compose_image(self) -> Image.Image:
        """Renderiza la imagen original con las anotaciones superpuestas.

        Returns
        -------
        Image.Image
            Imagen compuesta en modo RGB lista para guardar.
        """
        base = self._pil_image.copy().convert("RGBA")
        overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        for ann in self.annotations:
            rgb = _hex_to_rgb(ann["color"])
            coords = ann["coords"]

            if ann["tool"] == "line":
                draw.line(coords, fill=rgb, width=LINE_WIDTH)

            elif ann["tool"] == "pencil":
                points = list(zip(coords[::2], coords[1::2]))
                for i in range(len(points) - 1):
                    segment = [points[i], points[i + 1]]
                    draw.line(segment, fill=rgb, width=LINE_WIDTH)

            elif ann["tool"] == "circle":
                cx, cy, r = coords
                bbox = [cx - r, cy - r, cx + r, cy + r]
                draw.ellipse(bbox, outline=rgb, width=LINE_WIDTH)

        composite = Image.alpha_composite(base, overlay)
        return composite.convert("RGB")
