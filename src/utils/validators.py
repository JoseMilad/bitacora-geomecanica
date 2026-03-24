"""
Validadores para la Bitácora Geomecánica
"""
from datetime import datetime
from typing import Tuple, Dict, Any


class ValidadorBitacora:
    """Clase con métodos de validación para la bitácora"""
    
    # Rangos válidos
    GSI_MIN = 0
    GSI_MAX = 100
    RMR_MIN = 0
    RMR_MAX = 100
    
    @staticmethod
    def validar_turno(turno: str) -> Tuple[bool, str]:
        """
        Valida que el turno sea válido
        
        Args:
            turno: Turno ingresado
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if not turno or turno.strip() == "":
            return False, "El turno es obligatorio"
        
        turnos_validos = ["Mañana", "Tarde", "Noche"]
        if turno not in turnos_validos:
            return False, f"Turno inválido. Debe ser: {', '.join(turnos_validos)}"
        
        return True, "OK"
    
    @staticmethod
    def validar_labor(labor: str) -> Tuple[bool, str]:
        """
        Valida que la labor sea válida
        
        Args:
            labor: Labor ingresada
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if not labor or labor.strip() == "":
            return False, "La labor es obligatoria"
        
        if len(labor.strip()) < 3:
            return False, "La labor debe tener al menos 3 caracteres"
        
        if len(labor.strip()) > 100:
            return False, "La labor no puede exceder 100 caracteres"
        
        # Validar caracteres permitidos
        caracteres_invalidos = ["<", ">", "{", "}", "|", "\\", "^", "`"]
        for char in caracteres_invalidos:
            if char in labor:
                return False, f"La labor contiene caracteres no permitidos: {char}"
        
        return True, "OK"
    
    @staticmethod
    def validar_gsi(gsi: str) -> Tuple[bool, str]:
        """
        Valida el GSI (Geological Strength Index)
        
        Args:
            gsi: Valor de GSI ingresado
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if gsi.strip() == "":
            return True, "OK"  # GSI es opcional
        
        try:
            gsi_num = float(gsi)
        except ValueError:
            return False, "GSI debe ser un número"
        
        if gsi_num < ValidadorBitacora.GSI_MIN or gsi_num > ValidadorBitacora.GSI_MAX:
            return False, f"GSI debe estar entre {ValidadorBitacora.GSI_MIN} y {ValidadorBitacora.GSI_MAX}"
        
        return True, "OK"
    
    @staticmethod
    def validar_rmr(rmr: str) -> Tuple[bool, str]:
        """
        Valida el RMR (Rock Mass Rating)
        
        Args:
            rmr: Valor de RMR ingresado
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if rmr.strip() == "":
            return True, "OK"  # RMR es opcional
        
        try:
            rmr_num = float(rmr)
        except ValueError:
            return False, "RMR debe ser un número"
        
        if rmr_num < ValidadorBitacora.RMR_MIN or rmr_num > ValidadorBitacora.RMR_MAX:
            return False, f"RMR debe estar entre {ValidadorBitacora.RMR_MIN} y {ValidadorBitacora.RMR_MAX}"
        
        return True, "OK"
    
    @staticmethod
    def validar_soporte(soporte: str) -> Tuple[bool, str]:
        """
        Valida el tipo de soporte
        
        Args:
            soporte: Tipo de soporte
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if soporte.strip() == "":
            return True, "OK"  # Soporte es opcional
        
        if len(soporte.strip()) > 200:
            return False, "El soporte no puede exceder 200 caracteres"
        
        return True, "OK"
    
    @staticmethod
    def validar_observaciones(observaciones: str) -> Tuple[bool, str]:
        """
        Valida las observaciones
        
        Args:
            observaciones: Texto de observaciones
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        if observaciones.strip() == "":
            return True, "OK"  # Observaciones es opcional
        
        if len(observaciones.strip()) > 1000:
            return False, "Las observaciones no pueden exceder 1000 caracteres"
        
        return True, "OK"
    
    @staticmethod
    def validar_registro_completo(datos: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Valida un registro completo antes de guardarlo
        
        Args:
            datos: Diccionario con todos los datos del registro
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        # Validar turno
        valido, msg = ValidadorBitacora.validar_turno(datos.get("Turno", ""))
        if not valido:
            return False, msg
        
        # Validar labor
        valido, msg = ValidadorBitacora.validar_labor(datos.get("Labor", ""))
        if not valido:
            return False, msg
        
        # Validar GSI
        valido, msg = ValidadorBitacora.validar_gsi(datos.get("GSI", ""))
        if not valido:
            return False, msg
        
        # Validar RMR
        valido, msg = ValidadorBitacora.validar_rmr(datos.get("RMR", ""))
        if not valido:
            return False, msg
        
        # Validar soporte
        valido, msg = ValidadorBitacora.validar_soporte(datos.get("Soporte", ""))
        if not valido:
            return False, msg
        
        # Validar observaciones
        valido, msg = ValidadorBitacora.validar_observaciones(datos.get("Observaciones", ""))
        if not valido:
            return False, msg
        
        return True, "Registro válido"
    
    @staticmethod
    def sanitizar_entrada(texto: str) -> str:
        """
        Sanitiza una entrada de texto
        
        Args:
            texto: Texto a sanitizar
            
        Returns:
            Texto sanitizado
        """
        # Remover espacios al inicio y final
        texto = texto.strip()
        
        # Reemplazar múltiples espacios por uno solo
        while "  " in texto:
            texto = texto.replace("  ", " ")
        
        return texto
    
    @staticmethod
    def validar_fecha(fecha: str) -> Tuple[bool, str]:
        """
        Valida que una fecha sea válida
        
        Args:
            fecha: Fecha en formato DD-MM-YYYY
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        try:
            datetime.strptime(fecha, "%d-%m-%Y")
            return True, "OK"
        except ValueError:
            return False, "Fecha inválida. Formato esperado: DD-MM-YYYY"
    
    @staticmethod
    def validar_rango_fechas(fecha_inicio: str, fecha_fin: str) -> Tuple[bool, str]:
        """
        Valida que fecha_inicio sea menor que fecha_fin
        
        Args:
            fecha_inicio: Fecha inicial en formato DD-MM-YYYY
            fecha_fin: Fecha final en formato DD-MM-YYYY
            
        Returns:
            Tupla (es_valido, mensaje)
        """
        try:
            d_inicio = datetime.strptime(fecha_inicio, "%d-%m-%Y")
            d_fin = datetime.strptime(fecha_fin, "%d-%m-%Y")
            
            if d_inicio > d_fin:
                return False, "La fecha inicial debe ser menor que la fecha final"
            
            return True, "OK"
        except ValueError:
            return False, "Formato de fecha inválido"
    
    @staticmethod
    def obtener_calidad_macizo(rmr: float) -> str:
        """
        Obtiene la calidad del macizo rocoso según RMR
        
        Args:
            rmr: Valor de RMR
            
        Returns:
            Clasificación de calidad
        """
        if rmr >= 81:
            return "Excelente"
        elif rmr >= 61:
            return "Bueno"
        elif rmr >= 41:
            return "Regular"
        elif rmr >= 21:
            return "Pobre"
        else:
            return "Muy Pobre"
    
    @staticmethod
    def obtener_clase_gsi(gsi: float) -> str:
        """
        Obtiene la clase de GSI
        
        Args:
            gsi: Valor de GSI
            
        Returns:
            Clasificación de GSI
        """
        if gsi >= 75:
            return "I - Excelente"
        elif gsi >= 55:
            return "II - Bueno"
        elif gsi >= 35:
            return "III - Regular"
        elif gsi >= 15:
            return "IV - Pobre"
        else:
            return "V - Muy Pobre"