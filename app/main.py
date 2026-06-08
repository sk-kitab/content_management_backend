from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from source.routers import summaries, pipeline, reviews, review_labs

app = FastAPI(title="Kitab Voice Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
