from fastapi import FastAPI, status, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Query Param Example")

origins = [
    "http://localhost:4200",  # <--- YOUR FRONTEND ORIGIN
    "http://127.0.0.1:4200",
    "http://0.0.0.0:4200"
    # (Optional: Sometimes localhost maps to 127.0.0.1)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # Allows cookies, authorization headers, etc.
    allow_methods=["*"],  # Allows all HTTP methods (POST, GET, PUT, etc.)
    allow_headers=["*"],  # Allows all headers from the request
)
