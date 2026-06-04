# WhatsApp AI Agent 🤖

A production-ready WhatsApp chatbot powered by AI (Google Gemini), with intelligent conversation management, long-term memory (Mem0), and automatic response handling.

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

---

## 🏗️ Architecture

```text
WhatsApp User
      │
      ▼
Meta WhatsApp API
      │
      ▼
FastAPI Webhook (/message/webhook)
      │
      ├── Parse webhook payload
      ├── Get account credentials
      ├── Save message to PostgreSQL
      └── Start debounce timer (3s)
      │
      ▼
_generate_assistant_response()
      │
      ├── Check if 20 messages → Summarize
      ├── Fetch recent messages
      ├── Query Mem0 memories
      ├── Build conversation context
      ├── Call Gemini API
      ├── Save assistant response
      └── Send response to WhatsApp API
      │
      ▼
Meta WhatsApp API
      │
      ▼
WhatsApp User Receives AI Response
```

---

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

```http
POST http://localhost:8000/users/register
{
  "name": "Your Name",
  "email": "your@email.com",
  "password": "password123"
}
```

```http
POST http://localhost:8000/users/login
{
  "email": "your@email.com",
  "password": "password123"
}
```

```http
POST http://localhost:8000/account/create
Authorization: Bearer YOUR_JWT_TOKEN

{
  "phone_number": "15551470370",
  "phone_id": "799278879941922",
  "token": "YOUR_WHATSAPP_ACCESS_TOKEN"
}
```

### 6. Configure Webhook (Meta Developer Console)

1. Go to Meta Developers Console
2. Select your app → WhatsApp → Configuration
3. Set Webhook URL:

   ```text
   https://your-domain.com/message/webhook
   ```
4. Set Verify Token (same as `WHATSAPP_VERIFY_TOKEN`)
5. Subscribe to the `messages` field

### 7. Test

Send a WhatsApp message to your business number. The bot will respond automatically. 🎉

---

## 📚 Documentation

* `WHATSAPP_SETUP.md` — Detailed setup instructions
* `TESTING_GUIDE.md` — Testing procedures and debugging
* `IMPLEMENTATION_SUMMARY.md` — Technical implementation details

---

## 🛠️ Tech Stack

| Component      | Technology                    |
| -------------- | ----------------------------- |
| Backend        | FastAPI (Python 3.12+)        |
| Database       | PostgreSQL + SQLAlchemy Async |
| AI/LLM         | Google Gemini                 |
| Memory         | Mem0                          |
| Storage        | AWS S3                        |
| Authentication | JWT                           |
| Migrations     | Alembic                       |

---

## 📁 Project Structure

```text
whatsapp-agents/
├── src/app/
│   ├── controller/
│   │   └── message_controller.py
│   ├── service/
│   │   ├── whatsapp_service.py
│   │   ├── llm_service.py
│   │   ├── mem0_service.py
│   │   └── summary_service.py
│   ├── router/
│   │   └── message_router.py
│   ├── models/
│   ├── validation/
│   │   └── webhook_validation.py
│   └── utils/
│       └── session_processor.py
├── alembic/
└── .env
```

---

## 🔑 Key Features Explained

### Debouncing (3-Second Delay)

Prevents multiple AI responses when users send rapid messages. The system waits 3 seconds after the last message before generating a response.

### Chunked Summarization

Every 20 messages are automatically summarized into a rolling summary (≤150 words), keeping context manageable for the LLM.

### Context Building

* **Short-Term Memory** → Last 20 unsummarized messages
* **Long-Term Memory** → Mem0 memories + conversation summaries
* **Result** → Rich context without token overflow

### Multi-Account Support

Each WhatsApp Business account maintains its own credentials. The system identifies the correct account using `phone_number_id` from incoming webhooks.

---

## 🐛 Troubleshooting

### Webhook Verification Fails

* Verify `WHATSAPP_VERIFY_TOKEN` matches the Meta Developer Console configuration.

### Bot Doesn't Respond

* Verify `GEMINI_API_KEY`
* Verify `MEM0_API_KEY`
* Verify database connectivity
* Check application logs

### Messages Not Saved

* Verify PostgreSQL is running
* Verify `DATABASE_URL`
* Run:

```bash
alembic upgrade head
```

---

## 📊 API Endpoints

### Authentication

* `POST /users/register`
* `POST /users/login`

### WhatsApp Accounts

* `POST /account/create`
* `GET /account/{id}`

### Webhook

* `GET /message/webhook`
* `POST /message/webhook`

---

## 🤝 Contributing

Follow existing project patterns:

* Async/await for all I/O
* Service layer architecture
* Pydantic validation
* Type hints throughout the codebase

---

## 📄 License

[Your License Here]

---

## 🎉 Success!

Your WhatsApp AI Agent is now:

* ✅ Receiving messages automatically
* ✅ Processing conversations with AI
* ✅ Sending responses automatically
* ✅ Maintaining conversation context
* ✅ Handling multiple users simultaneously

**Fully automated — no manual intervention required! 🚀**
