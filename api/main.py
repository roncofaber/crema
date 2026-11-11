import asyncio
from contextlib import asynccontextmanager, suppress
import os
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from api.auth import auth_mode, cors_origins, session_cookie_secure, session_secret, session_ttl, validate_auth_configuration, verify_token
from api.routers import auth as auth_router
from api.routers import health, users, brews, stats, status, kiosk as kiosk_router
from api.routers import metrics as metrics_router
from api.schemas import RootResponse
import core.kiosk as kiosk
import core.db as db
from core import monitoring


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_configuration()
    db.init_db()
    start_hardware = os.getenv("CREMA_START_HARDWARE") == "1"
    start_simulator = os.getenv("CREMA_DEV_SIMULATOR") == "1"
    if start_hardware and start_simulator:
        raise RuntimeError("The development simulator cannot run with hardware ownership enabled")
    if start_simulator:
        import devsim
        devsim.start()
    elif start_hardware:
        kiosk.start()
    broadcaster = asyncio.create_task(kiosk.broadcast_loop())
    try:
        yield
    finally:
        broadcaster.cancel()
        with suppress(asyncio.CancelledError):
            await broadcaster
        if start_hardware or start_simulator:
            kiosk.stop()


app = FastAPI(title="CREMA API", lifespan=lifespan)


def _route_template(request: Request) -> str | None:
    effective_route = request.scope.get("fastapi", {}).get("effective_route_context")
    if effective_route is not None:
        return effective_route.path_format
    return getattr(request.scope.get("route"), "path", None)


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        monitoring.record_http_request(request.method, _route_template(request), 500)
        raise
    monitoring.record_http_request(request.method, _route_template(request), response.status_code)
    return response


if auth_mode() == "session":
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        session_cookie="crema_session",
        max_age=session_ttl(),
        same_site="strict",
        https_only=session_cookie_secure(),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

_auth = [Depends(verify_token)]

app.include_router(users.router,  prefix="/users",  tags=["users"],  dependencies=_auth)
app.include_router(brews.router,  prefix="/brews",  tags=["brews"],  dependencies=_auth)
app.include_router(stats.router,  prefix="/stats",  tags=["stats"],  dependencies=_auth)
app.include_router(status.router,                   tags=["status"], dependencies=_auth)
app.include_router(auth_router.router)
app.include_router(health.router,                   tags=["health"])
app.include_router(metrics_router.router, tags=["monitoring"])
app.include_router(kiosk_router.router, tags=["kiosk"])
if os.getenv("CREMA_DEV_SIMULATOR") == "1":
    import devsim
    app.include_router(devsim.router())


@app.get("/", response_model=RootResponse)
def root():
    return {"status": "ok"}


_DIST = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.isdir(_DIST):
    @app.get("/kiosk", include_in_schema=False)
    def serve_kiosk():
        return FileResponse(os.path.join(_DIST, "index.html"))

    app.mount("/ui", StaticFiles(directory=_DIST, html=True), name="dashboard")
else:
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "dashboard/dist/ not found — /kiosk and /ui will 404. Run: npm run build in dashboard/"
    )
