"""
Relab Commercial Chatbot - FastAPI Application
Backend-first chatbot for revenue generation
"""
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import logging

from models.database import init_db, get_db
from models.schemas import ChatRequest, ChatResponse
# chat_service import moved down
from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import services after logging is configured
from services.chat_service import chat_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Relab Chatbot Backend...")
    init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Relab Commercial Chatbot",
    description="Backend-first chatbot for Relab - Revenue-generating conversational AI",
    version="1.0.0",
    lifespan=lifespan
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler with environment-aware error responses.
    - META_COMPAT_MODE=true (production): Returns HTTP 200 to prevent Meta webhook retries
    - META_COMPAT_MODE=false (development): Returns HTTP 500 with proper error visibility
    """
    logger.critical(f"🔥 UNHANDLED EXCEPTION on {request.url.path}: {exc}", exc_info=True)
    
    if settings.meta_compat_mode:
        # Production/Meta mode: Return 200 to prevent retries
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=200,
            content={"message": "Service momentanément indisponible, veuillez réessayer."}
        )
    else:
        # Development mode: Return proper 500 for debugging
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if settings.debug else "An error occurred",
                "path": str(request.url.path)
            }
        )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Set to False to allow '*' origin
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Relab Commercial Chatbot",
        "version": "1.0.0",
        "environment": settings.app_env
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "llm": "configured"
    }


@app.get("/dashboard.html", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML file"""
    return FileResponse("dashboard.html")


@app.get("/test", response_class=HTMLResponse)
async def get_test_interface():
    """Serve the test interface HTML file"""
    return FileResponse("test_interface.html")


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Main chat endpoint
    
    This is the core endpoint that:
    1. Receives user messages
    2. Detects intent
    3. Applies business logic
    4. Qualifies leads
    5. Decides on human handoff
    6. Returns appropriate response
    
    The LLM is used ONLY for text formatting, never for decisions.
    """
    try:
        logger.info(f"Processing message: {request.message[:50]}...")
        
        # Process message through chat service
        response = await chat_service.process_message(request, db)
        
        logger.info(f"Response generated - Intent: {response.intent.type if response.intent else 'unknown'}, Handoff: {response.should_handoff}")
        
        return response
    
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        # Fallback response to prevent 500
        return ChatResponse(
            message="Je rencontre un petit souci technique, pourriez-vous reformuler ?",
            conversation_id=request.conversation_id or "error-fallback",
            intent=None,
            should_handoff=False,
            next_action="retry",
            metadata={"error": str(e)}
        )


@app.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Get conversation details"""
    from models.database import Conversation, Message
    
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at).all()
    
    return {
        "conversation": {
            "id": conversation.id,
            "contact_id": conversation.contact_id,
            "status": conversation.status,
            "intent_type": conversation.intent_type,
            "language": conversation.language,
            "monetization_score": conversation.monetization_score,
            "estimated_value": conversation.estimated_value,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at
        },
        "messages": [
            {
                "sender": msg.sender,
                "content": msg.content,
                "intent_type": msg.intent_type,
                "created_at": msg.created_at
            }
            for msg in messages
        ]
    }


@app.get("/leads")
async def get_leads(
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get all leads (for sales dashboard)"""
    from models.database import Lead
    
    query = db.query(Lead)
    
    if status:
        query = query.filter(Lead.status == status)
    
    leads = query.order_by(Lead.created_at.desc()).limit(50).all()
    
    return {
        "leads": [
            {
                "id": lead.id,
                "conversation_id": lead.conversation_id,
                "identifier": lead.user_id,
                "intent_type": lead.intent_type,
                "language": lead.language,
                "estimated_value": lead.estimated_value,
                "conversation_summary": lead.conversation_summary,
                "key_points": lead.key_points,
                "recommended_action": lead.recommended_action,
                "handoff_reason": lead.handoff_reason,
                "status": lead.status,
                "created_at": lead.created_at
            }
            for lead in leads
        ]
    }


@app.get("/api/dashboard/conversations")
async def get_dashboard_conversations(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Get recent conversations for dashboard inbox"""
    from models.database import Conversation, Message, Contact
    from sqlalchemy.orm import joinedload
    
    conversations = db.query(Conversation).options(
        joinedload(Conversation.contact)
    ).order_by(Conversation.last_message_at.desc()).limit(limit).all()
    
    results = []
    for conv in conversations:
        # Get last message text
        last_msg = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.desc()).first()
        
        results.append({
            "id": conv.id,
            "date": conv.last_message_at.isoformat(),
            "channel": conv.channel,
            "contact": conv.contact.contact_key if conv.contact else "Anonyme",
            "intent": conv.intent_type or "Inconnu",
            "topic": last_msg.content[:50] + "..." if last_msg else "Pas de message",
            "status": "bot" if conv.status != "handed_off" else "human",
            "credit": "OUI" if (conv.extra_data or {}).get("credit_interest") else "NON",
            "monetization_score": conv.monetization_score
        })
        
    return results


@app.get("/analytics/summary")
async def get_analytics_summary(db: Session = Depends(get_db)):
    """Get analytics summary"""
    from models.database import Conversation, Lead
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Time window: last 30 days
    last_30 = datetime.utcnow() - timedelta(days=30)
    
    # Total conversations
    total_conversations = db.query(func.count(Conversation.id)).scalar() or 0
    recent_conversations = db.query(func.count(Conversation.id)).filter(Conversation.created_at >= last_30).scalar() or 0
    
    # Total leads
    total_leads = db.query(func.count(Lead.id)).scalar() or 0
    
    # Leads by intent
    leads_by_intent = db.query(
        Lead.intent_type,
        func.count(Lead.id)
    ).group_by(Lead.intent_type).all()
    
    # Total estimated value
    total_value = db.query(func.sum(Lead.estimated_value)).scalar() or 0
    
    # Bot vs Human ratio
    human_handoffs = db.query(func.count(Conversation.id)).filter(Conversation.status == "handed_off").scalar() or 0
    bot_ratio = int(((total_conversations - human_handoffs) / total_conversations * 100)) if total_conversations > 0 else 100
    
    # Credit interest rate
    credit_interest = db.query(func.count(Conversation.id)).filter(Conversation.extra_data.contains({"credit_interest": True})).scalar() or 0
    credit_ratio = int((credit_interest / total_conversations * 100)) if total_conversations > 0 else 0

    return {
        "total_conversations": total_conversations,
        "recent_conversations": recent_conversations,
        "total_leads": total_leads,
        "total_estimated_value": total_value,
        "leads_by_intent": {
            intent: count for intent, count in leads_by_intent
        },
        "bot_ratio": bot_ratio,
        "human_ratio": 100 - bot_ratio,
        "credit_interest_ratio": credit_ratio,
        "conversion_rate": (total_leads / total_conversations * 100) if total_conversations > 0 else 0
    }


# ==========================================
# INSTAGRAM INTEGRATION
# ==========================================

from integrations.instagram import (
    verify_instagram_webhook,
    extract_instagram_message,
    send_instagram_message
)
from integrations.whatsapp import (
    verify_whatsapp_webhook,
    extract_whatsapp_message,
    send_whatsapp_message
)
from integrations.email import (
    extract_email_message_generic,
    send_email_message
)
from integrations.messenger import (
    verify_messenger_webhook,
    extract_messenger_message,
    send_messenger_message
)

@app.get("/webhook/instagram")
async def instagram_verification(request: Request):
    """
    Handle Instagram Webhook Verification
    """
    return await verify_instagram_webhook(request)


async def process_instagram_task(data: dict, db: Session):
    """
    Background task to process Instagram message without blocking Meta
    """
    try:
        # Create chat request
        chat_req = ChatRequest(
            message=data['text'],
            identifier=data['sender_id'],
            channel="instagram",
            metadata=data['metadata']
        )
        
        # Process through chatbot logic (can take 30s+)
        logger.info(f"🔄 Processing Instagram message from {data['sender_id']} in background")
        response = await chat_service.process_message(chat_req, db)
        
        # Send reply back to Instagram
        if response.message:
            logger.info(f"🚀 [PYTHON-SEND] Sending reply to Instagram: {response.message[:50]}...")
            await send_instagram_message(data['sender_id'], response.message)
        else:
            logger.info(f"🤫 Silent mode: No reply sent to Instagram user {data['sender_id']}")
    except Exception as e:
        logger.error(f"❌ Error in Instagram background task: {e}")

@app.post("/webhook/instagram")
async def instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle Incoming Instagram Messages (Async)
    """
    try:
        payload = await request.json()
        logger.info(f"📩 Received Instagram Webhook: {payload.get('object')}")
        
        # Extract message data
        data = extract_instagram_message(payload)
        
        if data:
            # Launch background task and return 200 immediately
            background_tasks.add_task(process_instagram_task, data, db)
            return {"status": "accepted", "message": "processing in background"}
            
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error receiving Instagram webhook: {e}")
        return {"status": "ok"} # Still 200 for Meta

# ==========================================
# WHATSAPP INTEGRATION
# ==========================================

@app.get("/webhook/whatsapp")
async def whatsapp_verification(request: Request):
    """Handle WhatsApp Webhook Verification"""
    return await verify_whatsapp_webhook(request)

async def process_whatsapp_task(data: dict, db: Session):
    """
    Background task to process WhatsApp message
    """
    try:
        chat_req = ChatRequest(
            message=data['text'],
            identifier=data['sender_id'],
            channel="whatsapp",
            metadata=data['metadata']
        )
        
        logger.info(f"🔄 Processing WhatsApp message from {data['sender_id']} in background")
        response = await chat_service.process_message(chat_req, db)
        
        if response.message:
            logger.info(f"🚀 [PYTHON-SEND] Sending reply to WhatsApp: {response.message[:50]}...")
            await send_whatsapp_message(data['sender_id'], response.message)
    except Exception as e:
        logger.error(f"❌ Error in WhatsApp background task: {e}")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Handle Incoming WhatsApp Messages (Async)"""
    try:
        payload = await request.json()
        logger.info(f"📩 Received WhatsApp Webhook")
        
        data = extract_whatsapp_message(payload)
        
        if data:
            background_tasks.add_task(process_whatsapp_task, data, db)
            
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error receiving WhatsApp webhook: {e}")
        return {"status": "ok"}

# ==========================================
# EMAIL INTEGRATION
# ==========================================

@app.post("/webhook/email")
async def email_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Incoming Email Webhooks"""
    try:
        # Check security token if provided in header or query
        token = request.query_params.get("token")
        if token != settings.email_webhook_token:
            raise HTTPException(status_code=401, detail="Invalid token")

        payload = await request.json()
        data = extract_email_message_generic(payload)
        
        if data:
            chat_req = ChatRequest(
                message=data['text'],
                identifier=data['sender_id'],
                channel="email",
                metadata=data['metadata']
            )
            
            logger.info(f"🔄 Processing Email from {data['sender_id']}")
            response = await chat_service.process_message(chat_req, db)
            
            if response.message:
                await send_email_message(data['sender_id'], response.message, subject=f"Re: {data['metadata'].get('subject', 'Relab')}")
            else:
                logger.info(f"🤫 Silent mode: No reply sent to Email user {data['sender_id']}")
            
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error processing Email webhook: {e}")
        return {"status": "error"}

# ==========================================
# MESSENGER INTEGRATION
# ==========================================

@app.get("/webhook/messenger")
async def messenger_verification(request: Request):
    """Handle Messenger Webhook Verification"""
    return await verify_messenger_webhook(request)

@app.post("/webhook/messenger")
async def messenger_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Incoming Messenger Messages"""
    try:
        payload = await request.json()
        logger.info(f"📩 Received Messenger Webhook: {payload}")
        
        data = extract_messenger_message(payload)
        
        if data:
            chat_req = ChatRequest(
                message=data['text'],
                identifier=data['sender_id'],
                channel="messenger",
                metadata=data['metadata']
            )
            
            logger.info(f"🔄 Processing Messenger from {data['sender_id']}")
            response = await chat_service.process_message(chat_req, db)
            
            if response.message:
                await send_messenger_message(data['sender_id'], response.message)
            else:
                logger.info(f"🤫 Silent mode: No reply sent to Messenger user {data['sender_id']}")
            
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error processing Messenger webhook: {e}")
        return {"status": "error"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
