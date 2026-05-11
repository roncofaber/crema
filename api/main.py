from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.auth import verify_token
from api.routers import users, brews, stats, status

app = FastAPI(title="CREMA API")

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


@app.get("/")
def root():
    return {"status": "ok"}
