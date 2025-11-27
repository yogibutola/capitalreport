from typing import Optional

from fastapi import FastAPI

app = FastAPI(title="Query Param Example")


@app.get("/", summary="Root Endpoint")
def read_root():
    """
    A basic root endpoint for checking service status.
    """
    return {"message": "Welcome to the PDF Uploader API. Go to /docs for more info."}


@app.get("/hello")
async def read_hello(name: Optional[str] = "World"):
    """Return a greeting message based on query param 'name'."""
    return {"message": f"Hello, {name}!"}


@app.options("/{any_path:path}")
async def preflight_handler(any_path: str):
    return {}
