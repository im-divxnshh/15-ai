"""Current env-stage contract: no SQL fallback, private data or fake live activity."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app
from app.core.runtime import jobstore as db,execution

class ConfigurationGateTests(unittest.TestCase):
    def test_preview_roster_and_health_do_not_open_sqlite_or_start_worker(self):
        with patch.dict(os.environ,{'STORAGE_BACKEND':'upstash','UPSTASH_REDIS_REST_TOKEN':''}),patch.object(db,'command') as sql:
            with TestClient(app) as client:
                roster=client.get('/api/office/roster').json();health=client.get('/api/health').json()
            self.assertEqual(len(roster['agents']),15);self.assertFalse(roster['activity_available'])
            self.assertTrue(all(a['status']=='unavailable' for a in roster['agents']))
            self.assertFalse(health['worker']['running']);self.assertFalse(health['database']['connected'])
            self.assertEqual(health['store']['backend'],'upstash');self.assertTrue(health['store']['implemented']);sql.assert_not_called()

    def test_private_operations_require_identity_then_connected_storage(self):
        with patch.dict(os.environ,{'APP_TOKEN':'configuration-test-token','ALLOW_LOCAL_NO_AUTH':'false','STORAGE_BACKEND':'upstash','UPSTASH_REDIS_REST_TOKEN':''}),patch.object(db,'command') as sql:
            with TestClient(app) as client:
                self.assertEqual(client.get('/api/tasks').status_code,401)
                headers={'Authorization':'Bearer configuration-test-token'}
                self.assertEqual(client.get('/api/session',headers=headers).json()['user_id'],'owner')
                self.assertEqual(client.get('/api/agents',headers=headers).status_code,503)
                self.assertEqual(client.get('/api/files/private.txt',headers=headers).status_code,503)
                self.assertEqual(client.post('/api/workflows',headers=headers,json={'tasks':[{'title':'Task','instruction':'Work'}]}).status_code,503)
            sql.assert_not_called()

    def test_public_roster_is_public_in_the_api_contract(self):
        contract=app.openapi()
        self.assertNotIn('security',contract['paths']['/api/office/roster']['get'])
        self.assertEqual(contract['paths']['/api/session']['get']['security'],[{'BearerAuth':[]}])

    def test_groq_model_fields_select_orchestrator_and_specialists(self):
        with patch.dict(os.environ,{'NOVA_LLM_MODEL':'nova-model','GROQ_MODEL':'specialist-model'},clear=True):
            self.assertEqual(execution.model('nova'),'nova-model')
            self.assertEqual(execution.model('michel'),'specialist-model')

if __name__=='__main__':unittest.main()
