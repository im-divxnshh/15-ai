"""Run NOVA against the local Postman Groq member; never sends notifications."""
import asyncio
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.runtime import workflows,execution,provider,jobstore as db
from storage_fixtures import StorageFixtures

async def main():
    base=os.environ['NOVA_SIMULATION_URL'].rstrip('/')
    if not base.startswith(('http://127.0.0.1:','http://localhost:')):raise ValueError('Only local simulation URLs are allowed')
    os.environ.update(GROQ_BASE_URL=base+'/groq/openai/v1',GROQ_API_KEY='simulation-only',SMTP_HOST='',SMTP_USER='',SMTP_PASSWORD='',TELEGRAM_BOT_TOKEN='')
    provider.BACKOFF=.001
    fixture=StorageFixtures().start()
    try:
        reply=await execution.respond('simulation','TOOL_REQUEST','friday')
        assert reply.reply.startswith('Simulated verification reply:'),reply
        assert db.events('simulation')[-1]['kind']=='agent_completed'
        req=workflows.BatchInput(tasks=[workflows.StepInput(title='Fail',instruction='FAIL_PROVIDER',agent_id='friday'),workflows.StepInput(title='Dependent',instruction='Summarize',agent_id='friday')])
        run=workflows.create('simulation',req)
        for _ in range(300):
            await workflows.tick();await asyncio.sleep(.01)
            result=db.get(run['id'])
            if result['status']=='failed':break
        assert result['status']=='failed',result
        assert [s['status'] for s in result['steps']]==['failed','skipped'],result
        print(json.dumps({'passed':True,'checks':['Actual tool creation through provider HTTP','Provider 503 failure and skipped dependent'],'scope':'Local Postman Groq stand-in; storage SDKs are disposable fixtures. No live services verified.'}))
    finally:
        await workflows.stop();fixture.stop()

if __name__=='__main__':asyncio.run(main())
