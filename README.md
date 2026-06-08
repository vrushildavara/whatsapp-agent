# WhatsApp AI Agent 🤖

A production-ready WhatsApp chatbot powered by AI (Google Gemini), with intelligent conversation management, long-term memory (Mem0), and automatic response handling.

## ✨ Features

- 🔄 **Automatic Message Handling** - Receives and responds to WhatsApp messages automatically
- 🧠 **AI-Powered Responses** - Uses Google Gemini for intelligent conversations
- 💾 **Long-Term Memory** - Remembers user preferences and context using Mem0
- 📝 **Smart Summarization** - Automatically summarizes conversations every 20 messages
- ⏱️ **Debouncing** - Waits for user to finish typing before responding (3s delay)
- 🔐 **Multi-Account Support** - Handle multiple WhatsApp Business accounts
- 📊 **Conversation Context** - Maintains rolling summaries + recent messages
- 🎯 **Production Ready** - Async/await, error handling, database transactions

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WhatsApp User                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Sends "Hi"
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Meta WhatsApp API                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Webhook POST
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Your FastAPI Server                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  POST /message/webhook                                    │  │
│  │    ↓                                                      │  │
│  │  1. Parse webhook payload                                │  │
│  │  2. Get account credentials (phone_number_id → token)    │  │
│  │  3. Save user message to PostgreSQL                      │  │
│  │  4. Start debounce timer (3 seconds)                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  _generate_assistant_response()                          │  │
│  │    ↓                                                      │  │
│  │  1. Check if 20 messages → Summarize                     │  │
│  │  2. Fetch last 20 unsummarized messages                  │  │
│  │  3. Query Mem0 for relevant memories                     │  │
│  │  4. Build context: Summary + Memories + Recent           │  │
│  │  5. Call Gemini API for AI response                      │  │
│  │  6. Save assistant message to DB                         │  │
│  │  7. Send response to WhatsApp API ← NEW!                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Send message
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Meta WhatsApp API                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Delivers message
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                         WhatsApp User                            │
│                    Receives AI Response                          │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd d:\miraiminds\whatsapp-agents
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/whatsapp_agent
SECRET_KEY=your_secret_key
GEMINI_API_KEY=your_gemini_api_key
MEM0_API_KEY=your_mem0_api_key
WHATSAPP_VERIFY_TOKEN=your_secure_verify_token

# Optional (for media support)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_S3_BUCKET=your_bucket
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Start Server

```bash
uvicorn app.main:app --reload
```

### 5. Register WhatsApp Account

```bash
# First, create user and login
POST http://localhost:8000/users/register
{
  "name": "Your Name",
  "email": "your@email.com",
  "password": "password123"
}

# Login to get JWT token
POST http://localhost:8000/users/login
{
  "email": "your@email.com",
  "password": "password123"
}

# Register WhatsApp Business account
POST http://localhost:8000/account/create
Authorization: Bearer YOUR_JWT_TOKEN
{
  "phone_number": "15551470370",
  "phone_id": "799278879941922",
  "token": "YOUR_WHATSAPP_ACCESS_TOKEN"
}
```

### 6. Configure Webhook (Meta Developer Console)

1. Go to https://developers.facebook.com/apps/
2. Select your app → WhatsApp → Configuration
3. Set Webhook URL: `https://your-domain.com/message/webhook`
4. Set Verify Token: (same as `WHATSAPP_VERIFY_TOKEN` in .env)
5. Subscribe to `messages` field

### 7. Test!

Send a WhatsApp message to your business number. The bot will respond automatically! 🎉

## 📚 Documentation

- [WHATSAPP_SETUP.md](WHATSAPP_SETUP.md) - Detailed setup instructions
- [TESTING_GUIDE.md](TESTING_GUIDE.md) - Testing procedures and debugging
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical implementation details

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.12+)
- **Database**: PostgreSQL with SQLAlchemy (async)
- **AI/LLM**: Google Gemini API
- **Memory**: Mem0 (long-term memory service)
- **Storage**: AWS S3 (media files)
- **Auth**: JWT tokens
- **Migrations**: Alembic

## 📁 Project Structure

```
whatsapp-agents/
├── src/app/
│   ├── controller/          # Business logic
│   │   └── message_controller.py  # Webhook + message handling
│   ├── service/             # External services
│   │   ├── whatsapp_service.py    # WhatsApp API integration
│   │   ├── llm_service.py         # Gemini AI
│   │   ├── mem0_service.py        # Long-term memory
│   │   └── summary_service.py     # Conversation summarization
│   ├── router/              # API endpoints
│   │   └── message_router.py      # Webhook endpoints
│   ├── models/              # Database models
│   ├── validation/          # Pydantic schemas
│   │   └── webhook_validation.py  # WhatsApp webhook schema
│   └── utils/               # Helpers
│       └── session_processor.py   # Debouncing logic
├── alembic/                 # Database migrations
└── .env                     # Configuration
```

## 🔑 Key Features Explained

### Debouncing (3-second delay)

Prevents multiple AI responses when user sends rapid messages. Waits 3 seconds after last message before generating response.

### Chunked Summarization

Every 20 messages are automatically summarized into a rolling summary (≤150 words). Keeps context manageable for LLM.

### Context Building

- **Short-term**: Last 20 unsummarized messages
- **Long-term**: Mem0 memories + conversation summary
- **Result**: AI has full context without token overflow

### Multi-Account Support

Each WhatsApp Business account has its own credentials. System identifies account by `phone_number_id` from webhook.

## 🐛 Troubleshooting

### Webhook verification fails

- Check `WHATSAPP_VERIFY_TOKEN` in `.env` matches Meta console

### Bot doesn't respond

- Check `GEMINI_API_KEY` and `MEM0_API_KEY` are valid
- Check database connection
- Check server logs for errors

### Message not saved

- Verify database is running
- Check `DATABASE_URL` is correct
- Run migrations: `alembic upgrade head`

## 📊 API Endpoints

### Authentication

- `POST /users/register` - Register new user
- `POST /users/login` - Login and get JWT token

### WhatsApp Accounts

- `POST /account/create` - Register WhatsApp Business account
- `GET /account/{id}` - Get account details

### Messages (Webhook)

- `GET /message/webhook` - Webhook verification
- `POST /message/webhook` - Receive incoming messages

## 🤝 Contributing

This is a production-ready system. Follow the existing code patterns:

- Async/await for all I/O operations
- Service layer for business logic
- Pydantic for validation
- Type hints everywhere

## 📄 License

[Your License Here]

## 🎉 Success!

Your WhatsApp AI agent is now:

- ✅ Receiving messages automatically
- ✅ Processing with AI intelligence
- ✅ Sending responses automatically
- ✅ Maintaining conversation context
- ✅ Handling multiple users simultaneously

**Fully automated - no manual intervention required!** 🚀
#   w h a t s a p p - a g e n t 
 
 
