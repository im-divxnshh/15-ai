"""Regressions for the observed SMTP trust and browser fixture CORS failures."""
import os
from pathlib import Path
import ssl
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.runtime import tls


class VerificationSupportTests(unittest.TestCase):
    def test_tls_context_has_trusted_roots_and_enforces_identity(self):
        context=tls.context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
        self.assertGreater(context.cert_store_stats()['x509_ca'],0)

    def test_browser_health_preserves_cors_and_fixture_identity(self):
        # A fresh process isolates the disposable fixture's environment/SDK patches.
        code="""
import sys
sys.path.insert(0,'backend');sys.path.insert(0,'backend/tests')
from browser_server import app
from fastapi.testclient import TestClient
with TestClient(app) as client:
    origin='http://127.0.0.1:13000'
    response=client.get('/api/health',headers={'Origin':origin})
    assert response.status_code==200
    assert response.json()['verification']=='simulated-disposable-harness'
    assert response.headers['access-control-allow-origin']==origin
    assert response.headers['access-control-allow-credentials']=='true'
    response=client.get('/api/health',headers={'Origin':'http://untrusted.invalid'})
    assert 'access-control-allow-origin' not in response.headers
"""
        env={**os.environ,'CORS_ORIGINS':'http://127.0.0.1:13000'}
        result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
