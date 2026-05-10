import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Pegamos a chave e garantimos que ela não está vazia
api_key = os.getenv("GOOGLE_API_KEY")

# Inicialização limpa
# Se o 404 persistir com 'gemini-1.5-flash', tentaremos 'models/gemini-1.5-flash'
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", 
    google_api_key=api_key,
    temperature=0
)

try:
    print("Iniciando chamada ao Gemini...")
    res = llm.invoke("Diga: Conexão estabelecida com sucesso!")
    print("\n--- RESPOSTA DO MODELO ---")
    print(res.content)
    print("--------------------------")
except Exception as e:
    print("\n--- ERRO CAPTURADO ---")
    print(f"Tipo do erro: {type(e).__name__}")
    print(f"Mensagem: {e}")