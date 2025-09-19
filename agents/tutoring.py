from langchain_huggingface import HuggingFaceEmbeddings
from supabase import create_client
import requests

# 🔹 Config Supabase
SUPABASE_URL = "http://127.0.0.1:54321"
SUPABASE_KEY = ""  # ⚠ utiliser clé Service Role côté backend uniquement
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🔹 Charger le modèle 512 dimensions
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/clip-ViT-B-32-multilingual-v1"
)

# 🔹 Fonction génération avec Mistral local
def generate_with_mistral(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False
        }
    )
    return response.json()["response"]

# 🔹 Fonction de réponse via Supabase
def answer_tutoring(question, k=3):
    # 1️⃣ Encoder la question en vecteur 512D
    q_vec = embeddings.embed_query(question)

    # 2️⃣ Recherche dans Supabase
    # Si tu as une colonne 'embedding' de type `vector(512)`
    results = supabase.rpc(
        "match_documents_tutoring",  # ta fonction SQL de recherche vectorielle
        {
            "query_embedding": q_vec,
            "match_count": k
        }
    ).execute()

    matches = results.data
    if not matches:
        return "Je n’ai pas trouvé de réponse pertinente."

    # 3️⃣ Construire le contexte
    context = "\n".join([m["content"] for m in matches if m.get("content")])

    # 4️⃣ Prompt vers Mistral
    prompt = f"""Tu es un assistant de formation.
Utilise les éléments suivants pour répondre à la question :
{context}

Question : {question}

Réponds de façon claire, professionnelle et utile."""
    return generate_with_mistral(prompt)


