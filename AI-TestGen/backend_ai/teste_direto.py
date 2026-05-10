import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

model = genai.GenerativeModel('gemini-1.5-flash')

try:
    response = model.generate_content("Oi!")
    print("O SDK oficial funcionou:", response.text)
except Exception as e:
    print("O SDK oficial também falhou:", e)