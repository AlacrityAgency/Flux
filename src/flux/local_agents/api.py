"""The local account-backed workspace API."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from flux.local_agents.runtime import ChatSpec, TurnSpec
from pydantic import BaseModel, Field, field_validator


class KeyRequest(BaseModel):
    provider: Literal["gemini", "groq", "openrouter", "together"] = "gemini"
    api_key: str = Field(max_length=250, repr=False)


class ChatPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    archived: bool | None = None

    @field_validator("title")
    @classmethod
    def not_blank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("عنوان نباید خالی باشد.")
        return value


class ProbeRequest(BaseModel):
    provider: Literal["codex", "claude", "gemini", "gemini-api", "gapcode", "antigravity"]
    model: str = Field(default="", max_length=100, pattern=r"^[A-Za-z0-9_.:/-]*$")


class WebSessionRequest(BaseModel):
    path: str = Field(min_length=1,max_length=1000)


def mount_local_api(app, runtime, static_dir):
    router = APIRouter(prefix="/api/local")

    @router.put('/connections/web/{provider}')
    async def web_import(provider: str, payload: WebSessionRequest):
        from flux.local_agents.web_session import import_session, SITES
        if provider not in SITES:raise HTTPException(404,'سایت پشتیبانی نمی‌شود.')
        if runtime.jobs or getattr(runtime,'web_connecting',False):raise HTTPException(409,'ابتدا اجرای جاری را تمام کنید.')
        try:result=import_session(provider,payload.path)
        except ValueError as exc:raise HTTPException(400,str(exc))
        # An imported file may belong to another account. Never reuse old account chats.
        with runtime.conn:runtime.conn.execute('UPDATE local_chats SET session_id=NULL WHERE provider=?',(provider,))
        runtime.status_cache=None
        return result

    @router.post('/connections/web/{provider}/verify')
    async def web_verify(provider: str):
        from flux.local_agents.web_session import generate, SITES, SessionError
        if provider not in SITES:raise HTTPException(404,'سایت پشتیبانی نمی‌شود.')
        if runtime.jobs or getattr(runtime,'web_connecting',False):raise HTTPException(409,'ابتدا اجرای جاری را تمام کنید.')
        runtime.web_connecting=True
        try:
            marker='FLUX_'+provider.replace('-','_').upper()+'_OK'
            _,usage,_=await generate(provider,'Reply with exactly '+marker,verification=True)
            return {'authenticated':True,'transport_verified':True,'usage':usage}
        except (ValueError,SessionError) as exc:raise HTTPException(409,str(exc))
        finally:
            runtime.web_connecting=False
            runtime.status_cache=None

    @router.put('/connections/gemini-api')
    async def gemini_key(payload: KeyRequest):
        from flux.local_agents.gemini_api import save_key
        save_key(payload.api_key)
        runtime.status_cache=None
        return {'saved':True,'has_key':bool(payload.api_key.strip()),'credential_validated':False}

    @router.put('/connections/key/{provider}')
    async def provider_key(provider: str, payload: KeyRequest):
        from flux.local_agents.gemini_api import save_provider_key
        if provider not in {"gemini", "groq", "openrouter", "together"}:
            raise HTTPException(400, "پرووایدر نامعتبر است.")
        save_provider_key(provider, payload.api_key)
        runtime.status_cache = None
        return {'saved': True, 'has_key': bool(payload.api_key.strip()), 'provider': provider}

    @router.get("/status")
    async def status(refresh: bool = False):
        return await runtime.status(refresh)

    @router.get("/chats")
    async def chats(archived: str = Query("no", pattern="^(no|only|all)$")):
        return runtime.chats(archived)

    @router.patch("/chats/{ident}")
    async def patch_chat(ident: str, payload: ChatPatch):
        try:
            return runtime.update_chat(ident, payload.title, payload.archived)
        except KeyError:
            raise HTTPException(404, "گفتگو پیدا نشد.")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.delete("/chats/{ident}")
    async def delete_chat(ident: str):
        try:
            return runtime.delete_chat(ident)
        except KeyError:
            raise HTTPException(404, "گفتگو پیدا نشد.")
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.get("/usage")
    async def usage(refresh: bool = False):
        return await runtime.quota(refresh)

    @router.get("/health")
    async def model_health():
        return {"results": runtime.health()}

    @router.post("/probe")
    async def probe(payload: ProbeRequest):
        """Spends one tiny request on the chosen account/model; the UI only calls this after an explicit click."""
        if runtime.jobs or getattr(runtime, 'web_connecting', False):
            raise HTTPException(409, "ابتدا اجرای جاری را تمام یا متوقف کنید.")
        try:
            return await runtime.probe(payload.provider, payload.model)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @router.get("/usage/summary")
    async def usage_summary():
        return {"accounts": runtime.usage_summary()}

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
