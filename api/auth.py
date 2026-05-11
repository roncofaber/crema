import os
from fastapi import Header, HTTPException

_TOKEN = os.getenv("CREMA_API_TOKEN", "")


async def verify_token(authorization: str | None = Header(None)):
    if not _TOKEN:
        return  # auth disabled when env var not set
    if authorization != f"Bearer {_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
