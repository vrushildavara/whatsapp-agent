# WhatsApp AI Agent 🤖

A production-ready WhatsApp chatbot powered by AI (Google Gemini), with intelligent conversation management, long-term memory (Mem0), automatic response handling, and comprehensive media support.

---

## ✨ Features

* 🔄 **Automatic Message Handling** — Receives and responds to WhatsApp messages automatically
* 🧠 **AI-Powered Responses** — Uses Google Gemini for intelligent conversations
* 💾 **Long-Term Memory** — Remembers user preferences and context using Mem0
* 📝 **Smart Summarization** — Automatically summarizes conversations every 20 messages
* ⏱️ **Debouncing** — Waits for user to finish typing before responding (3s delay)
* 🔐 **Multi-Account Support** — Handle multiple WhatsApp Business accounts
* 📊 **Conversation Context** — Maintains rolling summaries + recent messages
* 🎯 **Production Ready** — Async/await, error handling, database transactions
* 📁 **Rich Media Support** — Handle images, videos, audio, documents, stickers, and reactions
* 🎬 **Template Messages** — Send pre-approved templates with dynamic components
* 🔌 **RAG Integration** — Optional RAG service for knowledge-aware responses
* 📧 **Broadcasting** — Send bulk messages with delivery tracking
* 🔐 **User Authentication** — JWT-based auth with role management
* 💬 **Session Management** — Track conversation history and user interactions

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WhatsApp User                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │    Meta WhatsApp API (v24)   │
        └──────────────────────┬───────┘
                               │
                               ▼
        ┌────────────────────────────────────┐
        │  FastAPI Application (Port 8000)   │
        │                                    │
        │  Routers:                          │
        │  ├── message_router.py             │
        │  ├── account_router.py             │
        │  ├── user_router.py                │
        │  ├── session_router.py             │
        │  ├── broadcast_router.py           │
        │  ├── template_router.py            │
        │  ├── tool_router.py                │
        │  └── rag_router.py                 │
        └────────────────┬───────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        │                                  │
        ▼                                  ▼
┌──────────────────────┐      ┌──────────────────────┐
│  PostgreSQL + Async  │      │  Message Processing  │
│  (SQLAlchemy ORM)    │      │  Pipeline            │
│                      │      │                      │
│ • Users             │      │ 1. Parse webhook    │
│ • Accounts          │      │ 2. Validate request │
│ • Sessions          │      │ 3. Save message     │
│ • Messages          │      │ 4. Queue response   │
│ • Broadcasts        │      │ 5. Generate LLM     │
│ • Templates         │      │ 6. Send via Meta    │
│ • Reactions         │      │ 7. Update history   │
└──────────────────────┘      └──────────────────────┘
        │                             │
        │            ┌────────────────┼────────────────┐
        │            │                │                │
        ▼            ▼                ▼                ▼
    ┌──────┐  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
    │Redis │  │ Gemini   │  │   Mem0 AI    │  │ Hetzner S3   │
    │Cache │  │  API     │  │   Memory     │  │  (Media)     │
    └──────┘  └──────────┘  └──────────────┘  └──────────────┘
```

### Message Flow (Detailed)

```
1. Webhook Receives Message
   ├─ Parse Meta webhook payload
   ├─ Extract: from_number, to_number, message_type, media_id
   └─ Ignore status updates (read receipts, delivery confirmations)

2. Message Processing (send_message_controller)
   ├─ Validate account is active
   ├─ Download media from WhatsApp (if media_id present)
   │  └─ Convert to JPEG if needed (Pillow)
   ├─ Upload to S3 (Hetzner)
   ├─ Save USER message to PostgreSQL
   ├─ Add to Mem0 memory store
   └─ Enqueue for async response generation

3. Response Generation (session_processor.py)
   ├─ Check if 20 messages → trigger summarization
   ├─ Fetch recent unsummarized messages
   ├─ Query Mem0 for conversation memories
   ├─ Build context:
   │  ├─ Recent messages (last 20)
   │  ├─ Conversation summaries
   │  └─ Mem0 memories
   ├─ Call Gemini API with media support
   ├─ Save ASSISTANT message to session
   └─ Return response

4. WhatsApp Send
   ├─ Handle different message types:
   │  ├─ Text → send_message
   │  ├─ Media (image/video) → send media type
   │  ├─ Audio → send audio type
   │  ├─ Documents → send document type
   │  └─ Templates → send_template_message
   └─ Log delivery status via webhook
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd /path/to/whatsapp-agent
pip install -r requirements.txt
# OR with uv (faster):
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/whatsapp_agent

# Security
SECRET_KEY=your_secure_key_here
API_KEY_ENCRYPTION_KEY=your_encryption_key

# Redis (for debouncing and session locks)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# Email (optional)
MAIL_HOST=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
MAIL_TLS=true
MAIL_SSL=false

# AI & Memory
GEMINI_API_KEY=your_gemini_api_key
LLM_API_URL=https://api.gemini.com/v1/llm/generate
MEM0_API_KEY=your_mem0_api_key

# Storage (Hetzner S3)
HETZNER_ACCESS_KEY=your_access_key
HETZNER_SECRET_KEY=your_secret_key
HETZNER_S3_ENDPOINT=https://s3.hetzner.com
HETZNER_S3_BUCKET=your_bucket_name
HETZNER_S3_REGION=fsn1

# Optional
RAG_SERVICE_URL=https://your_rag_service_url
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Start Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or using the script:
```bash
python -m app.main
```

### 5. Register User & Account

```bash
# Register
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Your Name",
    "email": "your@email.com",
    "password": "password123"
  }'

# Login (get JWT token)
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your@email.com",
    "password": "password123"
  }'

# Create WhatsApp Account
curl -X POST http://localhost:8000/account/create \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "15551470370",
    "phone_number_id": "799278879941922",
    "token": "YOUR_WHATSAPP_ACCESS_TOKEN",
    "waba_id": "YOUR_WABA_ID"
  }'
```

### 6. Configure Webhook (Meta Developer Console)

1. Go to [Meta Developers Console](https://developers.facebook.com)
2. Select your app → WhatsApp → Configuration
3. Set Webhook URL:
   ```
   https://your-domain.com/message/send
   ```
4. Set Verify Token (same as `WHATSAPP_VERIFY_TOKEN` in `.env`)
5. Subscribe to:
   - `messages` — incoming messages
   - `message_status` — delivery/read receipts
   - `message_template_status_update` — template approvals

### 7. Test the Agent

Send a WhatsApp message to your business number. The bot will:
1. ✅ Receive the message
2. ✅ Process with AI
3. ✅ Send automatic response
4. ✅ Save conversation history

---

## 📚 API Endpoints

### Authentication
- `POST /users/register` — Create new user
- `POST /users/login` — Get JWT token

### Account Management
- `POST /account/create` — Add WhatsApp Business account
- `GET /account/{id}` — Get account details
- `GET /accounts` — List user's accounts

### Messaging
- `POST /message/send` — Send/receive messages (webhook & sandbox)
- `POST /message/{from_number}/send-template` — Send template
- `POST /message/assistant/send` — Send via API (auth required)
- `POST /message/react` — Send emoji reaction

### Sessions & History
- `GET /session/{session_id}` — Get conversation history
- `GET /sessions` — List user sessions
- `POST /session/{session_id}/archive` — Archive session

### Broadcasting
- `POST /broadcast/create` — Create bulk message campaign
- `GET /broadcast/{id}` — Get broadcast status
- `GET /broadcasts` — List all broadcasts

### Templates
- `GET /templates/{waba_id}` — List approved templates
- `GET /template/{template_id}` — Get template details

### RAG (Knowledge Base)
- `POST /rag/index` — Index documents
- `POST /rag/search` — Search knowledge base

---

## 🛠️ Tech Stack

| Component      | Technology                    |
| -------------- | ----------------------------- |
| Backend        | FastAPI (Python 3.12+)        |
| Database       | PostgreSQL + SQLAlchemy Async |
| AI/LLM         | Google Gemini                 |
| Memory         | Mem0 AI                       |
| Cache/Queue    | Redis                         |
| Storage        | Hetzner S3 (or AWS S3)        |
| Authentication | JWT + Bcrypt                  |
| Migrations     | Alembic                       |
| Media Utils    | Pillow, Pillow-HEIF           |
| HTTP Client    | HTTPX (async)                 |
| Task Queue     | Redis + async tasks           |

---

## 📁 Project Structure

```
whatsapp-agent/
├── src/app/
│   ├── main.py                          # FastAPI app entry point
│   ├── common/
│   │   ├── settings.py                  # Env config
│   │   └── responses.py                 # Standard response formats
│   ├── controller/
│   │   └── message_controller.py        # Request handlers
│   ├── service/
│   │   ├── whatsapp_service.py          # Meta API integration
│   │   ├── llm_service.py               # Gemini API calls
│   │   ├── mem0_service.py              # Memory management
│   │   ├── message_service.py           # Message CRUD
│   │   ├── session_processor.py         # Response generation
│   │   ├── account_service.py           # Account management
│   │   ├── broadcast_service.py         # Bulk messages
│   │   ├── template_service.py          # Template rendering
│   │   ├── s3_service.py                # Media storage
│   │   └── rag_service.py               # Knowledge base
│   ├── router/
│   │   ├── message_router.py            # /message endpoints
│   │   ├── account_router.py            # /account endpoints
│   │   ├── user_router.py               # /users endpoints
│   │   ├── session_router.py            # /session endpoints
│   │   ├── broadcast_router.py          # /broadcast endpoints
│   │   ├── template_router.py           # /templates endpoints
│   │   ├── tool_router.py               # /tools endpoints
│   │   └── rag_router.py                # /rag endpoints
│   ├── models/
│   │   ├── user.py                      # User ORM model
│   │   ├── account.py                   # WhatsApp account model
│   │   ├── message.py                   # Message history model
│   │   ├── session.py                   # Conversation session model
│   │   ├── broadcast.py                 # Bulk campaign model
│   │   └── template.py                  # Template cache model
│   ├── validation/
│   │   ├── message_validation.py        # Pydantic schemas
│   │   ├── account_validation.py        # Account DTOs
│   │   ├── broadcast_validation.py      # Broadcast DTOs
│   │   └── template_validation.py       # Template DTOs
│   ├── utils/
│   │   ├── media_utils.py               # MIME detection, conversion
│   │   ├── session_processor.py         # Background response generation
│   │   ├── redis_manager.py             # Redis client
│   │   ├── middleware.py                # Auth middleware
│   │   └── logger.py                    # Logging setup
│   └── database/
│       ├── db_handler.py                # SQLAlchemy + async setup
│       └── migrations/                  # Alembic migrations
├── alembic/
│   ├── versions/                        # Migration scripts
│   ├── env.py
│   └── script.py.mako
├── .env.example                         # Environment template
├── pyproject.toml                       # Dependencies
├── requirements.txt                     # Pip dependencies
├── alembic.ini                          # Alembic config
└── README.md                            # This file
```

---

## 🔑 Key Features Deep Dive

### 1. **Webhook Message Handling** (`message_router.py`)

The system accepts incoming WhatsApp messages via the Meta Webhook API. It handles:

- **Text messages** — Direct content
- **Media messages** — Images, videos, audio, documents, stickers
- **Button interactions** — Quick-reply button taps
- **Reactions** — Emoji reactions to previous messages
- **Status updates** — Delivery/read receipts (tracked separately)

```python
# Example: Processing different message types
if msg_type == "text":
    user_message = message.get("text", {}).get("body")
elif msg_type == "image":
    user_message = message.get("image", {}).get("caption", "[Image]")
    media_id = message.get("image", {}).get("id")
elif msg_type == "button":
    user_message = message.get("button", {}).get("text")
# ... more types
```

### 2. **Media Download & Storage** (`message_controller.py`)

When media is received:
1. Download from Meta (WhatsApp API) using access token
2. Detect MIME type and convert to JPEG if needed
3. Upload to Hetzner S3 for persistent storage
4. Extract metadata using Gemini for supported types
5. Save URL in message history

```python
# Download from WhatsApp
media_content, mime_type = await WhatsAppService.download_media(media_id, token)

# Upload to S3
s3_url = await s3_service.upload_media(media_content, filename, mime_type)

# Extract metadata async
asyncio.create_task(s3_service.extract_media_metadata(s3_url, message_id, mime_type))
```

### 3. **AI Response Generation** (`llm_service.py`)

The LLM service calls Gemini API with:
- **System prompt** — Bot personality and instructions
- **User message** — Actual user input
- **Media URLs** — Images/videos for multimodal understanding
- **Tools** — Optional tool definitions for extended capabilities

```python
# Retry logic: 3 attempts with exponential backoff
async def generate_response(
    system_prompt: str,
    user_message: str,
    media_urls: list[str] | None = None,
    tools: list[dict] | None = None,
) -> tuple[str, int | None, int | None]:
    # Handles 5xx errors with retry, fails fast on 4xx
```

### 4. **Memory Management** (`mem0_service.py`)

Mem0 provides long-term memory:
- Stores user preferences, history, context
- Retrieves relevant memories for conversation context
- Updates memories after each exchange
- Enables personalized responses across sessions

### 5. **Session & Conversation Context**

Each conversation is a **session**:
- Contains user + business phone numbers
- Tracks all messages (user + assistant)
- Stores summaries every 20 messages
- Maintains metadata (status, last activity, etc.)

Context building:
```
Recent Messages (last 20)
    +
Conversation Summaries (older messages)
    +
Mem0 Memories (preferences, facts)
    =
Full Context for Gemini
```

### 6. **Debouncing** (Redis)

Prevents multiple responses to rapid messages:
1. Message arrives → Set 3-second Redis timer
2. Another message arrives → Reset timer
3. Timer expires → Generate response once
4. Lock prevents concurrent processing

```python
redis = get_redis_client()
lock_key = f"s:{session_id}:lock"
if await redis.exists(lock_key):
    # Skip — already processing
    return
await enqueue_and_trigger(session_id, ...)  # Queue for response
```

### 7. **Template Messages**

Pre-approved message templates with dynamic components:
- **Header** — Image, video, or document
- **Body** — Text with placeholders
- **Buttons** — Call-to-action buttons

```python
components = [
    {"type": "header", "parameters": [{"type": "image", "image": {"link": "..."}}]},
    {"type": "body", "parameters": [{"type": "text", "text": "Hello John"}]},
    {"type": "button", "sub_type": "quick_reply", "index": 0, "parameters": [...]},
]

await WhatsAppService.send_template_message(
    phone_number_id=phone_number_id,
    to_number=to_number,
    template_name="welcome_template",
    language="en_US",
    components=components,
    access_token=token,
)
```

### 8. **Broadcasting**

Send bulk messages with tracking:
- Create campaigns with recipient lists
- Support templates and custom text
- Track delivery status per recipient
- Retry failed sends

---

## 🧪 Testing

### Manual Testing (Sandbox Mode)

```bash
curl -X POST http://localhost:8000/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "sandbox": true,
    "from_number": "919999999999",
    "to_number": "918888888888",
    "message": "Hello from sandbox!",
    "media_bytes": ["base64_encoded_image"],
    "media_type": "image/jpeg"
  }'
```

### Unit Tests

```bash
pytest tests/ -v
pytest tests/test_message_controller.py -v
pytest tests/test_llm_service.py -v
```

### Integration Tests

- Webhook payload validation
- End-to-end message flow
- Media upload/download
- LLM response generation

See `TESTING_GUIDE.md` for detailed procedures.

---

## 🐛 Troubleshooting

### Webhook Verification Fails

- Verify `WHATSAPP_VERIFY_TOKEN` matches Meta console
- Check that endpoint is accessible from internet
- Ensure POST method is allowed

### Bot Doesn't Respond

1. Check logs: `tail -f logs/app.log`
2. Verify `GEMINI_API_KEY` is set and valid
3. Verify `MEM0_API_KEY` is set and valid
4. Test Redis connection: `redis-cli ping`
5. Test database: `psql -U user -d whatsapp_agent -c "SELECT 1;"`

### Messages Not Saved to Database

- Run migrations: `alembic upgrade head`
- Check `DATABASE_URL` format
- Verify PostgreSQL is running: `psql -U user -c "\\dt"`

### Media Upload Fails

- Verify S3 credentials (Hetzner)
- Check bucket exists and is writable
- Verify CORS settings if media fails to load

### Rate Limiting

- Check Meta API limits (1000 messages/second)
- Implement request throttling if needed
- Use broadcast service for bulk sends

---

## 🔐 Security Best Practices

1. **Secrets Management**
   - Never commit `.env` to version control
   - Use strong `SECRET_KEY` (min 32 chars)
   - Rotate API keys regularly

2. **Database**
   - Use strong password for PostgreSQL
   - Enable SSL/TLS for remote connections
   - Run migrations with proper permissions

3. **WhatsApp Access**
   - Tokens stored encrypted in database
   - Rotate tokens quarterly
   - Monitor API logs for suspicious activity

4. **User Authentication**
   - JWT tokens expire after 7 days
   - Hash passwords with bcrypt
   - Implement rate limiting on login

5. **CORS Policy**
   - Currently allows all origins (`*`) — restrict in production
   - Set `allow_origins` to specific domains

---

## 📊 Monitoring & Logging

All events logged with structured format:
```
2026-06-24 14:23:45 | INFO | WhatsApp message sent | to=919999999999 | message_id=wamid.xxx
```

Logging levels:
- `DEBUG` — Detailed processing steps
- `INFO` — Normal operations
- `WARNING` — Recoverable issues
- `ERROR` — Failures requiring attention

Log locations:
- Console output (development)
- File logs (production, if configured)
- External service (e.g., Sentry for error tracking)

---

## 🚀 Deployment

### Using Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables (Production)

```bash
export DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/whatsapp_agent
export SECRET_KEY=$(openssl rand -hex 32)
export GEMINI_API_KEY=your_key
export MEM0_API_KEY=your_key
export REDIS_HOST=redis-host
```

### Running Migrations on Deploy

```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 📖 Additional Documentation

* `WHATSAPP_SETUP.md` — Detailed Meta setup instructions
* `TESTING_GUIDE.md` — Testing procedures and debugging
* `IMPLEMENTATION_SUMMARY.md` — Technical implementation details
* `API_DOCS.md` — Full API reference (auto-generated at `/docs`)

---

## 🤝 Contributing

Follow these patterns:

* **Async/await** — All I/O operations must be async
* **Service layer** — Keep business logic in services
* **Pydantic validation** — Use validators for all inputs
* **Type hints** — Full type coverage throughout codebase
* **Error handling** — Use `ErrorResponse` for API errors
* **Logging** — Log important operations with context
* **Testing** — Write tests for new features

Example:
```python
# Service layer
class MyService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def process_message(self, message: str) -> dict:
        # Validate
        if not message.strip():
            raise ErrorResponse(400, "Message cannot be empty")
        
        # Process
        result = await self.do_work(message)
        
        # Return
        return {"status": "success", "data": result}

# Controller
async def my_endpoint(data: MyValidation, db: AsyncSession) -> JSONResponse:
    service = MyService(db)
    result = await service.process_message(data.message)
    return success_response(data=result)
```

---

## 📄 License

This project is licensed under the MIT License — see LICENSE file for details.

---

## 🎉 Next Steps

Your WhatsApp AI Agent is now:

* ✅ Receiving messages automatically
* ✅ Processing conversations with AI
* ✅ Sending responses automatically
* ✅ Maintaining conversation context
* ✅ Handling multiple users simultaneously
* ✅ Supporting rich media types
* ✅ Storing long-term memories
* ✅ Sending templates & bulk messages

**Fully automated — no manual intervention required! 🚀**

For support, check the troubleshooting section or create an issue on GitHub.
