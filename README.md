# PTC Messenger Automation

This is a Python-based webhook server implementing Facebook Messenger automation, originally migrated from an n8n workflow. It uses FastAPI for the web server and LangChain with OpenAI's `gpt-4o-mini` for processing inbound messages.

## Setup

1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment:
   - Windows: `.\venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in your keys.

## Running the Server

```bash
uvicorn main:app --reload
```

## Features
- Webhook verification endpoint for Facebook Messenger.
- Filtering out of `feed` (comment) events.
- Processing messages using LangChain's `ConversationChain`.
- Memory storage mapped to Messenger sender IDs.
- Post-processing to clean up AI formatting and trailing `Conversation ID:` fields.
- Sending replies back via Facebook Graph API.
