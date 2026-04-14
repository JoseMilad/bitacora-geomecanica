"""Punto de entrada del servidor web de Bitácora Geomecánica"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.web.app:app", host="0.0.0.0", port=port, reload=False)
