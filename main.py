from fastapi import FastAPI

app = FastAPI(
    title="PPIS API",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "PPIS Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }