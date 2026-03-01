from fastmcp import FastMCP
from anonymize import Anonymizer
from pipeline import ProcessingPipeline
from ingestors import CSVIngestor, JSONIngestor
import os

# 1. Inicializamos el servidor MCP
mcp = FastMCP("DataShield-Anonymizer")

# 2. Configuramos la lógica basada en tus archivos
def get_anonymizer():
    # Aquí puedes cargar tus métricas personalizadas si quieres
    return Anonymizer()

@mcp.tool()
def anonymize_text(text: str) -> str:
    """
    Anonimiza información sensible (PII) de un texto plano.
    Útil para limpiar mensajes antes de procesarlos.
    """
    anonymizer = get_anonymizer()
    # Usamos tu lógica de hashing/reemplazo
    return anonymizer.anonymize_data(text)

@mcp.tool()
def process_file_securely(file_path: str) -> str:
    """
    Carga un archivo CSV o JSON, anonimiza todas las columnas 
    sensibles y devuelve un resumen del proceso.
    """
    if not os.path.exists(file_path):
        return "Error: Archivo no encontrado."

    # Detectar tipo de ingestor según tu lógica en ingestors.py
    if file_path.endswith('.csv'):
        ingestor = CSVIngestor(file_path)
    elif file_path.endswith('.json'):
        ingestor = JSONIngestor(file_path)
    else:
        return "Formato no soportado. Usa CSV o JSON."

    # Usamos tu Pipeline
    anonymizer = get_anonymizer()
    pipeline = ProcessingPipeline(ingestor, anonymizer)
    
    # Ejecutamos tu lógica
    results = pipeline.run()
    
    return f"Proceso completado. Se han anonimizado los datos en: {file_path}"

if __name__ == "__main__":
    mcp.run()
