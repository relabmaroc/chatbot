from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config import settings

Base = declarative_base()


class Contact(Base):
    """Long-term persistent user identity"""
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_key = Column(String, unique=True, index=True, nullable=False)  # channel + identifier
    language = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Persistent Memory
    memory_json = Column(JSON, default={
        "intent_history": [],
        "product_preferences": [],
        "budget_range": None,
        "city": None,
        "credit_interest": None,
        "objections": [],
        "lead_stage": "new",
        "last_action": None
    })
    
    conversations = relationship("Conversation", back_populates="contact")


class Conversation(Base):
    """Conversation tracking"""
    __tablename__ = "conversations"
    
    id = Column(String, primary_key=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), index=True)
    channel = Column(String, default="web")  # whatsapp, instagram, web
    status = Column(String, default="active")  # active, qualified, handed_off, closed
    language = Column(String, nullable=True)
    
    # Business metrics
    intent_type = Column(String, nullable=True)
    monetization_score = Column(Integer, default=0)
    estimated_value = Column(Integer, nullable=True)  # MAD
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Extra data
    extra_data = Column(JSON, default={})
    
    contact = relationship("Contact", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Individual messages in conversations"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), index=True, nullable=False)
    
    # Message content
    sender = Column(String, nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Intent detection
    intent_type = Column(String, nullable=True)
    intent_confidence = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Extra data
    extra_data = Column(JSON, default={})
    
    conversation = relationship("Conversation", back_populates="messages")


class Lead(Base):
    """Qualified leads for human handoff"""
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, unique=True, index=True)
    user_id = Column(String, nullable=True, index=True)
    
    # Lead details
    intent_type = Column(String, nullable=False)
    language = Column(String, nullable=False)
    channel = Column(String, default="web")
    
    # Qualification data
    qualification_data = Column(JSON, default={})
    estimated_value = Column(Integer, nullable=True)
    
    # Summary
    conversation_summary = Column(Text, nullable=False)
    key_points = Column(JSON, default=[])
    recommended_action = Column(Text, nullable=False)
    
    # Handoff details
    handoff_reason = Column(String, nullable=False)
    assigned_to = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, contacted, converted, lost
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Extra data
    extra_data = Column(JSON, default={})


class Analytics(Base):
    """Analytics and metrics"""
    __tablename__ = "analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Metrics
    date = Column(DateTime, default=datetime.utcnow, index=True)
    metric_name = Column(String, nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    
    # Dimensions
    intent_type = Column(String, nullable=True)
    language = Column(String, nullable=True)
    channel = Column(String, nullable=True)
    
    # Extra data
    extra_data = Column(JSON, default={})


# Database setup - Use environment-first approach
db_url = settings.database_url

# 1. Handle PostgreSQL (Railway style)
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# 2. Handle Turso (libsql)
elif db_url.startswith(("libsql://", "https://")) and "turso.io" in db_url:
    # Normalize host: remove protocols
    raw_host = db_url
    for proto in ["libsql://", "https://"]:
        raw_host = raw_host.replace(proto, "", 1)
    
    # Strip paths/queries
    base_host = raw_host.split("?")[0].split("/")[0]
    
    # Force sqlite+libsql:// (mandatory for the SQLAlchemy dialect)
    db_url = f"sqlite+libsql://{base_host}"
    
    # 3. Inject authToken safely
    if settings.database_auth_token:
        # Check if already present to avoid duplicates
        if "authToken=" not in db_url:
            separator = "&" if "?" in db_url else "?"
            db_url = f"{db_url}{separator}authToken={settings.database_auth_token}"

# Engine creation
is_sqlite_based = "sqlite" in db_url.lower()

engine = create_engine(
    db_url,
    # check_same_thread is ONLY for local SQLite files
    connect_args={"check_same_thread": False} if (is_sqlite_based and "libsql" not in db_url.lower()) else {},
    pool_pre_ping=True,      # Check connection before using
    pool_recycle=3600,       # Recycle connections every hour
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    # Debug log inside here because logging is configured AFTER import in main.py
    import logging
    logger = logging.getLogger(__name__)
    
    clean_url = db_url.split("authToken=")[0] + "authToken=***" if "authToken=" in db_url else db_url
    logger.info(f"🔌 Connecting to DB with: {clean_url}")
    
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
