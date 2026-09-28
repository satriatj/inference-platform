"""
Mock LLM inference worker.

This pretends to be a model server like vLLM. It does no real inference, but it
imitates the two properties that matter to a control plane:

1. Latency depends on how many tokens a request has (long prompts and long
   outputs take longer).
2. A worker has limited capacity. It can only work on N requests at once, and
   the rest have to wait.

It exposes the same endpoint shape as vLLM's OpenAI-compatible server
(POST /v1/completions), so the gateway you build later can talk to this mock
or to real vLLM without code changes.
"""

import asyncio
import os
import time
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
#
# Read from environment variables so you can run several workers with different
# "hardware" (e.g. one fast, one slow) without changing code. Docker Compose
# and Kubernetes both pass config to containers this way.
# ---------------------------------------------------------------------------

WORKER_ID = os.getenv("WORKER_ID", "worker-1")

# Real LLM inference has two phases:
#   - prefill: the model reads the whole prompt in one parallel pass. That's
#     cheap per token.
#   - decode: the model generates output one token at a time. That's
#     expensive per token.
# Decode is usually the bigger cost, which is why max_tokens matters so much.
PREFILL_MS_PER_TOKEN = float(os.getenv("PREFILL_MS_PER_TOKEN", "0.5"))
DECODE_MS_PER_TOKEN = float(os.getenv("DECODE_MS_PER_TOKEN", "20"))

# How many requests this worker processes at the same time. On a real GPU this
# is roughly the batch size. Anything beyond it waits in line.
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))

app = FastAPI()

# A semaphore is a counter of available slots. `async with semaphore:` takes a
# slot, or waits until one frees up. It is the worker's capacity limit, and the
# requests waiting on it form the worker's internal queue.
semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

# Load counters. Later the scheduler will read these (via /health) to decide
# which worker is least loaded. They're plain ints, not locked, because asyncio
# runs on one thread and only switches tasks at an `await`, so `+= 1` can't be
# interrupted halfway through.
active_requests = 0   # holding a slot, "on the GPU"
waiting_requests = 0  # waiting for a slot


# ---------------------------------------------------------------------------
# Request / response schemas (a subset of the OpenAI completions API)
# ---------------------------------------------------------------------------

class CompletionRequest(BaseModel):
    model: str = "mock-model"
    prompt: str
    max_tokens: int = 16


class Choice(BaseModel):
    index: int
    text: str
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CompletionResponse(BaseModel):
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage


def count_tokens(text: str) -> int:
    # Real models use a tokenizer (roughly 1 token per 3/4 of an English word).
    # Splitting on whitespace is close enough for simulation and has no
    # dependencies. It's a known inaccuracy you can revisit later.
    return len(text.split())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    # This does double duty as a liveness check ("am I up?") and a load report
    # ("how busy am I?"). Later you'll likely split those apart.
    return {
        "status": "ok",
        "worker_id": WORKER_ID,
        "active_requests": active_requests,
        "waiting_requests": waiting_requests,
        "max_concurrency": MAX_CONCURRENCY,
    }


# `async def` matters. A plain `def` endpoint runs in a threadpool capped at
# about 40 threads, which would add a hidden concurrency limit on top of
# MAX_CONCURRENCY. With `async def` + `await asyncio.sleep`, one thread can hold
# thousands of waiting requests. The only limit is the semaphore we chose.
@app.post("/v1/completions", response_model=CompletionResponse)
async def completions(request: CompletionRequest):
    global active_requests, waiting_requests

    prompt_tokens = count_tokens(request.prompt)
    completion_tokens = request.max_tokens

    arrived = time.perf_counter()
    waiting_requests += 1
    async with semaphore:
        waiting_requests -= 1
        active_requests += 1
        started = time.perf_counter()
        try:
            # Simulated inference. asyncio.sleep yields control, so other
            # requests keep being accepted while this one "computes".
            service_ms = (
                prompt_tokens * PREFILL_MS_PER_TOKEN
                + completion_tokens * DECODE_MS_PER_TOKEN
            )
            await asyncio.sleep(service_ms / 1000)
        finally:
            # `finally` makes sure the counter is decremented even if the
            # request is cancelled (e.g. client disconnects mid-sleep).
            active_requests -= 1
    finished = time.perf_counter()

    # Split the latency into waiting time and working time. This is the
    # most useful number in the whole project: when latency goes up, you need
    # to know whether requests are waiting or working.
    queue_ms = (started - arrived) * 1000
    run_ms = (finished - started) * 1000
    print(
        f"[{WORKER_ID}] prompt={prompt_tokens}tok out={completion_tokens}tok "
        f"queue={queue_ms:.0f}ms run={run_ms:.0f}ms"
    )

    return CompletionResponse(
        id=f"cmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=request.model,
        choices=[
            Choice(
                index=0,
                text=" ".join(["token"] * completion_tokens),
                finish_reason="length",
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )
