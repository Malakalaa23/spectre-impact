import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
url = "https://api.groq.com/openai/v1/models"

headers = {"Authorization": f"Bearer {api_key}"}

response = requests.get(url, headers=headers)
data = response.json()

print("Available models:")
for model in data.get("data", []):
    print(f"  - {model['id']}")