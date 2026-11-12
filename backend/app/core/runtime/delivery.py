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
from . import jobstore as db

CATEGORIES=['updates','results','failures','replies','reminders','summaries']
_worker=None


def configured(value):return bool(str(value or '').strip()) and not any(s in str(value).lower() for s in ('your_','your-','placeholder','changeme','example.com','...'))


def ready():return {'email':all(configured(os.getenv(k)) for k in ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD')),'telegram':configured(os.getenv('TELEGRAM_BOT_TOKEN'))}


def fingerprint(channel):
    names=('SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD','SMTP_FROM') if channel=='email' else ('TELEGRAM_BOT_TOKEN',)
    return hashlib.sha256('|'.join(os.getenv(k,'') for k in names).encode()).hexdigest()


def settings(user):
    with db.connect() as c:
        row=c.execute('SELECT * FROM delivery_settings WHERE user_id=?',(user,)).fetchone()
        tests=c.execute('SELECT * FROM connection_tests WHERE user_id=?',(user,)).fetchall()
    # Default destination is not auto-enabled for a new account: user explicitly saves preferences.
    prefs=dict(row) if row else {'email':os.getenv('NOTIFY_EMAIL','divyansh20060@gmail.com'),'telegram_chat_id':os.getenv('TELEGRAM_CHAT_ID',''),'email_enabled':False,'telegram_enabled':False,'categories':json.dumps(CATEGORIES)}
    prefs.pop('user_id',None);prefs['categories']=json.loads(prefs['categories'])
    connections={}
    for channel in ('email','telegram'):
        prefs[channel+'_enabled']=bool(prefs[channel+'_enabled']);dest=prefs['email' if channel=='email' else 'telegram_chat_id']
        test=next((t for t in tests if t['channel']==channel and t['destination']==dest and t['fingerprint']==fingerprint(channel)),None)
        connections[channel]={'configured':ready()[channel],'verified':bool(test),'tested_at':test['tested_at'] if test else None}
    return {**prefs,'connections':connections}


def save_settings(user,prefs):
    with db.connect() as c:
        c.execute('INSERT INTO delivery_settings VALUES(?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET email=excluded.email,telegram_chat_id=excluded.telegram_chat_id,email_enabled=excluded.email_enabled,telegram_enabled=excluded.telegram_enabled,categories=excluded.categories',(user,prefs['email'],prefs['telegram_chat_id'],prefs['email_enabled'],prefs['telegram_enabled'],json.dumps(prefs['categories'])))
        c.execute("UPDATE deliveries SET status='pending',next_attempt=0 WHERE user_id=? AND status='blocked'",(user,))
    return settings(user)


def queue(user,title,body,category='updates',is_test=False):
    if not is_test:
        from . import repository as repo
        repo.put(user,'notification',{'title':title[:200],'body':body[:18000],'read_at':None,'category':category})
    prefs=settings(user);ids=[]
    if not is_test and category not in prefs['categories']:return ids
    with db.connect() as c:
        for channel in ('email','telegram'):
            if not prefs[channel+'_enabled']:continue
            dest=prefs['email' if channel=='email' else 'telegram_chat_id']
            cur=c.execute('INSERT INTO deliveries(user_id,channel,title,body,status,created_at,is_test,destination) VALUES(?,?,?,?,?,?,?,?)',(user,channel,title[:200],body[:18000],'pending',db.now(),is_test,dest));ids.append(cur.lastrowid)
    return ids


def history(user):
    with db.connect() as c:return [dict(r) for r in c.execute('SELECT * FROM deliveries WHERE user_id=? ORDER BY id DESC LIMIT 100',(user,))]


def email(to,title,body):
    msg=EmailMessage();msg['Subject']='NOVA · '+title;msg['From']=os.getenv('SMTP_FROM') or os.getenv('SMTP_USER');msg['To']=to;msg.set_content(body)
    port=int(os.getenv('SMTP_PORT','587'));secure=port==465
    cls=smtplib.SMTP_SSL if secure else smtplib.SMTP
    with cls(os.getenv('SMTP_HOST'),port,timeout=20,**({'context':ssl.create_default_context()} if secure else {})) as smtp:
        if not secure:smtp.starttls(context=ssl.create_default_context())
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
    with db.connect() as c:rows=c.execute("SELECT * FROM deliveries WHERE status IN ('pending','blocked','retrying') AND next_attempt<=? ORDER BY id LIMIT 12",(time.time(),)).fetchall()
    for raw in rows:
        row=dict(raw)
        with db.connect() as c:
            if not c.execute("UPDATE deliveries SET status='sending' WHERE id=? AND status IN ('pending','blocked','retrying')",(row['id'],)).rowcount:continue
        state,error=await send(row);attempts=row['attempts']+(state not in ('blocked','disabled'))
        if state=='retrying' and attempts>=3:state='failed'
        dest=row['destination']
        with db.connect() as c:
            c.execute('UPDATE deliveries SET status=?,attempts=?,error=?,next_attempt=?,sent_at=?,destination=? WHERE id=?',(state,attempts,error,time.time()+(30 if state=='blocked' else 15*2**attempts),db.now() if state=='sent' else None,dest,row['id']))
            if state=='sent' and row['is_test']:c.execute('INSERT OR REPLACE INTO connection_tests VALUES(?,?,?,?,?)',(row['user_id'],row['channel'],dest,fingerprint(row['channel']),db.now()))


async def loop():
    while True:
        try:await tick()
        except asyncio.CancelledError:raise
        except Exception:
            import logging;logging.getLogger('nova.delivery').exception('Outbox tick failed')
        await asyncio.sleep(2)


def start():
    global _worker
    with db.connect() as c:c.execute("UPDATE deliveries SET status='interrupted',error='Server restarted during sending; confirm receipt before explicit retry' WHERE status='sending'")
    _worker=asyncio.create_task(loop())


async def stop():
    global _worker
    if _worker:_worker.cancel();await asyncio.gather(_worker,return_exceptions=True);_worker=None
