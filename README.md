# Relab Commercial Chatbot

Backend-first commercial chatbot for Relab - Moroccan high-tech sales, trade-in, and repair company.

## ✅ Current Status (Stable)
- **Codebase**: Production Ready
- **Recent Fixes**:
  - Fixed multiple questions bug (Prompt Reordering)
  - Resolved OpenAI Quota Exceeded error (Billing)
  - Optimized Product Search context
- **Last Deployed Code**: `fix: REORDER prompts` (Safe for deploy)


## 🎯 Purpose

This chatbot is a **business orchestrator**, not an autonomous AI. It:
- Qualifies leads
- Maximizes conversion
- Reduces human sales time
- Hands off to humans at the right moment

## 🏗️ Architecture

**Backend-First Design**
- FastAPI backend controls ALL decisions
- LLMs used ONLY for text formatting
- Deterministic business rules
- SQLite/PostgreSQL storage

**Key Components**
- Intent Detection (keyword + LLM fallback)
- Qualification Engine (data collection)
- Handoff Manager (human escalation)
- Response Generator (natural language)

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### 3. Run Locally

```bash
python main.py
```

Server runs at: `http://localhost:8000`

### 4. Test the API

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Bghit nchri iPhone 15",
    "channel": "whatsapp",
    "identifier": "212600000000"
  }'
```

**Note:** The `identifier` field is required. You can also use `user_id` as an alias.


## 📡 API Endpoints

### POST /chat
Main chat endpoint - processes user messages

**Request:**
```json
{
  "message": "Bghit nchri iPhone 15",
  "channel": "whatsapp",
  "identifier": "212600000000",
  "conversation_id": "optional-existing-id"
}
```

**Note:** `identifier` is required (phone number, user ID, email, etc.). The field `user_id` can be used as an alias for `identifier`.


**Response:**
```json
{
  "message": "Mezyan! Ghadi n3awnek. Ch7al budget dyalek?",
  "conversation_id": "uuid",
  "intent": {
    "type": "achat",
    "confidence": 0.95,
    "language": "darija",
    "monetization_score": 90
  },
  "should_handoff": false,
  "next_action": "continue_qualification"
}
```

### GET /conversations/{id}
Get conversation history

### GET /leads
Get qualified leads (for sales dashboard)

### GET /analytics/summary
Get analytics summary

## 🎛️ Business Rules

**Handoff Triggers:**
- Explicit human request
- Payment/financing mention
- High-value cart (>5000 MAD)
- SAV issues
- Qualification complete
- Max bot messages reached (10)

**Intent Types:**
- `achat` - Purchase (monetization: 90)
- `reprise` - Trade-in (monetization: 70)
- `reparation` - Repair (monetization: 60)
- `sav` - After-sales (monetization: 30)
- `info` - Information (monetization: 20)
- `humain` - Human request (monetization: 50)

**Languages:**
- Darija (priority)
- French
- English

## 📊 Database Schema

**Conversations** - Track all conversations
**Messages** - Individual messages with intent
**Leads** - Qualified leads for human handoff
**Analytics** - Metrics and KPIs

## 🚢 Deployment

### Railway (Recommended)

1. Push to GitHub
2. Connect Railway to your repo
3. Add environment variables
4. Deploy automatically

### Environment Variables

**Required:**
```
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

**Optional:**
```
DATABASE_URL=postgresql://... (Railway provides this)
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Meta Compatibility Mode
# Set to 'true' for production webhooks (returns HTTP 200 on errors)
# Set to 'false' for local development (returns proper 4xx/5xx codes)
META_COMPAT_MODE=true
```


## 📈 Monitoring

View analytics at: `GET /analytics/summary`

Key metrics:
- Total conversations
- Total leads
- Conversion rate
- Estimated revenue
- Leads by intent

## 🔧 Development

**Project Structure:**
```
├── main.py                 # FastAPI app
├── config.py              # Configuration
├── models/
│   ├── database.py        # SQLAlchemy models
│   └── schemas.py         # Pydantic schemas
├── engine/
│   └── intent_detector.py # Intent detection
├── logic/
│   ├── business_rules.py  # Business rules
│   ├── qualification.py   # Lead qualification
│   └── handoff_manager.py # Human handoff
├── llm/
│   ├── client.py          # OpenAI client
│   ├── prompts.py         # Prompt templates
│   └── response_generator.py # Response generation
└── services/
    └── chat_service.py    # Main orchestrator
```

## 🎯 Success Metrics

This chatbot succeeds if it:
- Generates qualified leads
- Saves sales team time
- Increases conversion rate
- Creates NO customer issues
- Remains simple to maintain

## 📝 License

Proprietary - Relab Morocco
