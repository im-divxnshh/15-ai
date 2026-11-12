"""Exercise the real bot HTTP client/outbox against a local Postman listener."""
import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.runtime import delivery, jobstore as db, telegram
from storage_fixtures import StorageFixtures


async def main():
    base = os.environ['NOVA_SIMULATION_URL'].rstrip('/')
    if not base.startswith(('http://127.0.0.1:', 'http://localhost:')):
        raise ValueError('Only a local simulation URL is allowed')
    os.environ.update(TELEGRAM_API_BASE_URL=base + '/telegram', TELEGRAM_BOT_TOKEN='123456:test-token', TELEGRAM_CHAT_ID='12345', TELEGRAM_CONTROL_USER_ID='simulation', TELEGRAM_CONTROL_ENABLED='true')
    fixture = StorageFixtures().start()
    try:
        delivery.save_settings('simulation', {'email': '', 'email_enabled': False, 'telegram_chat_id': '12345', 'telegram_enabled': True, 'categories': delivery.CATEGORIES.copy()})
        assert (await telegram.api('getMe'))['is_bot']
        assert (await telegram.api('getChat', {'chat_id': '12345'}))['type'] == 'private'
        assert not (await telegram.api('getWebhookInfo'))['url']
        assert await telegram.api('setMyCommands', {'commands': [{'command': c, 'description': d} for c, d in telegram.COMMANDS]})
        updates = await telegram.api('getUpdates', {'offset': 0, 'timeout': 0, 'allowed_updates': ['message']})
        assert telegram.handle_update(updates[0])
        assert not telegram.handle_update(updates[0])
        assert len(db.listing('simulation')) == 1
        assert await telegram.api('getUpdates', {'offset': updates[0]['update_id'] + 1, 'timeout': 0, 'allowed_updates': ['message']}) == []
        await delivery.tick()
        assert all(row['status'] == 'sent' for row in delivery.history('simulation'))
        delivery.queue('simulation', 'Failure', 'FAIL_TELEGRAM', channels=('telegram',))
        await delivery.tick()
        assert delivery.history('simulation')[0]['status'] == 'retrying'
        telegram.digest(telegram.config())
        db.event('simulation', 'step_started', title='Study tips', agent_id='friday')
        telegram.digest(telegram.config())
        await delivery.tick()
        assert delivery.history('simulation')[0]['status'] == 'sent'
        print(json.dumps({'passed': True, 'checks': ['Bot identity/chat/menu HTTP', 'Incoming task and duplicate protection', 'Offset acknowledgement', 'Actual outbox HTTP sends', '503 recorded for bounded retry', 'Automatic activity audit delivery'], 'scope': 'Local Postman Telegram stand-in and disposable storage; no live notifications.'}))
    finally:
        fixture.stop()


if __name__ == '__main__':
    asyncio.run(main())
