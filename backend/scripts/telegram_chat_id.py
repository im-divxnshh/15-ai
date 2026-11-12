"""Discover chat IDs after starting your Telegram bot. Never print its token."""
import json
import os
from pathlib import Path
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1]/'.env')

def main():
    token=os.getenv('TELEGRAM_BOT_TOKEN','').strip()
    if not token or token.startswith(('your','placeholder')):
        print('Set TELEGRAM_BOT_TOKEN in backend/.env first.',file=sys.stderr);return 1
    try:
        with httpx.Client(timeout=20) as client:
            response=client.get(f'https://api.telegram.org/bot{token}/getUpdates',params={'timeout':0,'allowed_updates':json.dumps(['message'])})
        if response.status_code==409:
            print('Another getUpdates poller or webhook is connected. Disconnect it before discovering this chat ID.',file=sys.stderr);return 1
        if response.status_code!=200 or not response.json().get('ok'):
            print(f'Telegram rejected the lookup (HTTP {response.status_code}). Check the token and bot settings.',file=sys.stderr);return 1
        chats={m['chat']['id']:m['chat'] for update in response.json()['result'] if (m:=update.get('message'))}
        if not chats:
            print('No conversations found. Open your bot, tap Start, send a message, then run this command again.');return 0
        for ident,chat in chats.items():
            print(f"Chat ID: {ident} · {chat.get('title') or chat.get('first_name') or chat.get('username') or chat.get('type')}")
        print('Paste your chat ID into Delivery in NOVA OS. Save and test the connection.');return 0
    except Exception as exc:
        print(f'Lookup failed ({type(exc).__name__}). Check connectivity and bot configuration.',file=sys.stderr);return 1

if __name__=='__main__':sys.exit(main())
