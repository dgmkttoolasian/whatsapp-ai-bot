from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os
import json
import base64
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
sessions = {}

SYSTEM_PROMPT = """You are a helpful and friendly customer care assistant for ToolAsian (Shri Sadhi Krupa Polysacks), a manufacturer of industrial and retail packaging bags based in Ahmedabad, Gujarat, India.

ABOUT THE COMPANY:
- Company: ToolAsian (Shri Sadhi Krupa Polysacks)
- Location: Naroda GIDC, Ahmedabad, Gujarat, India
- Website: toolasian.com
- We export to USA, UK, UAE, Africa, South America, Korea and more

PRODUCTS WE MANUFACTURE:
- PP Woven Bags: Made from polypropylene woven fabric. Strong and durable. Used for cement, fertilizer, food grains, agriculture products
- BOPP Printed Bags: High-quality glossy printed bags for branded retail and premium packaging
- Paper Laminated Bags: Kraft paper outer with woven inner layer. Used for cement and chemical packaging
- Non-Woven Bags: Used for retail, gifting, grocery, and promotional purposes
- HDPE/LD Film Rolls: Used as inner liners or standalone packaging films for industrial and agricultural products
- Back Seam Bags: Stitched along back seam, flat clean surface ideal for full-face printing
- Poly-coated Papers: For industrial packaging needs

INDUSTRIES WE SERVE:
Cement, fertilizer, food and agriculture, chemicals, construction, retail, and export industries

CUSTOMIZATION:
- Custom multicolor BOPP printing, metallic lamination, logo branding available
- Bags can be customized in size, weight capacity, color, and print design
- Samples available before bulk orders

PRICING AND ORDERS:
- MOQ depends on product type - team will confirm minimum quantity
- Prices depend on product type, size, quantity, and printing - custom quote provided
- Payment terms discussed based on order size and location

DELIVERY AND EXPORT:
- Production lead time: 2 to 4 weeks depending on quantity and customization
- International shipping via sea freight for bulk, air freight when required
- Can work with customer preferred freight forwarder

HOW TO HANDLE CUSTOMER REQUESTS:
1. Quote requests: Ask for their name, company name, product needed, quantity, and destination country
2. Bulk orders: Ask for name, company, product needed, then say team will follow up
3. Catalogue requests: Ask for their email address and say team will send it right away
4. Call requests: Ask for name and phone number and say team will call shortly
5. Sample requests: Ask for their requirement details and shipping address

ESCALATION RULES:
- If customer wants to speak to a human, wants a call back, or is frustrated - respond with exactly: ESCALATE_TO_HUMAN
- If customer shares their contact details for follow up - respond with exactly: ESCALATE_TO_HUMAN

LEAD CAPTURE - VERY IMPORTANT:
Whenever a customer asks for a quote, price, catalogue, sample, or wants to place an order - collect these details one by one:
1. Their name
2. Company name
3. Product they need
4. Quantity required
5. Destination (city and country)
Then say: Thank you! Our sales team will contact you within 24 hours with a custom quote.
Then respond with: ESCALATE_TO_HUMAN

IMPORTANT RULES:
- Always be polite, professional, and helpful
- Reply in the same language the customer uses (Hindi, Gujarati, or English)
- Never make up prices or delivery dates - always say team will confirm
- Keep replies short and clear
- If you do not know something, say our team will get back to you shortly"""


def get_google_creds():
    creds_json = os.getenv("GOOGLE_CREDS_JSON")
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/gmail.send"
        ]
    )
    return creds


def log_to_sheet(phone, conversation):
    try:
        creds = get_google_creds()
        service = build("sheets", "v4", credentials=creds)
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values = [[timestamp, phone, conversation, "Yes", "New Lead"]]
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Sheet1!A:E",
            valueInputOption="RAW",
            body={"values": values}
        ).execute()
        print("Lead logged to Google Sheet")
    except Exception as e:
        print("Sheet error: " + str(e))


def send_email(phone, conversation):
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        sender = os.getenv("NOTIFY_EMAIL")
        password = os.getenv("EMAIL_PASSWORD")
        receiver = os.getenv("NOTIFY_EMAIL")

        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = "New Lead from WhatsApp - ToolAsian Bot"

        body = "New lead received!\n\nCustomer Phone: " + phone + "\n\nConversation:\n" + conversation + "\n\nCheck your Google Sheet for all leads."
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print("Email sent to " + receiver)
    except Exception as e:
        print("Email error: " + str(e))                                                                                                                                                                                                                                       


def get_conversation_summary(from_number):
    history = sessions.get(from_number, [])
    summary = ""
    for msg in history:
        role = "Customer" if msg["role"] == "user" else "Bot"
        summary += role + ": " + msg["content"] + "\n"
    return summary


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
        if "ESCALATE_TO_HUMAN" in reply:
            conversation = get_conversation_summary(from_number)
            log_to_sheet(from_number, conversation)
            send_email(from_number, conversation)
            reply = "Thank you! Our sales team will contact you within 24 hours. For urgent queries call us directly at +91-XXXXXXXXXX"
            print("Lead captured for: " + from_number)
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
