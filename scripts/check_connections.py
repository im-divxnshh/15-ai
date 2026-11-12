#!/usr/bin/env python3
"""Validate both env files and check real service access without printing secrets.

This does not start workers, write application data, run an AI completion,
send notifications, or build the application. SQLite is never imported.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import hmac
import json
import logging
import re
import smtplib
import ssl
from pathlib import Path
import sys
from urllib.parse import urlsplit,quote

import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.runtime import tls
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
REQUIRED={
    'groq':['GROQ_API_KEY','GROQ_MODEL','NOVA_LLM_MODEL'],
    'upstash':['UPSTASH_REDIS_REST_URL','UPSTASH_REDIS_REST_TOKEN'],
    'firebase':['FIREBASE_CREDENTIALS','FIREBASE_PROJECT_ID','SYSTEM_ACCESS_USER_ID','NEXT_PUBLIC_FIREBASE_API_KEY','NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN','NEXT_PUBLIC_FIREBASE_PROJECT_ID','NEXT_PUBLIC_FIREBASE_APP_ID'],
    'neon':['NEON_URL'],
    'r2':['R2_ACCOUNT_ID','R2_ACCESS_KEY_ID','R2_SECRET_ACCESS_KEY','R2_BUCKET'],
    'email':['NOTIFY_EMAIL','SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM'],
    'telegram':['TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'],
}

def present(value):
    value=str(value or '').strip().lower()
    return bool(value) and not value.startswith(('your','placeholder','changeme')) and '...' not in value

def values():
    private=dotenv_values(ROOT/'backend/.env');public=dotenv_values(ROOT/'frontend/.env.local')
    result={**private,**public}
    result['GROQ_BASE_URL']='https://api.groq.com/openai/v1'
    return result

def validate_application(env):
    problems=[]
    if env.get('STORAGE_BACKEND')!='upstash':problems.append('STORAGE_BACKEND must be upstash')
    if env.get('FILE_STORAGE_BACKEND')!='r2':problems.append('FILE_STORAGE_BACKEND must be r2')
    try:
        backend=urlsplit(env.get('NEXT_PUBLIC_BACKEND_URL') or '')
        if backend.scheme not in ('http','https') or not backend.hostname or backend.username or backend.password or backend.query or backend.fragment or backend.path not in ('','/'):
            problems.append('NEXT_PUBLIC_BACKEND_URL must be the HTTP(S) backend origin')
        origins=[origin.strip() for origin in (env.get('CORS_ORIGINS') or '').split(',') if origin.strip()]
        if not origins:problems.append('CORS_ORIGINS must include your frontend origin')
        for origin in origins:
            parsed=urlsplit(origin)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
                problems.append('CORS_ORIGINS must contain HTTP(S) origins without paths or a trailing slash');break
        domain=env.get('NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN') or ''
        if not domain or '/' in domain or ':' in domain or any(c.isspace() for c in domain):problems.append('NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN must be a hostname')
        if not re.fullmatch(r'1:\d+:web:[A-Za-z0-9]+',env.get('NEXT_PUBLIC_FIREBASE_APP_ID') or ''):problems.append('NEXT_PUBLIC_FIREBASE_APP_ID must be your Firebase web app ID')
    except ValueError:problems.append('An application URL has invalid formatting')
    return problems

def validate(service,env):
    missing=[key for key in REQUIRED[service] if not present(env.get(key))]
    if missing:return 'Fill '+', '.join(missing)
    if service=='upstash':
        url=urlsplit(env['UPSTASH_REDIS_REST_URL'])
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:return 'Use the HTTPS Redis REST URL from the Upstash console'
    if service=='neon':
        url=urlsplit(env['NEON_URL'])
        if url.scheme not in ('postgres','postgresql') or not url.hostname or not url.username or not url.password or not url.path.strip('/'):return 'Use the complete PostgreSQL connection string from Neon'
    if service=='firebase':
        try:
            info=json.loads(env['FIREBASE_CREDENTIALS'])
            if info.get('type')!='service_account' or not info.get('private_key') or not info.get('client_email'):return 'Use valid inline Firebase Admin service-account JSON'
            projects=[info.get('project_id'),env['FIREBASE_PROJECT_ID'],env['NEXT_PUBLIC_FIREBASE_PROJECT_ID']]
            if len(set(projects))!=1:return 'Firebase Admin, backend and frontend must use the same project ID'
        except (ValueError,TypeError,AttributeError):return 'FIREBASE_CREDENTIALS must be valid one-line JSON; no JSON file is required'
    if service=='r2':
        if not re.fullmatch(r'[a-fA-F0-9]{32}',env['R2_ACCOUNT_ID']):return 'R2_ACCOUNT_ID must be the Cloudflare account ID (32 hexadecimal characters)'
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',env['R2_BUCKET']):return 'Use the actual R2 bucket name'
    if service=='email':
        try:
            if not 1<=int(env['SMTP_PORT'])<=65535:return 'SMTP_PORT must be a valid TCP port'
        except ValueError:return 'SMTP_PORT must be a number'
        for key in ('NOTIFY_EMAIL','SMTP_FROM'):
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',env[key]):return key+' must contain an email address'
        if '://' in env['SMTP_HOST']:return 'SMTP_HOST must be a hostname, without https://'
    if service=='telegram':
        if not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',env['TELEGRAM_BOT_TOKEN']):return 'TELEGRAM_BOT_TOKEN must be the token issued by BotFather'
        if not re.fullmatch(r'-?\d+',env['TELEGRAM_CHAT_ID']):return 'TELEGRAM_CHAT_ID must be a numeric chat ID'
    return None


def r2_head_bucket(env):
    """SigV4-authenticated HEAD. No files, buckets or user data are written."""
    host=env['R2_ACCOUNT_ID']+'.r2.cloudflarestorage.com'
    path='/'+quote(env['R2_BUCKET'],safe='')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');day=stamp[:8]
    empty=hashlib.sha256(b'').hexdigest();signed='host;x-amz-content-sha256;x-amz-date'
    headers={'host':host,'x-amz-content-sha256':empty,'x-amz-date':stamp}
    canonical='HEAD\n'+path+'\n\n'+''.join(key+':'+headers[key]+'\n' for key in signed.split(';'))+'\n'+signed+'\n'+empty
    scope=day+'/auto/s3/aws4_request'
    signing='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest()
    key=('AWS4'+env['R2_SECRET_ACCESS_KEY']).encode()
    for part in (day,'auto','s3','aws4_request'):key=hmac.new(key,part.encode(),hashlib.sha256).digest()
    signature=hmac.new(key,signing.encode(),hashlib.sha256).hexdigest()
    headers['Authorization']='AWS4-HMAC-SHA256 Credential='+env['R2_ACCESS_KEY_ID']+'/'+scope+', SignedHeaders='+signed+', Signature='+signature
    with httpx.Client(timeout=8) as client:return client.head('https://'+host+path,headers=headers).status_code

def failure_detail(service,error):
    if service=='firebase' and type(error).__name__=='RefreshError':
        data=next((arg for arg in error.args if isinstance(arg,dict)),{})
        code=data.get('error')
        message=str(data.get('error_description') or (error.args[0] if error.args else '')).lower()
        if 'invalid jwt signature' in message:
            return 'Firebase rejected the service-account JWT signature. Replace FIREBASE_CREDENTIALS with a current key for that service account.'
        if 'account not found' in message or 'has been deleted' in message:
            return 'Firebase service account was not found. Check the account and use its current Admin credentials.'
        if 'disabled' in message:
            return 'Firebase service account is disabled. Enable the intended account or use an active account.'
        if 'invalid jwt' in message and any(term in message for term in ('timeframe','iat','exp','short-lived')):
            return 'Firebase rejected JWT timing. Check the system date/time and automatic clock synchronization.'
        if code in ('invalid_grant','invalid_client','unauthorized_client','invalid_scope','access_denied'):
            return f'Firebase rejected service-account token refresh ({code}). Check the account/key status, permissions and system time.'
        return 'Firebase service-account token refresh failed. Check the account/key status and system time.'
    if service=='email' and isinstance(error,ssl.SSLCertVerificationError):
        return 'SMTP certificate verification failed. Check SMTP_HOST and the trusted CA bundle; TLS verification remains enabled.'
    return f'{service} connection unavailable ({type(error).__name__}); check credentials and network access'

def probe(service,env):
    problem=validate(service,env)
    if problem:return {'status':'missing','detail':problem}
    try:
        if service=='groq':
            with httpx.Client(timeout=8) as client:
                response=client.get(env['GROQ_BASE_URL'].rstrip('/')+'/models',headers={'Authorization':'Bearer '+env['GROQ_API_KEY']})
            if response.status_code!=200:return {'status':'failed','detail':f'Groq rejected the connection (HTTP {response.status_code})'}
            models={row['id'] for row in response.json()['data']}
            selected={env[k] for k in ('GROQ_MODEL','NOVA_LLM_MODEL')}
            selected.update(v for k,v in env.items() if k.endswith('_LLM_MODEL') and present(v))
            if not selected<=models:return {'status':'failed','detail':'One or more selected model IDs are not advertised by Groq'}
            detail='Groq key authenticated and selected models advertised. AI task execution has not been tested.'
        elif service=='upstash':
            with httpx.Client(timeout=8) as client:
                response=client.post(env['UPSTASH_REDIS_REST_URL'].rstrip('/'),headers={'Authorization':'Bearer '+env['UPSTASH_REDIS_REST_TOKEN']},json=['PING'])
            if response.status_code!=200 or response.json().get('result')!='PONG':return {'status':'failed','detail':f'Upstash PING rejected (HTTP {response.status_code})'}
            detail='Upstash Redis REST PING succeeded. Queue transactions and execution require separate integration verification.'
        elif service=='neon':
            import psycopg
            with psycopg.connect(env['NEON_URL'],connect_timeout=8,sslmode='require') as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1, EXISTS(SELECT 1 FROM pg_available_extensions WHERE name='vector'), EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
                    connected,available,installed=cursor.fetchone()
            if connected!=1 or not available:return {'status':'failed','detail':'Neon connected, but pgvector is unavailable for the selected RAG design'}
            detail='Neon SELECT 1 succeeded; pgvector '+('is enabled.' if installed else 'is available and will be enabled by the schema migration.')
        elif service=='r2':
            status=r2_head_bucket(env)
            if status!=200:return {'status':'failed','detail':f'R2 bucket access rejected (HTTP {status}); check account, bucket and key permissions'}
            detail='R2 bucket HEAD succeeded. File upload permissions and application integration are not yet verified.'
        elif service=='email':
            port=int(env['SMTP_PORT']);secure=port==465;context=tls.context()
            cls=smtplib.SMTP_SSL if secure else smtplib.SMTP
            with cls(env['SMTP_HOST'],port,timeout=8,**({'context':context} if secure else {})) as smtp:
                if not secure:smtp.starttls(context=context)
                smtp.login(env['SMTP_USER'],env['SMTP_PASSWORD']);code,_=smtp.noop()
                if code!=250:return {'status':'failed','detail':'SMTP authenticated, but connection verification failed'}
            detail='SMTP TLS authentication succeeded. No email was sent; delivery and sender acceptance remain unverified.'
        elif service=='telegram':
            base='https://api.telegram.org/bot'+env['TELEGRAM_BOT_TOKEN']
            with httpx.Client(timeout=8) as client:
                identity=client.get(base+'/getMe');chat=client.get(base+'/getChat',params={'chat_id':env['TELEGRAM_CHAT_ID']})
            if identity.status_code!=200 or not identity.json().get('ok'):return {'status':'failed','detail':f'Telegram bot authentication rejected (HTTP {identity.status_code})'}
            if chat.status_code!=200 or not chat.json().get('ok'):return {'status':'failed','detail':f'Telegram chat is unavailable (HTTP {chat.status_code}); Start the bot and check the chat ID'}
            detail='Telegram bot/chat lookup succeeded. No message was sent; delivery remains unverified.'
        else:
            from google.oauth2.service_account import Credentials
            from google.auth.transport.requests import Request
            from google.cloud import firestore
            class BoundedRequest(Request):
                def __call__(self,*args,**kwargs):
                    kwargs['timeout']=8;return super().__call__(*args,**kwargs)
            credentials=Credentials.from_service_account_info(json.loads(env['FIREBASE_CREDENTIALS']),scopes=['https://www.googleapis.com/auth/datastore','https://www.googleapis.com/auth/cloud-platform'])
            credentials.refresh(BoundedRequest())
            database=firestore.Client(project=env['FIREBASE_PROJECT_ID'],credentials=credentials)
            try:
                # A read-only query verifies Firestore access; no contents are logged.
                list(database.collection('_nova_connection_check').limit(1).stream(timeout=8,retry=None))
            finally:database.close()
            with httpx.Client(timeout=8) as client:
                response=client.get('https://identitytoolkit.googleapis.com/v1/projects',params={'key':env['NEXT_PUBLIC_FIREBASE_API_KEY']})
                owner=client.post('https://identitytoolkit.googleapis.com/v1/projects/'+quote(env['FIREBASE_PROJECT_ID'],safe='')+'/accounts:lookup',headers={'Authorization':'Bearer '+credentials.token},json={'localId':[env['SYSTEM_ACCESS_USER_ID']]})
            if response.status_code!=200:return {'status':'failed','detail':f'Firebase Admin connected, but the public Auth API key failed (HTTP {response.status_code})'}
            if owner.status_code!=200 or not owner.json().get('users'):return {'status':'failed','detail':'Firebase owner UID lookup failed; SYSTEM_ACCESS_USER_ID must be an existing user in this Firebase project'}
            detail='Firebase Admin/Firestore access succeeded; public Auth config and owner UID were verified and project IDs match. Google user sign-in is not yet tested.'
        return {'status':'passed','detail':detail}
    except Exception as error:
        # Exceptions can contain passwords, connection strings or bot URLs.
        return {'status':'failed','detail':failure_detail(service,error)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',action='store_true',help='Inspect configuration without contacting services')
    parser.add_argument('--include-telegram',action='store_true',help='Also test the optional Telegram access connection')
    args=parser.parse_args();env=values()
    problems=validate_application(env)
    if problems:
        for problem in problems:print('Application configuration: '+problem)
        return 1
    required=[service for service in REQUIRED if service!='telegram' or args.include_telegram]
    if args.offline:checks={s:{'status':'missing' if (problem:=validate(s,env)) else 'unverified','detail':problem or 'Values present; no live connection attempted'} for s in required}
    else:
        with ThreadPoolExecutor(max_workers=4) as executor:
            checks=dict(zip(required,executor.map(lambda service:probe(service,env),required)))
    passed=all(check['status']==('unverified' if args.offline else 'passed') for check in checks.values())
    if not args.include_telegram:checks['telegram']={'status':'deferred','detail':'Optional Telegram access probe not requested. Use --include-telegram; bot activation is separate.'}
    for service,check in checks.items():print(f"{service}: {check['status']} — {check['detail']}")
    if args.offline:
        print('Configuration values checked; no live access was attempted.')
    else:
        print('Service access checks passed.' if passed else 'Some services need attention; see the results above.')
    return 0 if passed else 1

if __name__=='__main__':sys.exit(main())
