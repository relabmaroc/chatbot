
import asyncio
from models.database import SessionLocal, init_db, Conversation, Contact, Message
from models.schemas import ChatRequest, IntentType, Language, ConversationStatus
from services.chat_service import chat_service
from logic.flow_manager import FlowAction, FlowStep
import uuid

async def verify_robustness_v2():
    print("\n🚀 Starting Robustness Verification V2...")
    init_db()
    db = SessionLocal()
    
    unique_id = str(uuid.uuid4())[:8]
    user_id = f"test_user_{unique_id}"
    incoming_conv_id = None # Let the service create it

    async def get_response(msg, cid, uid):
        req = ChatRequest(message=msg, conversation_id=cid, identifier=uid, channel="web")
        return await chat_service.process_message(req, db)

    print("\n--- Scenario 1: Greeting 'Bonjour' (No Handoff) ---")
    res1 = await get_response("Bonjour", incoming_conv_id, user_id)
    real_conv_id = res1.conversation_id
    print(f"Bot: {res1.message[:50]}...")
    print(f"Should Handoff? {res1.should_handoff}")
    assert res1.should_handoff is False, "❌ Failed: Greeting should not trigger handoff"

    print("\n--- Scenario 2: Selection Lock ('celui à 7 590 dhs') ---")
    print("User: 'Je veux un iPhone 13'")
    await get_response("Je veux un iPhone 13", real_conv_id, user_id)
    
    # Inject mock variants into the session so that explicit selection has something to work with
    # In a real scenario, the bot would have searched the inventory.
    # We refresh the object from DB to ensure it's up to date.
    db.expire_all()
    conv = db.query(Conversation).filter(Conversation.id == real_conv_id).first()
    
    # Initialize extra_data structure if needed
    if "qualification" not in conv.extra_data:
        conv.extra_data["qualification"] = {"extra_data": {}}
    
    # Inject available_variants as if a product list was just shown
    print("💡 Injecting mock variants for testing...")
    conv.extra_data["qualification"]["extra_data"]["available_variants"] = [
        {"model": "iPhone 13", "price": 7590, "storage": "128Go", "grade": "Excellent", "battery": "90%"},
        {"model": "iPhone 13", "price": 6500, "storage": "64Go", "grade": "Bon", "battery": "85%"}
    ]
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(conv, "extra_data")
    db.commit()

    print("User: 'Je prends celui à 7 590 dhs'")
    res2 = await get_response("Je prends celui à 7 590 dhs", real_conv_id, user_id)
    print(f"Bot: {res2.message[:50]}...")
    
    db.expire_all()
    conv = db.query(Conversation).filter(Conversation.id == real_conv_id).first()
    q_data = conv.extra_data.get("qualification", {})
    locked = q_data.get("selection_locked")
    print(f"Selection Locked? {locked}")
    assert locked is True, "❌ Failed: Selection should be locked"

    print("\n--- Scenario 3: Anti-Relisting Guard ---")
    print("User: 'Ok'")
    res3 = await get_response("Ok", real_conv_id, user_id)
    print(f"Bot: {res3.message[:50]}...")
    # It should NOT be a list. It should be a confirmation question.
    is_list = "1." in res3.message and "2." in res3.message
    print(f"Is it a product list? {is_list}")
    assert is_list is False, "❌ Failed: Bot relisted products even though selection is locked"

    print("\n--- Scenario 4: Handoff Guard on Unknown ---")
    res4 = await get_response("blabla random text", str(uuid.uuid4()), f"user_{uuid.uuid4()}")
    print(f"Bot: {res4.message[:50]}...")
    print(f"Should Handoff? {res4.should_handoff}")
    assert res4.should_handoff is False, "❌ Failed: Unknown intent should not trigger handoff"

    print("\n✅ Verification V2 complete.")
    db.close()

if __name__ == "__main__":
    import os
    os.environ["OFFLINE_MODE"] = "1"
    os.environ["OPENAI_API_KEY"] = "sk-dummy"
    asyncio.run(verify_robustness_v2())
