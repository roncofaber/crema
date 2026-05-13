import asyncio
import os
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.auth import verify_token
from api.routers import users, brews, stats, status, kiosk as kiosk_router
import core.kiosk as kiosk

app = FastAPI(title="CREMA API")

@app.on_event("startup")
async def _start_kiosk_broadcaster():
    asyncio.create_task(kiosk.broadcast_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth = [Depends(verify_token)]

app.include_router(users.router,  prefix="/users",  tags=["users"],  dependencies=_auth)
app.include_router(brews.router,  prefix="/brews",  tags=["brews"],  dependencies=_auth)
app.include_router(stats.router,  prefix="/stats",  tags=["stats"],  dependencies=_auth)
app.include_router(status.router,                   tags=["status"], dependencies=_auth)
app.include_router(kiosk_router.router, tags=["kiosk"])


@app.get("/")
def root():
    return {"status": "ok"}


_DIST = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.isdir(_DIST):
    app.mount("/ui", StaticFiles(directory=_DIST, html=True), name="dashboard")
