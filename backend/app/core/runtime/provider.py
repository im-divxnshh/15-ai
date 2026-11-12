"""Groq-only OpenAI-compatible client; safe errors and bounded HTTP retries."""
import asyncio
import json
import os
import httpx

class ProviderError(RuntimeError):pass
MAX_ATTEMPTS=3
BACKOFF=1.0


async def request(messages,model=None,tools=None):
    key=os.getenv('GROQ_API_KEY','').strip()
    if not key or key.lower().startswith(('your','placeholder','changeme')):raise ProviderError('GROQ_API_KEY is missing. Configure the backend to execute AI work.')
    # A local override is used by contract tests. Production defaults to Groq.
    base=os.getenv('GROQ_BASE_URL','https://api.groq.com/openai/v1').rstrip('/')
    payload={'model':model or os.getenv('GROQ_MODEL','openai/gpt-oss-20b'),'messages':messages,'temperature':0.35}
    if tools:payload['tools']=tools
    for attempt in range(MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                res=await client.post(base+'/chat/completions',headers={'Authorization':f'Bearer {key}'},json=payload)
            if res.status_code in (401,403):raise ProviderError('Groq rejected the API key. Check GROQ_API_KEY.')
            if res.status_code in (408,429,500,502,503,504):
                if attempt+1==MAX_ATTEMPTS:raise ProviderError(f'Groq temporarily unavailable (HTTP {res.status_code}). Explicit retry is available.')
            elif res.status_code>=400:raise ProviderError(f'Groq request rejected (HTTP {res.status_code}). Check model and provider settings.')
            else:
                try:
                    message=res.json()['choices'][0]['message']
                    if not isinstance(message,dict) or message.get('content') is not None and not isinstance(message.get('content'),str) or message.get('tool_calls') is not None and not isinstance(message.get('tool_calls'),list):raise ValueError('Invalid message')
                    return message
                except (ValueError,KeyError,IndexError,TypeError):raise ProviderError('Groq returned an invalid response.') from None
        except (httpx.TimeoutException,httpx.HTTPError) as exc:
            if attempt+1==MAX_ATTEMPTS:raise ProviderError(f'Groq connection failed ({type(exc).__name__}).') from None
        await asyncio.sleep(BACKOFF*(attempt+1))


async def complete(messages,model=None):
    result=await request(messages,model)
    content=result.get('content')
    if not isinstance(content,str) or not content.strip():raise ProviderError('Groq returned no answer.')
    return content.strip()


def extract_json(text):
    cleaned=text.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
    try:return json.loads(cleaned)
    except ValueError:
        try:return json.loads(cleaned[cleaned.index('{'):cleaned.rindex('}')+1])
        except (ValueError,TypeError):raise ProviderError('NOVA could not produce a valid plan. Enter explicit tasks or retry planning.') from None
