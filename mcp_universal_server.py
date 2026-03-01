import os
from fastmcp import FastMCP
from anonymize import AllAnonym
from ingestors import PlainTextingestor
from sensitive_identification.name_identifiers import SpacyIdentifier
from sensitive_identification.regex_identification import RegexIdentifier

# 1. Configuración del Servidor Multilingüe
mcp = FastMCP("Global-Privacy-Guard")

# Diccionario de modelos por idioma (puedes expandir esto)
# 'xx_ent_wiki_sm' es el modelo multilingüe de Spacy que ya tienes en tus requisitos
MODELS = {
    "es": "es_anonimization_core_lg",
    "en": "en_core_web_trf", 
    "multi": "xx_ent_wiki_sm"
}

def get_global_engine(country_code="es_CL"):
    """
    Crea un motor de anonimización adaptado al país.
    country_code ej: 'en_US', 'es_ES', 'fr_FR', 'pt_BR'
    """
    # Intentamos cargar el modelo específico, si no, usamos el multilingüe
    lang = country_code.split('_')[0]
    model_path = MODELS.get(lang, MODELS["multi"])
    
    labels = ["PER", "LOC", "ORG", "EMAIL", "PHONE", "ID_DOC"]
    
    ner_model = SpacyIdentifier(model_path, labels)
    # El RegexIdentifier se adapta según el archivo de definiciones que tengas
    regex_id = RegexIdentifier("data/regex_definition.csv", labels)
    
    # Aquí está la magia: AllAnonym usará el Faker del país solicitado
    anonymizer = AllAnonym()
    anonymizer.fake = anonymizer.faker.Faker(country_code) 
    
    return ner_model, regex_id, anonymizer

# 2. Herramienta: Anonimización de Texto con Selección de País
@mcp.tool()
def anonymize_text_global(text: str, country_code: str = "es_CL") -> str:
    """
    Anonimiza texto plano adaptándose a las convenciones del país especificado.
    Ejemplos de country_code: 'es_MX' (México), 'en_US' (EEUU), 'es_ES' (España).
    """
    ner, regex, anon = get_global_engine(country_code)
    
    # Creamos un registro temporal
    temp_file = "temp_global.txt"
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(text)
    
    ingestor = PlainTextingestor(temp_file)
    registry = ingestor.registries[0]
    
    # Proceso de identificación y reemplazo
    regex.identify_sensitive(registry)
    ner.identify_sensitive(registry)
    ingestor.anonymize_registries(anon)
    
    result = ingestor.registries[0].text
    os.remove(temp_file)
    return result

# 3. Herramienta: Procesamiento de Archivos por Lote
@mcp.tool()
def secure_file_vault(file_path: str, country_code: str = "es_CL") -> str:
    """
    Procesa un archivo completo y reemplaza datos reales por datos sintéticos 
    del país elegido. Soporta cumplimiento de privacidad global.
    """
    if not os.path.exists(file_path):
        return "Error: Archivo no encontrado."

    ner, regex, anon = get_global_engine(country_code)
    ingestor = PlainTextingestor(file_path)
    
    for reg in ingestor.registries:
        regex.identify_sensitive(reg)
        ner.identify_sensitive(reg)
    
    ingestor.anonymize_registries(anon)
    
    output_path = f"secured_{os.path.basename(file_path)}"
    ingestor.save(output_path)
    
    return f"Protección completada. Archivo listo para uso global en: {output_path}"
