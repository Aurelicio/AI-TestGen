import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Inicializa o cliente novo
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

try:
    print("Listando modelos disponíveis para sua chave...")
    # Isso vai nos dizer exatamente quais nomes o Google aceita para VOCÊ
    for model in client.models.list():
        methods = ", ".join(model.supported_actions)
        print(f"{model.name:<40} | {methods}")
except Exception as e:
    print(f"Erro ao listar: {e}")