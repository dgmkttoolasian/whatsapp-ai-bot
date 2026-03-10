from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
sessions = {}

SYSTEM_PROMPT = """You are a friendly customer care assistant for MyStore, an e-commerce shop.
ABOUT THE STORE:
- We sell electronics and accessories
- Free shipping on orders above Rs.499, otherwise Rs.50 flat
- Delivery in 3-5 business days
- Returns accepted within 7 days (unused items only)
- Payment: UPI, Credit/Debit Card, COD available
- Support hours: 9am to 6pm IST (you handle after hours)
WHAT YOU CAN DO:
1. Answer questions about products, shipping, returns, payments
2. Help customers with order issues
3. Track orders - ask for Order ID, then respond with: TRACK_ORDER:<order_id>
4. Escalate to human if needed - respond with: ESCALATE_TO_HUMAN
ESCALATION RULES:
- Customer asks for human/agent/manager - reply ESCALATE_TO_HUMAN
- Customer is very angry or frustrated - reply ESCALATE_TO_HUMAN
IMPORTANT:
- Keep replies short and friendly
- Reply in the same language the customer uses (Hindi or English)
- Never make up information you do not know"""

def get_order_status(order_id):
    orders = {
        "ORD001": "Packed and ready to ship",
        "ORD002": "Out for delivery - arriving today!",
        "ORD003": "Delivered on March 6th",
        "ORD004": "Return initiated, refund in 3-5 days",
    }
    return orders.get(order_id.upper(), "Order ID not found. Please double-check and try again.")

def get_ai_reply(history):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": "Bearer " + os.getenv("GROQ_API_KEY"),
        "Content-Type": "application/json"
    }
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": 500
    }
    r = requests.post(url, json=payload, headers=headers)
    data = r.json()
    if "choices" not in data:
        print("Groq error: " + str(data))
        return "Sorry, AI is unavailable right now."
    return data["choices"][0]["message"]["content"].strip()

def handle_incoming(from_number, user_message):
    if from_number not in sessions:
        sessions[from_number] = []
    sessions[from_number].append({"role": "user", "content": user_message})
    if len(sessions[from_number]) > 10:
        sessions[from_number] = sessions[from_number][-10:]
    try:
        reply = get_ai_reply(sessions[from_number])
        if "TRACK_ORDER:" in reply:
            order_id = reply.split("TRACK_ORDER:")[1].split("\n")[0].strip()
            status = get_order_status(order_id)
            reply = "Here is your order status for " + order_id + ":\n\n" + status
        if "ESCALATE_TO_HUMAN" in reply:
            reply = "I am connecting you with a human agent right now. Someone will get back to you within 15 minutes. Sorry for the trouble!"
            print("ESCALATION NEEDED - Customer: " + from_number)
            sessions[from_number] = []
        sessions[from_number].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        print("AI Error: " + str(e))
        return "Sorry, I am facing some technical issues right now. Please try again in a moment!"

@app.route("/webhook", methods=["POST"])
def webhook():
    from_number = request.form.get("From", "")
    body = request.form.get("Body", "")
    print("Message from " + from_number + ": " + body)
    reply_text = handle_incoming(from_number, body)
    resp = MessagingResponse()
    resp.message(reply_text)
    return Response(str(resp), mimetype="application/xml")

@app.route("/", methods=["GET"])
def home():
    return "WhatsApp AI Bot is running!", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    print("Bot running on port " + str(port))
    app.run(host="0.0.0.0", port=port)
