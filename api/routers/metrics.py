import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from api.auth import verify_token
from api.deps import get_db
from core.monitoring import render_prometheus


router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/api/metrics", response_class=PlainTextResponse)
def metrics(db: sqlite3.Connection = Depends(get_db)):
    return PlainTextResponse(
        render_prometheus(db),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
