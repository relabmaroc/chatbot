
import asyncio
import os
import sys
from models.database import init_db, SessionLocal
from services.chat_service import chat_service
from models.schemas import ChatRequest
import logging

# Set offline mode for local testing
os.environ["OFFLINE_MODE"] = "1"
# Disable noisy logs
logging.getLogger("services.chat_service").setLevel(logging.WARNING)

async def interactive_chat():
    init_db()
    db = SessionLocal()
    conversation_id = f"test_{os.urandom(4).hex()}"
    
    print("\n--- 🤖 Relab Chatbot Test Interface ---")
    print("Tapez 'exit' pour quitter.")
    print(f"Session ID: {conversation_id}\n")
    
    while True:
        user_input = input("Vous: ")
        if user_input.lower() in ("exit", "quit"):
            break
            
        request = ChatRequest(
            message=user_input,
            conversation_id=conversation_id,
            channel="terminal",
            user_id="tester"
        )
        
        try:
            response = await chat_service.process_message(request, db)
            print(f"Bot: {response.message}\n")
        except Exception as e:
            print(f"Erreur: {e}\n")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Erreur: OPENAI_API_KEY non configurée. Utilisez 'export OPENAI_API_KEY=votre_cle'")
        sys.exit(1)
        
    asyncio.run(interactive_chat())
