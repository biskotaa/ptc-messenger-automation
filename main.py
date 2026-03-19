import os
import re
from fastapi import FastAPI, Request, Query, HTTPException, Response
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
import requests

from langchain_openai import ChatOpenAI
from langchain_classic.memory import ConversationBufferWindowMemory
from langchain_classic.chains import ConversationChain

load_dotenv()

app = FastAPI(title="Messenger Automation Webhook")

FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")

# In-memory session store
sessions = {}

def get_session_memory(session_id: str):
    if session_id not in sessions:
        # According to standard setup
        sessions[session_id] = ConversationBufferWindowMemory(k=10) # 10 exchanges
    return sessions[session_id]

# The AI Model
if OPENAI_API_KEY:
    kwargs = {"model": "gpt-4o-mini", "api_key": OPENAI_API_KEY}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    llm = ChatOpenAI(**kwargs)
else:
    llm = None
    print("Warning: OPENAI_API_KEY is not set. AI model will not function.")

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Facebook Webhook Verification Endpoint
    """
    if hub_mode == "subscribe":
        if hub_verify_token == FB_VERIFY_TOKEN:
            print("Webhook verified successfully!")
            return Response(content=hub_challenge, media_type="text/plain")
        else:
            raise HTTPException(status_code=403, detail="Verification token mismatch")
            
    return Response(content="Ready", media_type="text/plain")

@app.post("/webhook")
async def process_webhook(request: Request):
    """
    Process inbound messages from Messenger
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Check if object is page
    if body.get("object") != "page":
        return Response(status_code=404)
        
    for entry in body.get("entry", []):
        # Determine if it's a comment event (feed)
        # Check changes[0].field == 'feed'
        changes = entry.get("changes", [])
        if changes:
            if changes[0].get("field") == "feed":
                print("Ignored 'feed' event")
                continue
                
        # the messaging branch
        messaging = entry.get("messaging", [])
        for event in messaging:
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            message_text = message.get("text")
            
            if sender_id and message_text:
                await handle_incoming_message(sender_id, message_text)
                
    return Response(status_code=200, content="EVENT_RECEIVED", media_type="text/plain")

async def handle_incoming_message(sender_id: str, text: str):
    print(f"Received message from {sender_id}: {text}")
    
    if not llm:
        print("Error: OpenAI is not configured.")
        return

    # Use Langchain AI Agent
    memory = get_session_memory(sender_id)
    conversation = ConversationChain(
        llm=llm,
        memory=memory,
        verbose=False
    )
    
    try:
        # Process with LLM
        response = conversation.predict(input=text)
    except Exception as e:
        print(f"OpenAI error: {e}")
        response = "I'm sorry, I'm having trouble processing your request right now."
        
    # Post-process message
    cleaned_reply = clean_ai_response(response)
    print(f"Cleaned reply to {sender_id}: {cleaned_reply}")
    
    # Send the response back to Facebook
    send_facebook_message(sender_id, cleaned_reply)

def clean_ai_response(text: str) -> str:
    """
    Matches the JS Logic:
    const cleanedText = text.replace(/^Conversation ID: [a-z0-9-]+\n+/i, '');
    return cleanedText.trim();
    And Edit Fields: output.replace(/\\n/g, ' ')
    """
    # 1. Remove 'Conversation ID: ...' at the beginning of string, case insensitive
    text = re.sub(r'(?i)^Conversation ID: [a-z0-9-]+\n+', '', text)
    # 2. Trim whitespace
    text = text.strip()
    # 3. Replace all newlines with a single space
    text = text.replace('\n', ' ')
    return text

def send_facebook_message(recipient_id: str, message_text: str):
    """
    Sends back the message via Facebook Graph API
    """
    if not FB_PAGE_ACCESS_TOKEN:
        print("Warning: FB_PAGE_ACCESS_TOKEN not set. Message not sent.")
        return

    url = "https://graph.facebook.com/v24.0/me/messages"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FB_PAGE_ACCESS_TOKEN}"
    }
    
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Message sent successfully to {recipient_id}")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error sending message: {e}")
        error_msg = e.response.json() if e.response else "Unknown"
        print(f"Error details: {error_msg}")
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
