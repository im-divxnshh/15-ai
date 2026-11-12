"""Validate and enable the private Telegram control bot without printing secrets."""
import argparse
import asyncio
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import set_key
from app.core.runtime import delivery, jobstore as db, telegram


async def setup(args):
    os.environ['TELEGRAM_CONTROL_USER_ID'] = args.user
    os.environ['TELEGRAM_CONTROL_ENABLED'] = 'true'
    cfg = telegram.config()
    if not cfg['enabled']:
        print('Set a valid TELEGRAM_BOT_TOKEN and a positive private TELEGRAM_CHAT_ID in backend/.env first.')
        return 1
    try:
        bot = await telegram.api('getMe')
        chat = await telegram.api('getChat', {'chat_id': cfg['chat']})
        webhook = await telegram.api('getWebhookInfo')
        if chat.get('type') != 'private' or str(chat.get('id')) != cfg['chat']:
            print('Control commands require your personal private chat with the bot. Group chats are not supported.')
            return 1
        if webhook.get('url'):
            print('This bot has an active webhook. Use a dedicated bot or remove that webhook before enabling polling.')
            return 1
        print('Telegram accepted the bot and private chat: @' + bot['username'])
        if not args.enable:
            print('Validation only. Run with --enable to connect this chat to the selected workspace account.')
            return 0
        await telegram.api('setMyCommands', {'commands': [{'command': name, 'description': description} for name, description in telegram.COMMANDS], 'scope': {'type': 'chat', 'chat_id': int(cfg['chat'])}})
        prefs = delivery.settings(args.user)
        prefs.pop('connections', None)
        prefs.update(telegram_chat_id=cfg['chat'], telegram_enabled=True, categories=delivery.CATEGORIES.copy())
        delivery.save_settings(args.user, prefs)
        env = Path(__file__).resolve().parents[1] / '.env'
        set_key(env, 'TELEGRAM_CONTROL_USER_ID', args.user)
        set_key(env, 'TELEGRAM_CONTROL_ENABLED', 'true')
        print('Telegram commands and all notification categories enabled for the selected workspace account.')
        print('Restart the backend, then send /start, /status or /task Write a three-point daily plan to the bot.')
        print('The backend skips old pending commands on first activation. Send new commands after it starts.')
        return 0
    except (telegram.TelegramUnavailable, db.StorageUnavailable) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print('Setup unavailable (' + type(error).__name__ + '). No token was printed.', file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable', action='store_true', help='Save bot menu, workspace preferences and local control configuration')
    parser.add_argument('--user', default='owner', help='owner for APP_TOKEN login, or the exact Firebase UID used in the frontend')
    return asyncio.run(setup(parser.parse_args()))


if __name__ == '__main__':
    sys.exit(main())
