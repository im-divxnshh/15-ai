"""Private bot authorization, replay protection and HTTP dependency checks."""
import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.runtime import delivery, jobstore as db, telegram, workflows
from storage_fixtures import StorageFixtures


class TelegramTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': '123456:test-token', 'TELEGRAM_CHAT_ID': '12345', 'TELEGRAM_CONTROL_USER_ID': 'one', 'TELEGRAM_CONTROL_ENABLED': 'true', 'SMTP_HOST': '', 'SMTP_USER': '', 'SMTP_PASSWORD': ''})
        self.env.start()
        self.storage = StorageFixtures().start()
        delivery.save_settings('one', {'email': '', 'email_enabled': False, 'telegram_chat_id': '12345', 'telegram_enabled': True, 'categories': delivery.CATEGORIES.copy()})

    async def asyncTearDown(self):
        await telegram.stop()
        self.storage.stop()
        self.env.stop()

    def update(self, text, ident=1, chat=12345, sender=12345, kind='private'):
        return {'update_id': ident, 'message': {'text': text, 'chat': {'id': chat, 'type': kind}, 'from': {'id': sender}}}

    async def test_private_sender_and_disabled_destination_boundaries(self):
        for update in (self.update('/task forbidden', chat=777), self.update('/task forbidden', sender=777), self.update('/task forbidden', kind='group')):
            self.assertFalse(telegram.handle_update(update))
        forwarded = self.update('/task forwarded');forwarded['message']['forward_origin'] = {'type': 'user'}
        self.assertFalse(telegram.handle_update(forwarded))
        prefs = delivery.settings('one');prefs.pop('connections');prefs['telegram_enabled'] = False;delivery.save_settings('one', prefs)
        self.assertFalse(telegram.handle_update(self.update('/task disabled')))
        self.assertEqual(db.listing('one'), [])

    async def test_plain_text_submission_deduplicates_and_scopes(self):
        update = self.update('Write three study tips')
        self.assertTrue(telegram.handle_update(update))
        self.assertFalse(telegram.handle_update(update))
        self.assertEqual(len(db.listing('one')), 1)
        self.assertEqual(db.listing('two'), [])
        self.assertIn('Write three study tips', db.listing('one')[0]['steps'][0]['instruction'])

    async def test_control_replay_and_other_user_run_denied(self):
        run = workflows.create('one', workflows.BatchInput(tasks=[workflows.StepInput(title='Work', instruction='Draft a plan')]))
        update = self.update('/pause ' + run['id'])
        self.assertTrue(telegram.handle_update(update))
        self.assertFalse(telegram.handle_update(update))
        self.assertEqual(db.get(run['id'], 'one')['status'], 'paused')
        private = workflows.create('two', workflows.BatchInput(tasks=[workflows.StepInput(title='Private', instruction='Other user data')]))
        telegram.handle_update(self.update('/run ' + private['id'], 2))
        self.assertIn('Workflow not found', delivery.history('one')[0]['body'])

    async def test_ambiguous_claim_never_replays_and_command_reply_telegram_only(self):
        cfg = telegram.config();ident = 'telegram-update:' + cfg['identity'] + ':1'
        db.put('migrations', ident, {'id': ident, 'kind': 'telegram_update', 'status': 'processing'})
        self.assertFalse(telegram.handle_update(self.update('/task uncertain')))
        prefs = delivery.settings('one');prefs.pop('connections');prefs.update(email='a@local.test', email_enabled=True, categories=[]);delivery.save_settings('one', prefs)
        self.assertTrue(telegram.handle_update(self.update('/help', 2)))
        rows = delivery.history('one')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['channel'], 'telegram')

    async def test_audit_cursor_deduplicates_and_omits_raw_tool_payload(self):
        cfg = telegram.config()
        db.event('one', 'old_activity');telegram.digest(cfg)
        db.event('two', 'private_other_user', secret='hidden')
        db.event('one', 'tool_completed', agent_id='friday', tool='create_task', result={'secret': 'omit-me'})
        telegram.digest(cfg);telegram.digest(cfg)
        rows = delivery.history('one')
        self.assertEqual(len(rows), 1)
        self.assertIn('tool_completed', rows[0]['body'])
        self.assertNotIn('omit-me', rows[0]['body'])
        self.assertNotIn('private_other_user', rows[0]['body'])

    async def test_group_chat_configuration_cannot_enable_control(self):
        with patch.dict(os.environ, {'TELEGRAM_CHAT_ID': '-12345'}):
            self.assertFalse(telegram.config()['enabled'])


if __name__ == '__main__':
    unittest.main()
