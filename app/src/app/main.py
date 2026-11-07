import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated

import boto3
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel


class Item(BaseModel):
    id: int
    name: str


ITEMS = {
    1: Item(id=1, name="alpha"),
    2: Item(id=2, name="beta"),
}

DOCS_ENABLED = os.environ.get("APP_ENABLE_DOCS") == "true"


def load_api_key() -> str:
    secret_id = os.environ.get("APP_SECRET_ID")
    if secret_id:
        response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)
        return response["SecretString"]

    api_key = os.environ.get("APP_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set APP_SECRET_ID (Secrets Manager) or APP_API_KEY (local only)"
        )
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.api_key = load_api_key()
    yield


app = FastAPI(
    title="backend-api",
    lifespan=lifespan,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


def require_api_key(request: Request, x_api_key: Annotated[str, Header()] = "") -> None:
    if not hmac.compare_digest(x_api_key.encode(), request.app.state.api_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/items", dependencies=[Depends(require_api_key)])
def list_items() -> list[Item]:
    return list(ITEMS.values())


@app.get("/api/v1/items/{item_id}", dependencies=[Depends(require_api_key)])
def get_item(item_id: int) -> Item:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item
