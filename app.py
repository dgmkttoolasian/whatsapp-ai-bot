from flask import Flask, request
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Store conversation history per user (in memory)
sessions = {}

# ✏️ CUSTOMIZE THIS with your own business info
SYSTEM_PROMPT = """
You are a friendly customer care assistant for MyStore, an e-commerce shop.

ABOUT THE STORE:
- We sell electronics and accessories
- Free shipping on orders above ₹499, otherwise ₹50 flat
- Delivery in 3-5 business days
- Returns accepted within 7 days (unused items only)
- Payment: UPI, Credit/Debit Card, COD available
- Support hours: 9am to 6pm IST (you handle after hours)

WHAT YOU CAN DO:
1. Answer questions about products, shipping, returns, payments
2. Help customers with order issues
3. Track orders — ask for Order ID, then respond with: TRACK_ORDER:<order_id>
4. Escalate to human if needed — respond with: ESCALATE_TO_HUMAN

ESCALATION RULES:
- Customer asks for human/agent/manager → ESCALATE_TO_HUMAN
- Customer is very angry or frustrated → ESCALATE_TO_HUMAN

IMPORTANT:
- Keep replies short and friendly
- Reply in the same language the customer uses (Hindi or English)
- Never make up information you don't know
"""

# Fake order data — replace with your real DB later
def get_order_status(order_id):
    orders = {
        "ORD001": "📦 Packed and ready to ship",
        "ORD002": "🚚 Out for delivery — arriving today!",
        "ORD003": "✅ Delivered on March 6th",
        "ORD004": "🔄 Return initiated, refund in 3-5 days",
    }
    return orders.get(order_id.upper(), "❌ Order ID not found. Please double-check and try again.")


# Send WhatsApp message
def send_message(to, text):
    url = f"https://graph.facebook.com/v19.0/{os.getenv('PHONE_NUMBER_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {os.getenv('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(url, json=payload, headers=headers)
    if r.status_code == 200:
        print(f"✅ Replied to {to}")
    else:
        print(f"❌ Failed to send: {r.text}")


# Get AI reply from Gemini
def get_ai_reply(history):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={os.getenv('GEMINI_API_KEY')}"
    
    contents = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents
    }
    
    r = requests.post(url, json=payload)
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# Handle incoming message
def handle_incoming(from_number, user_message):
    if from_number not in sessions:
        sessions[from_number] = []

    sessions[from_number].append({"role": "user", "content": user_message})

    # Keep only last 10 messages
    if len(sessions[from_number]) > 10:
        sessions[from_number] = sessions[from_number][-10:]

    try:
        reply = get_ai_reply(sessions[from_number])

        # Handle order tracking
        if "TRACK_ORDER:" in reply:
            order_id = reply.split("TRACK_ORDER:")[1].split("\n")[0].strip()
            status = get_order_status(order_id)
            reply = f"Here's your order status for *{order_id}*:\n\n{status}"

        # Handle escalation
        if "ESCALATE_TO_HUMAN" in reply:
            reply = "I'm connecting you with a human agent right now. Someone will get back to you within 15 minutes. Sorry for the trouble! 🙏"
            print(f"🚨 ESCALATION NEEDED — Customer: {from_number}")
            sessions[from_number] = []

        sessions[from_number].append({"role": "assistant", "content": reply})
        send_message(from_number, reply)

    except Exception as e:
        print(f"AI Error: {e}")
        send_message(from_number, "Sorry, I'm facing some technical issues right now. Please try again in a moment! 🙏")


# Webhook verification
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == os.getenv("VERIFY_TOKEN"):
        print("✅ Webhook verified by Meta!")
        return challenge, 200
    else:
        print("❌ Webhook verification failed")
        return "Forbidden", 403


# Receive messages
@app.route("/webhook", methods=["POST"])
def receive_message():
    try:
        body = request.get_json()
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if messages:
            msg = messages[0]
            if msg.get("type") == "text":
                from_number = msg["from"]
                text = msg["text"]["body"]
                print(f"📩 Message from {from_number}: {text}")
                handle_incoming(from_number, text)

        return "OK", 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return "Error", 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    print(f"🚀 Bot running on port {port}")
    app.run(host="0.0.0.0", port=port)
