from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import users, brews, stats, status

app = FastAPI(title="CREMA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router,  prefix="/users",  tags=["users"])
app.include_router(brews.router,  prefix="/brews",  tags=["brews"])
app.include_router(stats.router,  prefix="/stats",  tags=["stats"])
app.include_router(status.router,                   tags=["status"])


@app.get("/")
def root():
    return {"status": "ok"}
