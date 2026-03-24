"""
Sistema de logging y auditoría para la Bitácora Geomecánica
"""
import logging
import os
from datetime import datetime
from pathlib import Path


class LoggerBitacora:
    """Gestor centralizado de logs para la bitácora"""
    
    # Directorio de logs
    LOGS_DIR = Path("logs")
    
    # Archivos de log
    LOG_GENERAL = LOGS_DIR / "bitacora.log"
    LOG_AUDITOR = LOGS_DIR / "auditoria.log"
    LOG_ERRORES = LOGS_DIR / "errores.log"
    
    _logger_general = None
    _logger_auditor = None
    _logger_errores = None
    
    @classmethod
    def _crear_directorio(cls):
        """Crea el directorio de logs si no existe"""
        cls.LOGS_DIR.mkdir(exist_ok=True)
    
    @classmethod
    def _configurar_logger(cls, nombre: str, archivo: Path) -> logging.Logger:
        """
        Configura un logger específico
        
        Args:
            nombre: Nombre del logger
            archivo: Ruta del archivo de log
            
        Returns:
            Logger configurado
        """
        logger = logging.getLogger(nombre)
        logger.setLevel(logging.DEBUG)
        
        # Evitar duplicados
        if logger.handlers:
            return logger
        
        # Crear formateador
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        
        # Handler para archivo
        file_handler = logging.FileHandler(archivo, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Handler para consola (solo para errores)
        if "errores" in nombre:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger
    
    @classmethod
    def obtener_logger_general(cls) -> logging.Logger:
        """Obtiene el logger general"""
        cls._crear_directorio()
        if cls._logger_general is None:
            cls._logger_general = cls._configurar_logger(
                "general",
                cls.LOG_GENERAL
            )
        return cls._logger_general
    
    @classmethod
    def obtener_logger_auditor(cls) -> logging.Logger:
        """Obtiene el logger de auditoría"""
        cls._crear_directorio()
        if cls._logger_auditor is None:
            cls._logger_auditor = cls._configurar_logger(
                "auditor",
                cls.LOG_AUDITOR
            )
        return cls._logger_auditor
    
    @classmethod
    def obtener_logger_errores(cls) -> logging.Logger:
        """Obtiene el logger de errores"""
        cls._crear_directorio()
        if cls._logger_errores is None:
            cls._logger_errores = cls._configurar_logger(
                "errores",
                cls.LOG_ERRORES
            )
        return cls._logger_errores
    
    @staticmethod
    def registrar_inicio_app():
        """Registra el inicio de la aplicación"""
        logger = LoggerBitacora.obtener_logger_general()
        logger.info("=" * 60)
        logger.info("APLICACIÓN INICIADA")
        logger.info("=" * 60)
    
    @staticmethod
    def registrar_cierre_app():
        """Registra el cierre de la aplicación"""
        logger = LoggerBitacora.obtener_logger_general()
        logger.info("=" * 60)
        logger.info("APLICACIÓN CERRADA")
        logger.info("=" * 60)
    
    @staticmethod
    def registrar_guardar_registro(datos: dict):
        """
        Registra el guardado de un nuevo registro
        
        Args:
            datos: Diccionario con datos del registro
        """
        logger = LoggerBitacora.obtener_logger_auditor()
        logger.info(
            f"REGISTRO GUARDADO - Turno: {datos.get('Turno')}, "
            f"Labor: {datos.get('Labor')}, "
            f"RMR: {datos.get('RMR')}, "
            f"GSI: {datos.get('GSI')}"
        )
    
    @staticmethod
    def registrar_editar_registro(id_registro: int, cambios: dict):
        """
        Registra la edición de un registro
        
        Args:
            id_registro: ID del registro editado
            cambios: Diccionario con cambios realizados
        """
        logger = LoggerBitacora.obtener_logger_auditor()
        cambios_str = ", ".join([f"{k}: {v}" for k, v in cambios.items()])
        logger.info(f"REGISTRO EDITADO - ID: {id_registro}, Cambios: {cambios_str}")
    
    @staticmethod
    def registrar_eliminar_registro(id_registro: int, labor: str):
        """
        Registra la eliminación de un registro
        
        Args:
            id_registro: ID del registro eliminado
            labor: Labor del registro eliminado
        """
        logger = LoggerBitacora.obtener_logger_auditor()
        logger.warning(f"REGISTRO ELIMINADO - ID: {id_registro}, Labor: {labor}")
    
    @staticmethod
    def registrar_generar_reporte(tipo_reporte: str, fecha: str):
        """
        Registra la generación de un reporte
        
        Args:
            tipo_reporte: Tipo de reporte generado
            fecha: Fecha del reporte
        """
        logger = LoggerBitacora.obtener_logger_auditor()
        logger.info(f"REPORTE GENERADO - Tipo: {tipo_reporte}, Fecha: {fecha}")
    
    @staticmethod
    def registrar_busqueda(criterios: dict, resultados: int):
        """
        Registra una búsqueda realizada
        
        Args:
            criterios: Criterios de búsqueda
            resultados: Número de resultados encontrados
        """
        logger = LoggerBitacora.obtener_logger_general()
        criterios_str = ", ".join([f"{k}: {v}" for k, v in criterios.items() if v])
        logger.info(f"BÚSQUEDA REALIZADA - Criterios: {criterios_str}, Resultados: {resultados}")
    
    @staticmethod
    def registrar_error(seccion: str, error: Exception):
        """
        Registra un error
        
        Args:
            seccion: Sección donde ocurrió el error
            error: Excepción capturada
        """
        logger = LoggerBitacora.obtener_logger_errores()
        logger.error(f"ERROR EN {seccion}: {str(error)}", exc_info=True)
    
    @staticmethod
    def registrar_validacion_fallida(campo: str, valor: str, razon: str):
        """
        Registra una validación fallida
        
        Args:
            campo: Campo que falló la validación
            valor: Valor ingresado
            razon: Razón de la validación fallida
        """
        logger = LoggerBitacora.obtener_logger_general()
        logger.warning(f"VALIDACIÓN FALLIDA - Campo: {campo}, Valor: {valor}, Razón: {razon}")
    
    @staticmethod
    def registrar_carga_datos(cantidad: int, archivo: str):
        """
        Registra la carga de datos
        
        Args:
            cantidad: Cantidad de registros cargados
            archivo: Archivo desde el que se cargó
        """
        logger = LoggerBitacora.obtener_logger_general()
        logger.info(f"DATOS CARGADOS - Cantidad: {cantidad} registros, Archivo: {archivo}")
    
    @staticmethod
    def registrar_exportar_datos(cantidad: int, formato: str, archivo_salida: str):
        """
        Registra la exportación de datos
        
        Args:
            cantidad: Cantidad de registros exportados
            formato: Formato de exportación (PDF, Excel, etc)
            archivo_salida: Ruta del archivo de salida
        """
        logger = LoggerBitacora.obtener_logger_auditor()
        logger.info(f"DATOS EXPORTADOS - Cantidad: {cantidad}, Formato: {formato}, Archivo: {archivo_salida}")
    
    @staticmethod
    def obtener_log_reciente(tipo: str = "general", lineas: int = 10) -> list:
        """
        Obtiene las líneas más recientes del log
        
        Args:
            tipo: Tipo de log ("general", "auditor", "errores")
            lineas: Número de líneas a obtener
            
        Returns:
            Lista con las líneas del log
        """
        if tipo == "general":
            archivo = LoggerBitacora.LOG_GENERAL
        elif tipo == "auditor":
            archivo = LoggerBitacora.LOG_AUDITOR
        else:
            archivo = LoggerBitacora.LOG_ERRORES
        
        if not archivo.exists():
            return []
        
        try:
            with open(archivo, 'r', encoding='utf-8') as f:
                todas_las_lineas = f.readlines()
            return todas_las_lineas[-lineas:]
        except Exception as e:
            return [f"Error al leer el archivo: {str(e)}"]
    
    @staticmethod
    def limpiar_logs_antiguos(dias: int = 30):
        """
        Limpia los logs más antiguos de X días
        
        Args:
            dias: Número de días de antigüedad
        """
        from datetime import timedelta
        
        LoggerBitacora._crear_directorio()
        fecha_limite = datetime.now() - timedelta(days=dias)
        
        for archivo in LoggerBitacora.LOGS_DIR.glob("*.log"):
            try:
                timestamp = datetime.fromtimestamp(os.path.getmtime(archivo))
                if timestamp < fecha_limite:
                    archivo.unlink()
                    LoggerBitacora.obtener_logger_general().info(
                        f"Log antiguo eliminado: {archivo.name}"
                    )
            except Exception as e:
                LoggerBitacora.obtener_logger_errores().error(
                    f"Error al limpiar logs: {str(e)}"
                )