import os
from fastmcp import FastMCP
from anonymize import AllAnonym
from ingestors import PlainTextingestor
from sensitive_identification.name_identifiers import SpacyIdentifier
from sensitive_identification.regex_identification import RegexIdentifier

mcp = FastMCP("Global-Enterprise-Shield")

def get_engine(country="US"):
    # Mapeo de locales para Faker
    locales = {"US": "en_US", "CL": "es_CL", "MX": "es_MX", "ES": "es_ES"}
    target_locale = locales.get(country.upper(), "en_US")
    
    # Etiquetas que tu sistema identificará
    labels = ["PER", "LOC", "ORG", "EMAIL", "CREDIT_CARD", "RUT_CL", "IBAN"]
    
    # Cargamos tus modelos existentes
    ner = SpacyIdentifier("xx_ent_wiki_sm", labels)
    regex = RegexIdentifier("data/enterprise_regex.csv", labels)
    
    anon = AllAnonym()
    anon.faker = anon.faker.Faker(target_locale) # Inyección dinámica de país
    
    return ner, regex, anon

@mcp.tool()
def protect_content(text: str, country: str = "CL") -> str:
    """Anonimiza texto sensible (PII) usando estándares bancarios y legales del país elegido."""
    ner, regex, anon = get_engine(country)
    
    # Usamos tu PlainTextingestor para procesar la línea
    temp_name = "stream_process.txt"
    with open(temp_name, "w", encoding="utf-8") as f: f.write(text)
    
    ingestor = PlainTextingestor(temp_name)
    reg = ingestor.registries[0]
    
    regex.identify_sensitive(reg)
    ner.identify_sensitive(reg)
    ingestor.anonymize_registries(anon)
    
    result = ingestor.registries[0].text
    os.remove(temp_name)
    return result

if __name__ == "__main__":
    mcp.run()
