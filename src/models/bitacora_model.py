"""
Modelo de datos para la Bitácora Geomecánica
Maneja toda la lógica de lectura/escritura de Excel
"""
import pandas as pd
import os
from datetime import datetime
from src.utils.config import (
    ARCHIVO_BITACORA, COLUMNAS_BITACORA, COLUMNAS_ESTANDAR
)

class BitacoraModel:
    """Gestiona la lógica de datos de la bitácora"""
    
    def __init__(self):
        self.archivo = ARCHIVO_BITACORA
        self.inicializar_excel()
    
    def inicializar_excel(self):
        """Crea el archivo Excel si no existe"""
        if not os.path.exists(self.archivo):
            bitacora = pd.DataFrame(columns=COLUMNAS_BITACORA)
            estandar = pd.DataFrame(columns=COLUMNAS_ESTANDAR)
            
            with pd.ExcelWriter(self.archivo) as writer:
                bitacora.to_excel(writer, sheet_name="Bitacora", index=False)
                estandar.to_excel(writer, sheet_name="Estandar_Sostenimiento", index=False)
    
    def guardar_registro(self, datos):
        """
        Guarda un nuevo registro en la bitácora
        
        Args:
            datos (dict): Diccionario con los datos del registro
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")
            df_nuevo = pd.DataFrame([datos])
            df = pd.concat([df, df_nuevo], ignore_index=True)
            
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl", 
                               if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Bitacora", index=False)
            
            return True, "Registro guardado exitosamente"
        except Exception as e:
            return False, f"Error al guardar: {str(e)}"
    
    def obtener_bitacora(self):
        """Obtiene todos los registros de la bitácora"""
        try:
            return pd.read_excel(self.archivo, sheet_name="Bitacora")
        except Exception as e:
            print(f"Error al leer bitácora: {str(e)}")
            return pd.DataFrame(columns=COLUMNAS_BITACORA)
    
    def obtener_labores_unicas(self):
        """Obtiene lista de labores únicas ordenadas"""
        try:
            df = self.obtener_bitacora()
            return sorted(df["Labor"].dropna().unique().tolist())
        except Exception:
            return []
    
    def filtrar_labores(self, texto):
        """
        Filtra labores que contengan el texto
        
        Args:
            texto (str): Texto a buscar
        
        Returns:
            list: Lista de labores que coinciden
        """
        labores = self.obtener_labores_unicas()
        texto_lower = texto.lower()
        return [l for l in labores if texto_lower in l.lower()][:5]
    
    def obtener_ultimo_registro_labor(self, labor):
        """
        Obtiene el último registro de una labor específica
        
        Args:
            labor (str): Nombre de la labor
        
        Returns:
            dict: Datos del último registro o None
        """
        try:
            df = self.obtener_bitacora()
            df_labor = df[df["Labor"] == labor]
            
            if df_labor.empty:
                return None
            
            return df_labor.iloc[-1].to_dict()
        except Exception:
            return None
    
    def obtener_estandar_sostenimiento(self):
        """Obtiene los estándares de sostenimiento"""
        try:
            return pd.read_excel(self.archivo, sheet_name="Estandar_Sostenimiento")
        except Exception:
            return pd.DataFrame(columns=COLUMNAS_ESTANDAR)
    
    def recomendar_soporte(self, rmr):
        """
        Recomienda soporte según el valor de RMR
        
        Args:
            rmr (int): Valor de Rock Mass Rating
        
        Returns:
            str: Recomendación de soporte o vacío
        """
        try:
            df = self.obtener_estandar_sostenimiento()
            
            for _, row in df.iterrows():
                rmr_min = int(row["RMR_min"])
                rmr_max = int(row["RMR_max"])
                
                if rmr_min <= rmr <= rmr_max:
                    return str(row["Soporte"])
            
            return ""
        except Exception:
            return ""
    
    def guardar_estandar_sostenimiento(self, datos):
        """
        Guarda los estándares de sostenimiento
        
        Args:
            datos (list): Lista de diccionarios con los estándares
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            df = pd.DataFrame(datos)
            
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                               if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Estandar_Sostenimiento", index=False)
            
            return True, "Estándar guardado correctamente"
        except Exception as e:
            return False, f"Error al guardar estándar: {str(e)}"
    
    def buscar_registros(self, labor="", fecha_inicio=None, fecha_fin=None):
        """
        Busca registros con filtros
        
        Args:
            labor (str): Filtro por labor
            fecha_inicio (str): Filtro fecha inicio (formato dd/mm/yyyy)
            fecha_fin (str): Filtro fecha fin (formato dd/mm/yyyy)
        
        Returns:
            DataFrame: Registros filtrados
        """
        try:
            df = self.obtener_bitacora()
            
            if df.empty:
                return df
            
            # Convertir fechas
            df["Fecha"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y")
            
            # Filtrar por labor
            if labor:
                df = df[df["Labor"].str.contains(labor, case=False, na=False)]
            
            # Filtrar por fechas
            if fecha_inicio and fecha_fin:
                inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
                fin = datetime.strptime(fecha_fin, "%d/%m/%Y")
                df = df[(df["Fecha"] >= inicio) & (df["Fecha"] <= fin)]
            
            # Convertir de vuelta a string
            df["Fecha"] = df["Fecha"].dt.strftime("%d/%m/%Y")
            
            return df
        except Exception as e:
            print(f"Error al buscar: {str(e)}")
            return pd.DataFrame(columns=COLUMNAS_BITACORA)