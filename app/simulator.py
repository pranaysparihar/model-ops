"""Deterministic CPU test double; this is not an AI model."""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(docs_url=None, redoc_url=None)
FAULT_FILE = Path(os.getenv("FAULT_FILE", "/tmp/modelops-fail"))


@app.get("/health")
async def health():
    return JSONResponse(
        {"status": "failed" if FAULT_FILE.exists() else "ok"}, status_code=503 if FAULT_FILE.exists() else 200
    )


@app.post("/v1/chat/completions")
async def completion(payload: dict):
    if FAULT_FILE.exists():
        return JSONResponse({"error": "Injected simulator failure"}, status_code=503)
    await asyncio.sleep(float(os.getenv("SIMULATED_DELAY_SECONDS", "0.15")))
    return {
        "id": "simulated",
        "object": "chat.completion",
        "model": payload.get("model", "demo-model"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "ModelOps simulator: delivery and reliability checks passed. This is not model inference.",
                },
                "finish_reason": "stop",
            }
        ],
    }
