"""FastAPI 앱: REST API와 정적 파일 서빙.

실행: uv run uvicorn server.main:app --host 127.0.0.1 --port 8765
앱 자체에는 인증이 없다. 반드시 127.0.0.1에만 바인딩한다.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Iterator

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .prices import collect

WEB_DIR = db.ROOT / "web"
SYMBOLS = db.ROOT / "data" / "symbols.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = db.connect()
    try:
        db.init(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="내 리밸런싱 보드", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def get_conn() -> Iterator[Any]:
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


class PortfolioIn(BaseModel):
    doc: dict[str, Any]
    version: int


NO_STORE = {"Cache-Control": "no-store"}


@app.get("/api/portfolio")
def get_portfolio(conn=Depends(get_conn)):
    doc, version = db.get_portfolio(conn)
    db.log_usage(conn, "open")
    return JSONResponse({"doc": doc, "version": version}, headers=NO_STORE)


@app.put("/api/portfolio")
def put_portfolio(body: PortfolioIn, conn=Depends(get_conn)):
    if not isinstance(body.doc.get("assets"), list):
        return JSONResponse({"detail": "doc.assets가 목록이어야 합니다."}, status_code=422)
    new_version = db.put_portfolio(conn, body.doc, body.version)
    if new_version is None:
        doc, version = db.get_portfolio(conn)
        return JSONResponse({"doc": doc, "version": version}, status_code=409, headers=NO_STORE)
    db.log_usage(conn, "save")
    return JSONResponse({"version": new_version}, headers=NO_STORE)


@app.get("/api/prices")
def get_prices(conn=Depends(get_conn)):
    doc, _ = db.get_portfolio(conn)
    return JSONResponse(db.latest_prices(conn, doc), headers=NO_STORE)


@app.post("/api/prices/refresh")
def refresh_prices(conn=Depends(get_conn)):
    """가격 수집을 지금 실행한다. 결과(성공·실패 종목)와 갱신된 가격 문서를 돌려준다."""
    result = collect.run(conn)
    doc, _ = db.get_portfolio(conn)
    return JSONResponse({**result, "prices": db.latest_prices(conn, doc)}, headers=NO_STORE)


@app.get("/api/symbols")
def get_symbols():
    # 목록은 드물게 바뀐다. 하루 캐시하고, 그 뒤에는 ETag로 변경 여부만 확인한다.
    return FileResponse(SYMBOLS, media_type="application/json", headers={"Cache-Control": "private, max-age=86400"})


@app.middleware("http")
async def static_no_cache(request, call_next):
    """빌드 없는 정적 파일이라 파일명에 해시가 없다. 매번 변경 여부를 확인하게 한다."""
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
