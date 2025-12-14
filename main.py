from fastapi import FastAPI
from app.routers import jobs, share

app = FastAPI(title="Cat Recognition Service")

app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
app.include_router(share.router, prefix="/api/v1", tags=["share"])


