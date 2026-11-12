"""One bounded live Groq smoke completion; no user data or notifications."""
import asyncio
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import provider,execution

async def main():
    try:
        result=await asyncio.wait_for(provider.request([{'role':'user','content':'For a connection verification, reply with exactly: NOVA verification passed'}],execution.model('nova')),timeout=120)
        if not (result.get('content') or '').strip():raise provider.ProviderError('No verification content')
        print('Live Groq completion passed for the selected NOVA model. No user history or notification was created.')
        return 0
    except Exception as error:
        print(f'Live Groq completion failed ({type(error).__name__}).')
        return 1

if __name__=='__main__':sys.exit(asyncio.run(main()))
