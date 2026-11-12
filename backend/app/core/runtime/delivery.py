"""Persistent email/Telegram outbox with bounded retries and honest connection tests."""
import asyncio
import hashlib
import json
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
import httpx
from . import jobstore as db,tls

CATEGORIES=['updates','results','failures','replies','reminders','summaries']
_worker=None


def configured(value):return bool(str(value or '').strip()) and not any(s in str(value).lower() for s in ('your_','your-','placeholder','changeme','example.com','...'))


def ready():return {'email':all(configured(os.getenv(k)) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD')),'telegram':configured(os.getenv('TELEGRAM_BOT_TOKEN'))}


def fingerprint(channel):
    names=('SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM') if channel=='email' else ('TELEGRAM_BOT_TOKEN',)
    return hashlib.sha256('|'.join(os.getenv(k,'') for k in names).encode()).hexdigest()


def settings(user):
    rows=db.records('delivery_settings',user_id=user)
    tests=db.records('connection_tests',user_id=user)
    prefs=dict(rows[0]) if rows else {'email':os.getenv('NOTIFY_EMAIL',''),'telegram_chat_id':os.getenv('TELEGRAM_CHAT_ID',''),'email_enabled':False,'telegram_enabled':False,'categories':CATEGORIES.copy()}
    prefs.pop('user_id',None)
    connections={}
    for channel in ('email','telegram'):
        prefs[channel+'_enabled']=bool(prefs[channel+'_enabled']);dest=prefs['email' if channel=='email' else 'telegram_chat_id']
        test=next((t for t in tests if t['channel']==channel and t['destination']==dest and t['fingerprint']==fingerprint(channel)),None)
        connections[channel]={'configured':ready()[channel],'verified':bool(test),'tested_at':test['tested_at'] if test else None}
    return {**prefs,'connections':connections}


def save_settings(user,prefs):
    def save(tx):
        tx.put('delivery_settings',db.user_key(user),{'user_id':user,**prefs})
        for row in tx.rows('deliveries',user_id=user,status='blocked'):row.update(status='pending',next_attempt=0)
    db.atomic(['delivery_settings','deliveries'],save)
    return settings(user)


def queue(user,title,body,category='updates',is_test=False,dedupe=None,channels=None,bypass_categories=False):
    import uuid
    notice=db.user_key(user+':'+dedupe) if dedupe else str(uuid.uuid4())
    ids={channel:db.next_id('delivery') for channel in ('email','telegram')}
    def enqueue(tx):
        if tx.get('notices',notice):return []
        tx.put('notices',notice,{'id':notice,'user_id':user,'title':title[:200],'body':body[:18000],'read_at':None,'category':category,'created_at':db.now(),'is_test':is_test})
        prefs=tx.get('delivery_settings',db.user_key(user)) or {'categories':CATEGORIES,'email_enabled':False,'telegram_enabled':False}
        if not is_test and not bypass_categories and category not in prefs['categories']:return []
        out=[]
        for channel in ('email','telegram'):
            if channels is not None and channel not in channels:continue
            if not prefs[channel+'_enabled']:continue
            dest=prefs['email' if channel=='email' else 'telegram_chat_id'];ident=ids[channel]
            tx.put('deliveries',ident,{'id':ident,'user_id':user,'channel':channel,'title':title[:200],'body':body[:18000],'status':'pending','created_at':db.now(),'is_test':is_test,'destination':dest,'attempts':0,'next_attempt':0,'sent_at':None,'error':None});out.append(ident)
        return out
    return db.atomic(['delivery_settings','deliveries','notices'],enqueue)


def history(user):return sorted(db.records('deliveries',user_id=user),key=lambda r:r['id'],reverse=True)[:100]


def retry(user,ident):
    def reset(tx):
        row=tx.get('deliveries',ident)
        if not row or row['user_id']!=user or row['status'] not in ('failed','blocked','interrupted','disabled'):return False
        prefs=tx.get('delivery_settings',db.user_key(user)) or {}
        row.update(status='pending',attempts=0,next_attempt=0,error=None,destination=prefs.get('email' if row['channel']=='email' else 'telegram_chat_id',''));return True
    return db.atomic(['deliveries','delivery_settings'],reset)


def email(to,title,body):
    msg=EmailMessage();msg['Subject']='NOVA · '+title;msg['From']=os.getenv('SMTP_FROM') or os.getenv('SMTP_USER');msg['To']=to;msg.set_content(body)
    port=int(os.getenv('SMTP_PORT','587'));secure=port==465
    cls=smtplib.SMTP_SSL if secure else smtplib.SMTP
    with cls(os.getenv('SMTP_HOST'),port,timeout=20,**({'context':tls.context()} if secure else {})) as smtp:
        if not secure:smtp.starttls(context=tls.context())
        smtp.login(os.getenv('SMTP_USER'),os.getenv('SMTP_PASSWORD'))
        if smtp.send_message(msg):raise smtplib.SMTPRecipientsRefused({to:'rejected'})


async def send(row):
    prefs=settings(row['user_id']);channel=row['channel'];dest=row['destination']
    if not prefs[channel+'_enabled']:return 'disabled','Channel disabled'
    if dest!=prefs['email' if channel=='email' else 'telegram_chat_id']:return 'blocked','Destination changed. Explicit retry sends this message to the current destination.'
    if not dest or not ready()[channel]:return 'blocked','Add SMTP sender settings and email destination' if channel=='email' else 'Create a Telegram bot, set its token, and connect a chat ID'
    accepted=0
    try:
        if channel=='email':await asyncio.to_thread(email,dest,row['title'],row['body'])
        else:
            base=os.getenv('TELEGRAM_API_BASE_URL','https://api.telegram.org').rstrip('/')
            async with httpx.AsyncClient(timeout=20) as client:
                text='NOVA · '+row['title']+'\n\n'+row['body']
                for start in range(0,len(text),3900):
                    res=await client.post(f"{base}/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage",json={'chat_id':dest,'text':text[start:start+3900]})
                    if res.status_code==429 or res.status_code>=500:
                        return ('interrupted' if accepted else 'retrying'),f'Telegram transient failure (HTTP {res.status_code})'+('; earlier message parts were accepted. Confirm receipt before retry.' if accepted else '')
                    if res.status_code>=400 or not res.json().get('ok'):
                        return ('interrupted' if accepted else 'failed'),f'Telegram rejected delivery (HTTP {res.status_code}); check bot/chat permissions'
                    accepted+=1
        return 'sent',None
    except (smtplib.SMTPAuthenticationError,smtplib.SMTPRecipientsRefused):return 'failed','SMTP rejected sender credentials or recipient'
    except (httpx.ConnectError,httpx.ConnectTimeout,ConnectionRefusedError) as exc:
        return ('interrupted' if accepted else 'retrying'),f'{channel.title()} connection failure ({type(exc).__name__})'
    except smtplib.SMTPResponseException as exc:
        return ('retrying' if 400<=exc.smtp_code<500 else 'failed'),f'SMTP rejected delivery (code {exc.smtp_code})'
    except Exception as exc:
        # A lost acknowledgement may follow successful delivery. Do not replay it.
        return 'interrupted',f'{channel.title()} outcome uncertain ({type(exc).__name__}); confirm receipt before explicit retry'


async def tick():
    rows=sorted([r for r in db.records('deliveries') if r['status'] in ('pending','blocked','retrying') and r['next_attempt']<=time.time()],key=lambda r:r['id'])[:12]
    for row in rows:
        if not db.update('deliveries',row['id'],{'status':'sending'},status=row['status']):continue
        db.assert_lease()
        state,error=await send(row);attempts=row['attempts']+(state not in ('blocked','disabled'))
        if state=='retrying' and attempts>=3:state='failed'
        def finish(tx):
            current=tx.get('deliveries',row['id'])
            if current['status']!='sending':return
            current.update(status=state,attempts=attempts,error=error,next_attempt=time.time()+(30 if state=='blocked' else 15*2**attempts),sent_at=db.now() if state=='sent' else None)
            if state=='sent' and row['is_test']:
                tx.put('connection_tests',db.user_key(row['user_id'])+':'+row['channel'],{'user_id':row['user_id'],'channel':row['channel'],'destination':row['destination'],'fingerprint':fingerprint(row['channel']),'tested_at':db.now()})
        db.atomic(['deliveries','connection_tests'],finish)


async def loop():
    while True:
        try:await tick()
        except asyncio.CancelledError:raise
        except Exception:
            import logging;logging.getLogger('nova.delivery').exception('Outbox tick failed')
        await asyncio.sleep(2)


def start():
    global _worker
    if not _worker or _worker.done():_worker=asyncio.create_task(loop())


async def stop():
    global _worker
    if _worker:_worker.cancel();await asyncio.gather(_worker,return_exceptions=True);_worker=None
