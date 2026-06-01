from fastapi import FastAPI
from app.api.runtime import (
    router as runtime_router
)
from app.api.voice import router as voice_router
from app.api.system import router as system_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import (
    router as chat_router
)


app = FastAPI() 
app.include_router(system_router)
app.include_router(runtime_router)
app.include_router(voice_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(
    chat_router
)
@app.get("/")
def root():
    return {
        "status": "Jarvis Online"
    }
    
    