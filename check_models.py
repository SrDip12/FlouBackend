import os
import sys
from dotenv import load_dotenv
from google import genai

# Cargar variables de entorno
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    # Intenta leerlo directamente si dotenv falla
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.strip().split('=')[1]
                    break
    except:
        pass

if not api_key:
    with open('model_check_output.txt', 'w') as f:
        f.write("❌ ERROR: No se encontró GEMINI_API_KEY")
    sys.exit(1)

with open('model_check_output.txt', 'w', encoding='utf-8') as f:
    f.write(f"Usando API Key: {api_key[:5]}...{api_key[-4:]}\n")
    try:
        client = genai.Client(api_key=api_key)

        f.write("\n--- 🔍 Modelos Detectados ---\n")
        found = False
        for m in client.models.list():
            # Intentamos obtener los métodos soportados
            methods = getattr(m, 'supported_generation_methods', [])
            if not methods:
                methods = getattr(m, 'supported_actions', [])
            
            if 'embedContent' in methods:
                found = True
                version = getattr(m, 'version', 'N/A')
                f.write(f"✅ ID: {m.name}\n")
                f.write(f"   Versión: {version}\n")
                f.write(f"   Métodos: {methods}\n")
                f.write("-" * 30 + "\n")

        if not found:
             f.write("⚠️ No se encontraron modelos con embedContent.\n")

    except Exception as e:
         f.write(f"\n❌ ERROR AL LISTAR MODELOS: {e}\n")
