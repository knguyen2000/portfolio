import os
import streamlit as st
from google import genai

# Only for local testing
api_key = None
try:
    if os.path.exists(".streamlit/secrets.toml"):
        import toml
        secrets = toml.load(".streamlit/secrets.toml")
        api_key = secrets.get("GOOGLE_API_KEY")
except Exception:
    pass

if not api_key:
    api_key = os.getenv("GOOGLE_API_KEY")

if api_key:
    client = genai.Client(api_key=api_key)
    print("--- AVAILABLE MODELS ---")
    for m in client.models.list():
        # Filter for relevant models (Gemini/Gemma)
        if "gemini" in m.name or "gemma" in m.name:
            print(f"- {m.name}")
else:
    print("No API Key found. Please check .streamlit/secrets.toml")
