from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, chat, events, users

app = FastAPI(title="Planorama API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
async def read_root():
    return {"message": "Planorama API"}
