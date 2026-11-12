"""NOVA OS: authenticated API and elected continuous worker on a persistent volume."""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.core.runtime import workflows,jobstore as db
from app.api.nova import router

logging.basicConfig(level=logging.INFO)
# Telegram authenticates in its URL path. Keep transport request URLs out of logs.
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

@asynccontextmanager
async def lifespan(app):
    if db.storage_ready():workflows.start()
    else:logging.getLogger('nova.startup').warning(db.storage_info()['reason'])
    try:yield
    finally:await workflows.stop()

app=FastAPI(title='NOVA OS',version='3.0.0',description='One orchestrator, fourteen specialists. Durable execution and per-user results.',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in os.getenv('CORS_ORIGINS','http://localhost:3000').split(',') if s.strip()],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
app.include_router(router)
@app.exception_handler(db.StorageUnavailable)
async def unavailable_storage(request,error):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503,content={'detail':str(error)})
@app.get('/')
def root():return {'service':'NOVA OS','version':'3.0.0','docs':'/docs'}

def contract():
    if app.openapi_schema:return app.openapi_schema
    schema=get_openapi(title=app.title,version=app.version,description=app.description,routes=app.routes)
    schema['components']['securitySchemes']={'BearerAuth':{'type':'http','scheme':'bearer','description':'Firebase ID token or private APP_TOKEN'}}
    for path,item in schema['paths'].items():
        if path.startswith('/api/') and path not in ('/api/health','/api/system/health','/api/office/roster'):
            for operation in item.values():
                if isinstance(operation,dict):operation['security']=[{'BearerAuth':[]}]
    app.openapi_schema=schema
    return schema

app.openapi=contract
