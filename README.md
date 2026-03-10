# WhatsApp AI Customer Care Bot 🤖

A Python-based WhatsApp bot powered by Google Gemini AI.

## Setup

### 1. Install Python dependencies
```
pip install -r requirements.txt
```

### 2. Fill in your .env file
```
WHATSAPP_TOKEN=     ← from Meta Developer Dashboard
PHONE_NUMBER_ID=    ← from Meta Developer Dashboard
VERIFY_TOKEN=mySecretVerify123
GEMINI_API_KEY=     ← from aistudio.google.com
PORT=3000
```

### 3. Run locally
```
python app.py
```

### 4. Deploy to Render.com
- Push to GitHub
- Connect repo on render.com
- Add environment variables
- Build command: pip install -r requirements.txt
- Start command: gunicorn app:app

## Features
- ✅ Auto-reply to customer questions using Gemini AI
- ✅ Order tracking (connect your DB in get_order_status())
- ✅ Human escalation detection
- ✅ Per-user conversation history
- ✅ Hindi + English support
