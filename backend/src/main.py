from fastapi import FastAPI, Request
import time
import logging
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .api import auth, languages, patient, admin, doctor, stats, public, reminders

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
)

# Middleware for timing requests
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    logger.info(f"Request: {request.method} {request.url.path} - Process Time: {process_time:.4f}s")
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should be restricted in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(languages.router, prefix="/api/v1/languages", tags=["languages"])
app.include_router(patient.router, prefix="/api/v1/patient", tags=["patient"])
app.include_router(doctor.router, prefix="/api/v1/doctor", tags=["doctor"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["stats"])
app.include_router(public.router, prefix="/api", tags=["public"])
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["reminders"])

@app.get("/api/health")
def health_check():
    return {"success": True, "message": "Backend is healthy!"}

@app.get("/")
def read_root():
    return {"message": "Welcome to Tanuh BCD API"}
