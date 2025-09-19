import requests

def detect_intents(question: str) -> str:
    prompt = f"""
Tu es un classificateur d’intention pour un chatbot.

Tu dois lire la question suivante et répondre **seulement par un mot exact** :
- sales
- onboarding
- support

Si la question concerne plusieurs thèmes, choisis celui qui **semble prioritaire**.

Donne une seule réponse : sales, onboarding ou support.
Question : "{question}"
Réponse :
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral", "prompt": prompt, "stream": False}
    )

    intent = response.json()["response"].strip().lower()

    # pour éviter les erreurs de format
    if "sales" in intent:
      return "sales"
    elif "onboarding" in intent:
        return "onboarding"
    elif "support" in intent:
        return "support"
    else:
        return "unknown"

