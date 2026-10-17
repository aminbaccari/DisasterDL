"""POST /llm and GET /llm/status: the fallback chain (backend/llm_chain.py) as an endpoint for the n8n HTTP nodes.

Request body: {"system": str, "user": str, "json": bool (default true), "image_b64": str|null, "image_mime": str|null, "retry": bool,
"task": "text" (default) | "vision"}. A vision task uses VISION_CHAIN when it is set, else LLM_CHAIN.
The answer is a Gemini-shaped generateContent answer plus "x_llm" (provider, model, attempts), see llm_chain.complete.
"""
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from backend import llm_chain

router = APIRouter()


@router.post("/llm")
async def llm(request: Request):
    body = await request.json()
    image = {"mime": body["image_mime"], "b64": body["image_b64"]} if body.get("image_b64") and body.get("image_mime") else None
    return await run_in_threadpool(llm_chain.complete, body.get("system", ""), body.get("user", ""), body.get("json", True), image,
                                   None, None, bool(body.get("retry")), body.get("task", "text"))


@router.get("/llm/status")
def llm_status():
    """Which models are configured, whether their key is present (never the key) and whether they are cooling down."""
    return {"chain": llm_chain.status(), "vision_chain": llm_chain.status_vision()}
