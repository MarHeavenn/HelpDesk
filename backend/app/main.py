"""Punto de entrada del backend (estructura inicial, sin funcionalidades)."""

from fastapi import FastAPI

app = FastAPI(title="HelpDesk API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
