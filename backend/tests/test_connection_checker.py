"""Local checker-policy tests. No real service access or credentials are used."""
import importlib.util
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('connection_checker',Path(__file__).resolve().parents[2]/'scripts/check_connections.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

class ConnectionCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.report=Path(self.temp.name)/'report.json'
        self.env={key:'test-value' for keys in checker.REQUIRED.values() for key in keys}
        self.env.update(STORAGE_BACKEND='upstash',FILE_STORAGE_BACKEND='r2')

    def run_cli(self,*args,probe=None):
        with patch.object(checker,'REPORT',self.report),patch.object(checker,'values',return_value=self.env),patch.object(checker,'validate_application',return_value=[]),patch.object(checker,'record_progress') as progress,patch.object(checker,'probe',side_effect=probe) as call,patch('sys.argv',['check_connections.py',*args]),patch('builtins.print'):
            result=checker.main()
        return result,call,progress

    def passed_report(self):
        return {'version':checker.CHECK_VERSION,'checked_at':datetime.now(timezone.utc).isoformat(),'mode':'live','fingerprint':checker.fingerprint(self.env),'passed':True,'checks':{service:{'status':'passed'} for service in checker.REQUIRED if service!='telegram'}}

    def test_default_probes_six_services_and_never_telegram(self):
        code,probe,progress=self.run_cli(probe=lambda service,env:{'status':'passed','detail':'SIMULATED local test'})
        self.assertEqual(code,0)
        self.assertEqual({call.args[0] for call in probe.call_args_list},set(checker.REQUIRED)-{'telegram'})
        report=json.loads(self.report.read_text())
        self.assertEqual(report['checks']['telegram']['status'],'deferred');self.assertEqual(len(report['required_services']),6)
        progress.assert_called_once()

    def test_deferred_telegram_can_change_without_invalidating_six_service_gate(self):
        self.report.write_text(json.dumps(self.passed_report()))
        self.env['TELEGRAM_BOT_TOKEN']='changed-later'
        code,probe,_=self.run_cli('--require-verified')
        self.assertEqual(code,0);probe.assert_not_called()
        code,_,_=self.run_cli('--require-verified','--include-telegram')
        self.assertEqual(code,1)

    def test_failed_stale_offline_and_changed_configuration_cannot_unlock_builds(self):
        for change in ('failed','stale','offline','changed'):
            with self.subTest(change=change):
                report=self.passed_report()
                if change=='failed':report['checks']['email']['status']='failed';report['passed']=False
                elif change=='stale':report['checked_at']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
                elif change=='offline':report['mode']='offline'
                else:report['fingerprint']='old-config'
                self.report.write_text(json.dumps(report));code,probe,_=self.run_cli('--require-verified')
                self.assertEqual(code,1);probe.assert_not_called()

    def test_explicit_telegram_check_requires_matching_telegram_credentials(self):
        report=self.passed_report();report['checks']['telegram']={'status':'passed'};report['telegram_fingerprint']=checker.telegram_fingerprint(self.env)
        self.report.write_text(json.dumps(report))
        self.assertEqual(self.run_cli('--require-verified','--include-telegram')[0],0)
        self.env['TELEGRAM_CHAT_ID']='new-chat'
        self.assertEqual(self.run_cli('--require-verified','--include-telegram')[0],1)

if __name__=='__main__':unittest.main()
