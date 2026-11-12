"""Private Telegram commands and activity digest, driven by the elected worker.

Only the configured private chat and matching sender may submit commands.
Update claims, workflow client keys and outbox dedupe survive restarts.
"""
import asyncio
import hashlib
import logging
import os
import re
import time

import httpx
from . import delivery, jobstore as db

_worker = None
_state = 'disabled'
COMMANDS = [
    ('start', 'Connect and show available commands'),
    ('status', 'Current running and queued work'),
    ('tasks', 'Recent workflows and IDs'),
    ('task', 'Queue a new task: /task your instruction'),
    ('run', 'Results and steps: /run workflow-id'),
    ('audit', 'Recent recorded activity'),
    ('pause', 'Pause a workflow'),
    ('resume', 'Resume a paused workflow'),
    ('cancel', 'Cancel a workflow'),
    ('retry', 'Explicitly retry unsuccessful steps'),
    ('help', 'Show commands'),
]
HELP = ('NOVA Telegram\n\n/task <instruction> — queue work (plain text also queues a task)\n'
        '/status — current work\n/tasks — recent workflows and IDs\n'
        '/run <id> — steps and results\n/audit — recent activity\n'
        '/pause <id> · /resume <id> · /cancel <id> · /retry <id>\n\n'
        'Queue updates, results, failures and activity arrive automatically while the backend runs. '
        'Command approvals remain in the workspace.')


def config():
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    user = os.getenv('TELEGRAM_CONTROL_USER_ID', '').strip()
    enabled = os.getenv('TELEGRAM_CONTROL_ENABLED', 'false').lower() == 'true'
    valid = bool(re.fullmatch(r'\d+:[A-Za-z0-9_-]+', token) and re.fullmatch(r'[1-9]\d*', chat) and user)
    identity = hashlib.sha256((token + ':' + chat + ':' + user).encode()).hexdigest()
    return {'enabled': enabled and valid, 'token': token, 'chat': chat, 'user': user, 'identity': identity}


def status():
    return {'configured': config()['enabled'], 'running': bool(_worker and not _worker.done()), 'state': _state}


class TelegramUnavailable(RuntimeError):
    pass


async def api(method, payload=None):
    cfg = config()
    base = os.getenv('TELEGRAM_API_BASE_URL', 'https://api.telegram.org').rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{base}/bot{cfg['token']}/{method}", json=payload or {})
        body = response.json()
        if response.status_code != 200 or not body.get('ok'):
            raise TelegramUnavailable(f'Telegram {method} unavailable (HTTP {response.status_code})')
        return body['result']
    except TelegramUnavailable:
        raise
    except Exception as error:
        # A transport exception can contain the token-bearing request URL.
        raise TelegramUnavailable(f'Telegram {method} unavailable ({type(error).__name__})') from None


def reply(cfg, update_id, body):
    return delivery.queue(cfg['user'], 'Telegram', body, dedupe=f"telegram:{cfg['identity']}:{update_id}",
                          channels=('telegram',), bypass_categories=True)


def summary(run):
    return f"{run['title']} — {run['status']} ({run['completed']}/{run['total']})\nID: {run['id']}"


def activity_line(event):
    payload = event.get('payload') or {}
    detail = payload.get('title') or payload.get('task') or payload.get('tool') or ''
    return f"#{event['id']} {event['created_at']} · {event['kind']} · {event.get('agent_id') or 'NOVA'}" + (f' · {str(detail)[:160]}' if detail else '')


def handle_update(update, cfg=None):
    from . import workflows
    cfg = cfg or config()
    message = update.get('message') or {}
    chat, sender = message.get('chat') or {}, message.get('from') or {}
    if (not cfg['enabled'] or chat.get('type') != 'private' or str(chat.get('id')) != cfg['chat']
            or str(sender.get('id')) != cfg['chat'] or sender.get('is_bot') or 'forward_origin' in message or 'forward_date' in message):
        return False
    prefs = delivery.settings(cfg['user'])
    if not prefs['telegram_enabled'] or prefs['telegram_chat_id'] != cfg['chat']:
        return False
    text = (message.get('text') or '').strip()
    if not text or not isinstance(update.get('update_id'), int):
        return False
    ident = f"telegram-update:{cfg['identity']}:{update['update_id']}"
    def claim(tx):
        if tx.get('migrations', ident):
            return False
        tx.put('migrations', ident, {'id': ident, 'kind': 'telegram_update', 'user_id': cfg['user'], 'status': 'processing', 'created_at': db.now()})
        return True
    if not db.atomic(['migrations'], claim):
        return False  # An ambiguous command is never silently replayed.
    parts = text.split(None, 1)
    head, argument = parts[0], parts[1] if len(parts) > 1 else ''
    command = head.split('@', 1)[0].lower() if text.startswith('/') else '/task'
    argument = argument.strip() if text.startswith('/') else text
    try:
        if command in ('/start', '/help'):
            body = HELP
        elif command in ('/status', '/tasks'):
            runs = db.listing(cfg['user'])
            if command == '/status':
                runs = [r for r in runs if r['status'] not in workflows.TERMINAL]
            body = '\n\n'.join(summary(run) for run in runs[:10]) or 'No current work.'
        elif command == '/audit':
            events = db.recent_events(cfg['user'], 20)
            body = '\n'.join(activity_line(event) for event in reversed(events)) or 'No activity recorded yet.'
        elif command == '/task':
            if not argument or len(argument) > 8000:
                raise ValueError('Use /task followed by an instruction of 1–8000 characters.')
            run = workflows.create(cfg['user'], workflows.BatchInput(title=argument[:160], tasks=[workflows.StepInput(title=argument[:160], instruction=argument)], client_key=f"telegram:{cfg['identity'][:24]}:{update['update_id']}"))
            body = 'Task accepted.\n' + summary(run)
        elif command == '/run':
            run = db.get(argument, cfg['user'])
            if not run:
                raise ValueError('Workflow not found. Use /tasks for its full ID.')
            body = summary(run) + '\n\n' + '\n\n'.join(f"{step['title']} — {step['status']}\n{str(step.get('result') or step.get('error') or '')[:1800]}" for step in run['steps'])
        elif command in ('/pause', '/resume', '/cancel', '/retry'):
            run = workflows.control(cfg['user'], argument, command[1:])
            body = summary(run)
        else:
            body = 'Unknown command. Use /help.'
    except (ValueError, KeyError) as error:
        body = str(error)
    except db.StorageUnavailable:
        raise
    except Exception as error:
        body = f'Command failed ({type(error).__name__}). Check /tasks and Activity before retrying.'
    reply(cfg, update['update_id'], body)
    db.update('migrations', ident, {'status': 'complete'})
    db.event(cfg['user'], 'telegram_command', command=command)
    return True


def digest(cfg):
    ident = 'telegram-audit:' + cfg['identity']
    prior = next(iter(db.records('migrations', id=ident)), None)
    if prior is None:
        recent = db.recent_events(cfg['user'], 1)
        prior = {'id': ident, 'kind': 'telegram_audit_cursor', 'after': recent[0]['id'] if recent else 0}
        db.put('migrations', ident, prior)
    runs = [r for r in db.records('workflows', user_id=cfg['user']) if r['status'] in ('queued', 'running', 'paused', 'interrupted')]
    active = db.records('activity', user_id=cfg['user'], status='working')
    body = '\n'.join(sorted(f"{r['title']} — {r['status']}\nID: {r['id']}" for r in runs[:10])) or 'No current tasks.'
    if active:
        body += '\n\nWorking now:\n' + '\n'.join(sorted(f"{r['agent_id']}: {r['task']}" for r in active[:15]))
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    if prior.get('status_hash') != fingerprint:
        revision = prior.get('status_revision', 0) + 1
        delivery.queue(cfg['user'], 'Current tasks', body, dedupe=f"{ident}:status:{revision}", channels=('telegram',))
        db.update('migrations', ident, {'status_hash': fingerprint, 'status_revision': revision})
    events = db.events(cfg['user'], after=prior['after'], limit=30)
    if not events:
        return
    delivery.queue(cfg['user'], 'Activity audit', '\n'.join(activity_line(e) for e in events),
                   dedupe=f"{ident}:{events[-1]['id']}", channels=('telegram',))
    db.update('migrations', ident, {'after': events[-1]['id']})


async def loop():
    global _state
    cfg = config()
    cursor_id = 'telegram-poll:' + cfg['identity']
    last_digest = 0
    while True:
        try:
            db.assert_lease()
            saved = await asyncio.to_thread(db.records, 'migrations', id=cursor_id)
            if not saved:
                # First activation skips old pending commands rather than running stale work.
                updates = await api('getUpdates', {'offset': -1, 'timeout': 0, 'allowed_updates': ['message']})
                offset = updates[-1]['update_id'] + 1 if updates else 0
                await asyncio.to_thread(db.put, 'migrations', cursor_id, {'id': cursor_id, 'kind': 'telegram_poll_cursor', 'offset': offset})
                await asyncio.to_thread(digest, cfg)
                await asyncio.to_thread(reply, cfg, 'welcome', HELP)
            else:
                offset = saved[0]['offset']
            _state = 'polling'
            updates = await api('getUpdates', {'offset': offset, 'timeout': 10, 'allowed_updates': ['message']})
            for update in updates:
                db.assert_lease()
                await asyncio.to_thread(handle_update, update, cfg)
                await asyncio.to_thread(db.update, 'migrations', cursor_id, {'offset': update['update_id'] + 1})
            if time.monotonic() - last_digest >= 15:
                await asyncio.to_thread(digest, cfg)
                last_digest = time.monotonic()
        except asyncio.CancelledError:
            raise
        except db.LeaseLost:
            _state = 'standby'
            return
        except Exception as error:
            _state = 'unavailable'
            logging.getLogger('nova.telegram').warning('Telegram poll unavailable (%s)', type(error).__name__)
            await asyncio.sleep(5)


def start():
    global _worker, _state
    if config()['enabled'] and (not _worker or _worker.done()):
        _state = 'starting'
        _worker = asyncio.create_task(loop())


async def stop():
    global _worker, _state
    if _worker:
        _worker.cancel()
        await asyncio.gather(_worker, return_exceptions=True)
        _worker = None
    _state = 'disabled'
