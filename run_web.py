"""Punto de entrada del servidor web de Bitácora Geomecánica"""
import os
import uvicorn
from dotenv import load_dotenv

# Carga las variables del archivo .env (si existe)
load_dotenv()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=port, reload=False)