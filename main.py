from fastapi import FastAPI , Request
from agents.sales import answer_sales
from agents.helpdesk import answer_support
from agents.tutoring import answer_tutoring
from pydantic import BaseModel
from detect_intent import detect_intents
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


class ChatRequest(BaseModel):
    question: str


@app.post("/chat")  
async def route_chat(request: ChatRequest):
    
    question =request.question
    print(f"Question reçue : {question}")
    #  Détecter l’intention avec LLM
    intent = detect_intents(question)
    print(f"[Intent détectée] → {intent}")

    #  Rediriger vers l’agent approprié
    if intent == "sales":
        response = answer_sales(question)
    elif intent == "support":
        response = answer_support(question)
    elif intent == "onboarding":
        response = answer_tutoring(question)
    else:
        response = "Je n’ai pas compris votre demande. Pouvez-vous reformuler ?"

    return {"intent": intent, "response": response}



