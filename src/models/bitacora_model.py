"""
Modelo de datos para la Bitácora Geomecánica
Maneja toda la lógica de lectura/escritura de Excel
"""
import shutil
import pandas as pd
import os
from datetime import datetime
from utils.config import (
    ARCHIVO_BITACORA, COLUMNAS_BITACORA, COLUMNAS_ESTANDAR,
    COLUMNAS_LABORES, COLUMNAS_SOSTENIMIENTO, BACKUP_DIR
)

def _safe_concat(df_base: "pd.DataFrame", df_nuevo: "pd.DataFrame") -> "pd.DataFrame":
    """
    Concatena df_nuevo a df_base sin FutureWarning alineando columnas y dtypes.
    Maneja correctamente columnas con todos NA y columnas ausentes en alguno de los DataFrames.
    """
    if df_base.empty:
        return df_nuevo.copy()
    if df_nuevo.empty:
        return df_base.copy()

    # Alinear columnas: agregar columnas faltantes en cada DataFrame con pd.NA
    for col in df_nuevo.columns:
        if col not in df_base.columns:
            df_base = df_base.copy()
            df_base[col] = pd.NA
    for col in df_base.columns:
        if col not in df_nuevo.columns:
            df_nuevo = df_nuevo.copy()
            df_nuevo[col] = pd.NA

    # Forzar dtype object en columnas con todos NA para evitar FutureWarning
    df_nuevo = df_nuevo.copy()
    for col in df_nuevo.columns:
        if df_nuevo[col].isna().all():
            df_nuevo[col] = df_nuevo[col].astype(object)
    df_base = df_base.copy()
    for col in df_base.columns:
        if df_base[col].isna().all():
            df_base[col] = df_base[col].astype(object)

    return pd.concat([df_base, df_nuevo], ignore_index=True)


def _convertir_valor(valor, col_dtype) -> object:
    """
    Convierte un valor al dtype de la columna para asignación segura con df.at.
    Si falla, retorna el valor como string.

    Args:
        valor: Valor a convertir.
        col_dtype: dtype de la columna destino.

    Returns:
        Valor convertido o str del valor original.
    """
    try:
        if pd.api.types.is_integer_dtype(col_dtype):
            return int(valor) if str(valor).strip() not in ('', 'nan') else pd.NA
        elif pd.api.types.is_float_dtype(col_dtype):
            return float(valor) if str(valor).strip() not in ('', 'nan') else pd.NA
        else:
            return str(valor)
    except (ValueError, TypeError):
        return str(valor)


class BitacoraModel:
    """Gestiona la lógica de datos de la bitácora"""

    _UNDO_MAX = 5

    def __init__(self, archivo=None):
        self.archivo = archivo or ARCHIVO_BITACORA
        self._undo_stack: list = []
        self.inicializar_excel()
    
    def _hacer_backup(self):
        """
        Crea una copia de respaldo del archivo Excel en data/backups/.
        Si ya existe un backup del día, lo sobreescribe.
        Respeta el flag backup_automatico de la configuración.
        """
        try:
            from utils.config_manager import cargar_config
            config = cargar_config()
            if not config.get("backup_automatico", True):
                return
        except Exception:
            pass

        try:
            if not os.path.exists(self.archivo):
                return
            fecha_hoy = datetime.now().strftime("%Y-%m-%d")
            nombre_backup = BACKUP_DIR / f"bitacora_backup_{fecha_hoy}.xlsx"
            shutil.copy2(self.archivo, nombre_backup)
        except Exception as e:
            print(f"Advertencia: no se pudo crear backup: {str(e)}")

    def inicializar_excel(self):
        """Crea el archivo Excel si no existe; añade hojas/columnas faltantes si ya existe."""
        if not os.path.exists(self.archivo):
            bitacora = pd.DataFrame(columns=COLUMNAS_BITACORA)
            estandar = pd.DataFrame(columns=["RMR_min", "RMR_max", "Tipo", "Soporte"])
            labores = pd.DataFrame(columns=COLUMNAS_LABORES)
            cols_sost = self._columnas_sostenimiento_actuales()
            sostenimiento = pd.DataFrame(columns=cols_sost)

            with pd.ExcelWriter(self.archivo) as writer:
                bitacora.to_excel(writer, sheet_name="Bitacora", index=False)
                estandar.to_excel(writer, sheet_name="Estandar_Sostenimiento", index=False)
                labores.to_excel(writer, sheet_name="Labores", index=False)
                sostenimiento.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
        else:
            try:
                import openpyxl
                wb = openpyxl.load_workbook(self.archivo)
                sheetnames = wb.sheetnames
                wb.close()

                # ── Sostenimiento_Diario ──────────────────────────────────────
                if "Sostenimiento_Diario" not in sheetnames:
                    cols_sost = self._columnas_sostenimiento_actuales()
                    sostenimiento = pd.DataFrame(columns=cols_sost)
                    with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl") as writer:
                        sostenimiento.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
                else:
                    try:
                        df_sost = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
                        cols_sost = self._columnas_sostenimiento_actuales()
                        modified = False
                        for col in cols_sost:
                            if col not in df_sost.columns:
                                df_sost[col] = "" if col in ("Observaciones", "Tipo_Shotcrete") else 0
                                modified = True
                        # Añadir Tipo_Shotcrete si falta (retrocompatibilidad)
                        if "Tipo_Shotcrete" not in df_sost.columns:
                            df_sost["Tipo_Shotcrete"] = ""
                            modified = True
                        if modified:
                            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                                if_sheet_exists="replace") as writer:
                                df_sost.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
                    except Exception:
                        pass

                # ── Labores ───────────────────────────────────────────────────
                if "Labores" in sheetnames:
                    try:
                        df_lab = pd.read_excel(self.archivo, sheet_name="Labores")
                        lab_modified = False
                        for col in ("Fase", "Clasificacion_KPI"):
                            if col not in df_lab.columns:
                                df_lab[col] = ""
                                lab_modified = True
                        if lab_modified:
                            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                                if_sheet_exists="replace") as writer:
                                df_lab.to_excel(writer, sheet_name="Labores", index=False)
                    except Exception:
                        pass
            except Exception:
                pass

    def _columnas_sostenimiento_actuales(self) -> list:
        """Retorna la lista completa de columnas de Sostenimiento_Diario (base + activas)."""
        base = ["Fecha", "Turno", "Labor"]
        activos = self._columnas_sostenimiento_activas()
        fin = ["Observaciones"]
        # Columnas base de config + activas sin duplicar
        cols = base[:]
        for col in COLUMNAS_SOSTENIMIENTO:
            if col not in base and col not in fin and col not in cols:
                cols.append(col)
        for col in activos:
            if col not in cols and col not in fin:
                cols.append(col)
        cols += fin
        return cols

    def _columnas_sostenimiento_activas(self) -> list:
        """Retorna las columnas numéricas activas de sostenimiento desde config."""
        try:
            from utils.config_manager import cargar_config
            config = cargar_config()
            activos = config.get("sostenimientos_activos", [])
            return [s["columna"] for s in activos if isinstance(s, dict) and "columna" in s]
        except Exception:
            return [
                "Shotcrete_m3", "Pernos_Helicoidales", "Splitsets",
                "Mesh_Strap", "Cable_Bolting", "Marco_Acero"
            ]
    
    def _guardar_snapshot(self, sheet: str = "Bitacora"):
        """Guarda un snapshot del DataFrame en el stack de deshacer (máx 5)."""
        try:
            df = pd.read_excel(self.archivo, sheet_name=sheet)
            if len(self._undo_stack) >= self._UNDO_MAX:
                self._undo_stack.pop(0)
            self._undo_stack.append({"sheet": sheet, "data": df.to_dict(orient="list")})
        except Exception:
            pass

    def deshacer_ultima_accion(self) -> tuple:
        """
        Restaura el último snapshot del stack de deshacer.

        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        if not self._undo_stack:
            return False, "No hay acciones para deshacer"
        snapshot = self._undo_stack.pop()
        try:
            df = pd.DataFrame(snapshot["data"])
            sheet = snapshot["sheet"]
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=sheet, index=False)
            return True, "Última acción deshecha correctamente"
        except Exception as e:
            return False, f"Error al deshacer: {str(e)}"

    def guardar_registro(self, datos):
        """
        Guarda un nuevo registro en la bitácora.
        Verifica duplicados por (Fecha, Turno, Labor) antes de guardar.
        
        Args:
            datos (dict): Diccionario con los datos del registro
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")

            # Verificar duplicado
            mascara = (
                (df["Fecha"].astype(str) == str(datos.get("Fecha", ""))) &
                (df["Turno"].astype(str) == str(datos.get("Turno", ""))) &
                (df["Labor"].astype(str) == str(datos.get("Labor", "")))
            )
            if mascara.any():
                return False, "DUPLICADO: Ya existe un registro para esta labor en este turno y fecha."

            self._hacer_backup()
            self._guardar_snapshot("Bitacora")
            df_nuevo = pd.DataFrame([datos])
            df = _safe_concat(df, df_nuevo)
            
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl", 
                               if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Bitacora", index=False)
            
            return True, "Registro guardado exitosamente"
        except Exception as e:
            return False, f"Error al guardar: {str(e)}"

    def guardar_registro_forzado(self, datos):
        """
        Guarda un registro omitiendo la verificación de duplicados.
        Usar cuando el usuario confirma sobreescribir un duplicado.
        
        Args:
            datos (dict): Diccionario con los datos del registro
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Bitacora")
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")
            df_nuevo = pd.DataFrame([datos])
            df = _safe_concat(df, df_nuevo)
            
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
    
    def obtener_labores_guardadas(self):
        """Obtiene la lista de nombres de labores guardadas"""
        try:
            df = self._leer_labores_df()
            return sorted(df["Labor"].dropna().unique().tolist())
        except Exception:
            return []

    def _leer_labores_df(self):
        """Lee el DataFrame completo de la hoja Labores"""
        try:
            return pd.read_excel(self.archivo, sheet_name="Labores")
        except Exception:
            return pd.DataFrame(columns=COLUMNAS_LABORES)

    def agregar_labor(self, nombre_labor, gsi="", rmr="", soporte="", tipo="Temporal",
                      fase="", clasificacion_kpi=""):
        """
        Agrega una nueva labor a la hoja Labores con sus datos técnicos.
        Returns: tuple (éxito: bool, mensaje: str)
        """
        try:
            nombre_labor = nombre_labor.strip()
            if not nombre_labor:
                return False, "El nombre de la labor no puede estar vacío"

            df = self._leer_labores_df()
            if nombre_labor in df["Labor"].values:
                return False, f"La labor '{nombre_labor}' ya existe"

            self._hacer_backup()
            nueva_fila = pd.DataFrame([{
                "Labor": nombre_labor,
                "GSI": gsi,
                "RMR": rmr,
                "Soporte": soporte,
                "Tipo": tipo,
                "Fase": fase,
                "Clasificacion_KPI": clasificacion_kpi,
            }])
            df = _safe_concat(df, nueva_fila)
            df = df.sort_values("Labor").reset_index(drop=True)

            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                               if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Labores", index=False)

            return True, f"Labor '{nombre_labor}' agregada correctamente"
        except Exception as e:
            return False, f"Error al agregar labor: {str(e)}"

    def eliminar_labor(self, nombre_labor):
        """
        Elimina una labor de la hoja Labores.
        Returns: tuple (éxito: bool, mensaje: str)
        """
        try:
            df = self._leer_labores_df()
            if nombre_labor not in df["Labor"].values:
                return False, f"La labor '{nombre_labor}' no existe"

            self._hacer_backup()
            df = df[df["Labor"] != nombre_labor].reset_index(drop=True)

            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                               if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Labores", index=False)

            return True, f"Labor '{nombre_labor}' eliminada correctamente"
        except Exception as e:
            return False, f"Error al eliminar labor: {str(e)}"

    def obtener_datos_labor(self, nombre_labor):
        """
        Obtiene los datos técnicos de una labor del catálogo.
        Returns: dict con GSI, RMR, Soporte, Tipo o None
        """
        try:
            df = self._leer_labores_df()
            fila = df[df["Labor"] == nombre_labor]
            if fila.empty:
                return None
            return fila.iloc[0].to_dict()
        except Exception:
            return None

    def obtener_labores_unicas(self):
        """
        Mantiene compatibilidad: ahora retorna las labores guardadas
        en la hoja 'Labores' en lugar de las únicas de la bitácora.
        """
        return self.obtener_labores_guardadas()
    
    def filtrar_labores(self, texto):
        """
        Filtra labores guardadas que contengan el texto.
        IMPORTANTE: Ahora usa la hoja 'Labores' en lugar de la bitácora.
        """
        labores = self.obtener_labores_guardadas()
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
    
    def recomendar_soporte(self, rmr, tipo="Temporal"):
        """
        Recomienda soporte según el valor de RMR y el tipo de labor.

        Args:
            rmr (int): Valor de Rock Mass Rating
            tipo (str): Tipo de labor ("Temporal" o "Permanente")

        Returns:
            str: Recomendación de soporte o vacío
        """
        try:
            df = self.obtener_estandar_sostenimiento()

            # Filtrar por tipo si la columna existe
            if "Tipo" in df.columns:
                df_tipo = df[df["Tipo"] == tipo]
                # Si no hay filas para ese tipo, usar todas (retrocompatibilidad)
                if df_tipo.empty:
                    df_tipo = df
            else:
                df_tipo = df

            for _, row in df_tipo.iterrows():
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
            self._hacer_backup()
            cols = ["RMR_min", "RMR_max", "Tipo", "Soporte"]
            if datos:
                df = pd.DataFrame(datos)
                # Ensure column order and add missing columns with empty values
                for col in cols:
                    if col not in df.columns:
                        df[col] = ""
                df = df[cols]
            else:
                df = pd.DataFrame(columns=cols)
            
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

    def editar_registro(self, indice: int, datos: dict) -> tuple:
        """
        Edita un registro de la bitácora por su índice (0-based).
        
        Args:
            indice: Índice de la fila en el DataFrame
            datos: Diccionario con los nuevos datos (solo los campos a modificar)
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Bitacora")
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")
            if indice < 0 or indice >= len(df):
                return False, "Índice fuera de rango"
            for campo, valor in datos.items():
                if campo in df.columns:
                    valor_conv = _convertir_valor(valor, df[campo].dtype)
                    df[campo] = df[campo].astype(object)
                    df.at[indice, campo] = valor_conv
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Bitacora", index=False)
            return True, "Registro editado correctamente"
        except Exception as e:
            return False, f"Error al editar: {str(e)}"

    def eliminar_registro(self, indice: int) -> tuple:
        """
        Elimina un registro de la bitácora por su índice (0-based).
        
        Args:
            indice: Índice de la fila en el DataFrame
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Bitacora")
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")
            if indice < 0 or indice >= len(df):
                return False, "Índice fuera de rango"
            df = df.drop(index=indice).reset_index(drop=True)
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Bitacora", index=False)
            return True, "Registro eliminado correctamente"
        except Exception as e:
            return False, f"Error al eliminar: {str(e)}"

    def exportar_historial_excel(self, df, nombre_archivo):
        """
        Exporta un DataFrame a un archivo Excel.
        
        Args:
            df: DataFrame a exportar
            nombre_archivo: Nombre/ruta del archivo destino
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            df.to_excel(nombre_archivo, index=False)
            return True, f"Archivo exportado: {nombre_archivo}"
        except Exception as e:
            return False, f"Error al exportar: {str(e)}"

    # ── Sostenimiento Diario ─────────────────────────────────────────────────

    def guardar_sostenimiento(self, datos: dict) -> tuple:
        """
        Guarda un registro de sostenimiento diario.
        Verifica duplicado por (Fecha, Turno, Labor); si existe retorna
        (False, 'DUPLICADO') para que la UI gestione la confirmación.
        
        Args:
            datos: Diccionario con los campos de COLUMNAS_SOSTENIMIENTO
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")

            # Verificar duplicado
            mascara = (
                (df["Fecha"].astype(str) == str(datos.get("Fecha", ""))) &
                (df["Turno"].astype(str) == str(datos.get("Turno", ""))) &
                (df["Labor"].astype(str) == str(datos.get("Labor", "")))
            )
            if mascara.any():
                return False, "DUPLICADO"

            self._hacer_backup()
            self._guardar_snapshot("Sostenimiento_Diario")
            df_nuevo = pd.DataFrame([datos])
            df = _safe_concat(df, df_nuevo)
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
            return True, "Sostenimiento guardado correctamente"
        except Exception as e:
            return False, f"Error al guardar sostenimiento: {str(e)}"

    def guardar_sostenimiento_forzado(self, datos: dict) -> tuple:
        """
        Guarda un registro de sostenimiento omitiendo la verificación de duplicados.
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Sostenimiento_Diario")
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
            df_nuevo = pd.DataFrame([datos])
            df = _safe_concat(df, df_nuevo)
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
            return True, "Sostenimiento guardado correctamente"
        except Exception as e:
            return False, f"Error al guardar sostenimiento: {str(e)}"

    def obtener_sostenimiento(self, fecha=None, labor=None) -> "pd.DataFrame":
        """
        Retorna registros de sostenimiento diario, opcionalmente filtrados.
        
        Args:
            fecha: Filtrar por fecha exacta (string dd/mm/yyyy)
            labor: Filtrar por nombre de labor (substring)
        
        Returns:
            DataFrame con los registros
        """
        try:
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
            if fecha:
                df = df[df["Fecha"].astype(str) == str(fecha)]
            if labor:
                df = df[df["Labor"].astype(str).str.contains(labor, case=False, na=False)]
            return df
        except Exception:
            return pd.DataFrame(columns=COLUMNAS_SOSTENIMIENTO)

    def editar_sostenimiento(self, indice: int, datos: dict) -> tuple:
        """
        Edita un registro de sostenimiento por índice (0-based).
        
        Args:
            indice: Índice de la fila
            datos: Campos a actualizar
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Sostenimiento_Diario")
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
            if indice < 0 or indice >= len(df):
                return False, "Índice fuera de rango"
            for campo, valor in datos.items():
                if campo in df.columns:
                    valor_conv = _convertir_valor(valor, df[campo].dtype)
                    df[campo] = df[campo].astype(object)
                    df.at[indice, campo] = valor_conv
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
            return True, "Sostenimiento editado correctamente"
        except Exception as e:
            return False, f"Error al editar sostenimiento: {str(e)}"

    def eliminar_sostenimiento(self, indice: int) -> tuple:
        """
        Elimina un registro de sostenimiento por índice (0-based).
        
        Args:
            indice: Índice de la fila
        
        Returns:
            tuple: (éxito: bool, mensaje: str)
        """
        try:
            self._hacer_backup()
            self._guardar_snapshot("Sostenimiento_Diario")
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
            if indice < 0 or indice >= len(df):
                return False, "Índice fuera de rango"
            df = df.drop(index=indice).reset_index(drop=True)
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name="Sostenimiento_Diario", index=False)
            return True, "Registro de sostenimiento eliminado"
        except Exception as e:
            return False, f"Error al eliminar sostenimiento: {str(e)}"

    def obtener_totales_sostenimiento(self, fecha_inicio=None, fecha_fin=None,
                                      labor=None) -> "pd.DataFrame":
        """
        Agrupa y suma los totales de cada elemento de sostenimiento por labor.
        
        Args:
            fecha_inicio: Fecha mínima (string dd/mm/yyyy)
            fecha_fin: Fecha máxima (string dd/mm/yyyy)
            labor: Filtrar por labor específica
        
        Returns:
            DataFrame agrupado por Labor con sumas de cada elemento
        """
        try:
            df = pd.read_excel(self.archivo, sheet_name="Sostenimiento_Diario")
            if df.empty:
                return df

            # Usar columnas activas dinámicamente
            cols_num = self._columnas_sostenimiento_activas()
            # Incluir también las columnas fijas de la hoja aunque no estén en activas
            for col in COLUMNAS_SOSTENIMIENTO:
                if col not in ("Fecha", "Turno", "Labor", "Observaciones") and col not in cols_num:
                    cols_num.append(col)

            for col in cols_num:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            if "Fecha" in df.columns:
                df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
                if fecha_inicio:
                    inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
                    df = df[df["Fecha_dt"] >= inicio]
                if fecha_fin:
                    fin = datetime.strptime(fecha_fin, "%d/%m/%Y")
                    df = df[df["Fecha_dt"] <= fin]

            if labor:
                df = df[df["Labor"].astype(str).str.contains(labor, case=False, na=False)]

            cols_agrupar = [c for c in cols_num if c in df.columns]
            if "Labor" not in df.columns or not cols_agrupar:
                return pd.DataFrame()

            return df.groupby("Labor")[cols_agrupar].sum().reset_index()
        except Exception as e:
            print(f"Error al obtener totales: {str(e)}")
            return pd.DataFrame()

    def archivar_periodo(self, fecha_inicio: str, fecha_fin: str) -> tuple:
        """
        Mueve registros de un rango de fechas al archivo histórico anual y los elimina del
        archivo principal.

        Args:
            fecha_inicio: Fecha inicio en formato dd/mm/yyyy
            fecha_fin: Fecha fin en formato dd/mm/yyyy

        Returns:
            tuple: (éxito: bool, mensaje: str, cantidad: int)
        """
        from utils.config import DATA_DIR
        try:
            df = pd.read_excel(self.archivo, sheet_name="Bitacora")
            if df.empty:
                return False, "No hay registros en la bitácora", 0

            df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
            inicio = datetime.strptime(fecha_inicio, "%d/%m/%Y")
            fin = datetime.strptime(fecha_fin, "%d/%m/%Y")

            mask_arch = (df["Fecha_dt"] >= inicio) & (df["Fecha_dt"] <= fin)
            df_archivar = df[mask_arch].drop(columns=["Fecha_dt"])
            df_restante = df[~mask_arch].drop(columns=["Fecha_dt"]).reset_index(drop=True)

            if df_archivar.empty:
                return False, "No hay registros en ese período", 0

            anio = inicio.year
            archivo_hist = DATA_DIR / f"historico_{anio}.xlsx"

            if archivo_hist.exists():
                df_hist_existente = pd.read_excel(archivo_hist, sheet_name="Bitacora")
                df_hist_final = _safe_concat(df_hist_existente, df_archivar)
            else:
                df_hist_final = df_archivar

            with pd.ExcelWriter(str(archivo_hist), engine="openpyxl") as writer:
                df_hist_final.to_excel(writer, sheet_name="Bitacora", index=False)

            # Guardar el archivo principal sin los registros archivados
            self._hacer_backup()
            with pd.ExcelWriter(self.archivo, mode="a", engine="openpyxl",
                                if_sheet_exists="replace") as writer:
                df_restante.to_excel(writer, sheet_name="Bitacora", index=False)

            cantidad = len(df_archivar)
            return True, (f"{cantidad} registro(s) archivado(s) en '{archivo_hist.name}'"), cantidad
        except Exception as e:
            return False, f"Error al archivar: {str(e)}", 0