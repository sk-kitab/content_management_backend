import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from source.routers import summaries, pipeline, reviews, review_labs

app = FastAPI(title="Kitab Voice Pipeline API")

_origins_env = os.getenv("CORS_ORIGINS", "")
_default_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
]
allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(summaries.router)
app.include_router(pipeline.router)
app.include_router(reviews.router)
app.include_router(review_labs.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
