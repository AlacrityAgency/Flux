"""The local account-backed workspace API."""
from fastapi import APIRouter, HTTPException, Query

from flux.local_agents.runtime import ChatSpec, TurnSpec


def mount_local_api(app, runtime, static_dir):
    router = APIRouter(prefix="/api/local")

    @router.get("/status")
    async def status(refresh: bool = False):
        return await runtime.status(refresh)

    @router.get("/chats")
    async def chats():
        return runtime.chats()

    @router.get("/usage")
    async def usage(refresh: bool = False):
        return await runtime.quota(refresh)

    @router.get('/notebooks')
    async def notebooks():
        try:
            return await runtime.notebooks()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.post("/chats", status_code=201)
    async def new_chat(spec: ChatSpec):
        return runtime.create_chat(spec)

    @router.get("/chats/{ident}")
    async def chat(ident: str):
        try:
            return runtime.chat(ident)
        except KeyError:
            raise HTTPException(404, "گفتگو پیدا نشد.")

    @router.post("/chats/{ident}/turns", status_code=202)
    async def submit(ident: str, spec: TurnSpec):
        try:
            return runtime.submit(ident, spec)
        except KeyError:
            raise HTTPException(404, "گفتگو پیدا نشد.")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.get("/turns/{ident}")
    async def turn(ident: str):
        try:
            return runtime.turn(ident)
        except KeyError:
            raise HTTPException(404, "اجرا پیدا نشد.")

    @router.get("/turns/{ident}/events")
    async def events(ident: str, after: int = Query(0, ge=0)):
        try:
            return runtime.events(ident, after)
        except KeyError:
            raise HTTPException(404, "اجرا پیدا نشد.")

    @router.post("/turns/{ident}/cancel")
    async def cancel(ident: str):
        try:
            return await runtime.cancel(ident)
        except KeyError:
            raise HTTPException(404, "اجرا پیدا نشد.")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    app.include_router(router)
