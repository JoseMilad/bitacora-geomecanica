# bitacora-geomecanica
Mining Geomechanical Log Automation

## 🌐 Plataforma Web

La aplicación también está disponible como plataforma web empresarial.

### Instalación adicional
```bash
pip install -r requirements.txt
```

### Iniciar servidor web
```bash
python run_web.py
```

Acceder en: http://localhost:8000

### Características web
- Dashboard con KPIs y gráficos
- Gestión completa de Bitácora (CRUD)
- Catálogo de Labores
- Sostenimiento Diario
- Exportación a Excel
- Documentación API automática: http://localhost:8000/docs

---

## 🚀 Despliegue en Render

### Pasos para desplegar en [Render](https://render.com)

1. Crea una cuenta en [render.com](https://render.com) y conecta tu repositorio de GitHub.
2. Selecciona **"New Web Service"** y elige este repositorio.
3. Configura el servicio con los siguientes parámetros:

| Parámetro | Valor |
|---|---|
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn src.web.app:app --host 0.0.0.0 --port $PORT` |

4. En la sección **Environment Variables**, agrega:

| Variable | Descripción |
|---|---|
| `BITACORA_SECRET_KEY` | Clave secreta segura y aleatoria (p. ej. generada con `openssl rand -hex 32`) |
| `DATABASE_URL` | Cadena de conexión MySQL (ej: `mysql+pymysql://usuario:contraseña@localhost:3306/bitacora_geomecanica`) |

5. Haz clic en **"Create Web Service"** y Render desplegará la aplicación automáticamente.

### 💾 Persistencia de datos (MySQL)

La aplicación usa **MySQL** como base de datos principal (configurable con `DATABASE_URL`) y mantiene archivos Excel en `data/` para exportación/sincronización.

Para entornos productivos, define credenciales reales por variables de entorno (recomendado) y evita hardcodear usuarios/contraseñas en el código.
