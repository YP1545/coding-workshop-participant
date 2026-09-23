"""
Building a FastAPI application that behaves correctly inside Lambda.

Part of: backend / core (infrastructure).

Why its own file: every service needs the same three pieces of wiring — the
path prefix CloudFront adds, the error shape the API promises, and the Mangum
adapter that turns a Lambda event into an ASGI request. Doing it once here
means a service's own file is nothing but its routes.

This file is the canonical copy. Do not edit the copies inside the service
directories — edit here and run ./sync.sh.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum

from db import is_local
from errors import ApiError


class StripServicePrefix:
    """
    Remove the "/api/{service}" prefix before FastAPI routes the request.

    CloudFront sends the prefix through to the Lambda (infra/cloudfront.tf
    routes /api/{service}* without rewriting), while the local dev proxy strips
    it. Rather than declaring every route twice, the path is normalised here so
    both environments reach the same handler.

    Written as plain ASGI middleware rather than FastAPI middleware because it
    has to run before routing, not before the endpoint.
    """

    def __init__(self, app, service_name):
        self.app = app
        self.prefix = f"/api/{service_name}"

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == self.prefix:
                scope["path"] = "/"
            elif path.startswith(self.prefix + "/"):
                scope["path"] = path[len(self.prefix):]
        await self.app(scope, receive, send)


def create_app(service_name, title):
    """
    Build the FastAPI application for one service.

    Args:
        service_name: the directory name, e.g. "users-service". Used for the
            path prefix and returned by /health.
        title: what this service is, shown in the generated documentation.

    Returns:
        FastAPI: configured with the error handlers and a /health route.
    """
    # The generated documentation is a complete map of the API — every path,
    # every field, every enum value — and it needs no token to read. That is
    # exactly what you want while building and exactly what you do not want to
    # publish, so it is served locally only. IS_LOCAL comes from
    # infra/locals.tf and is "false" everywhere that is deployed.
    development = is_local()

    app = FastAPI(
        title=title,
        version="1.0.0",
        docs_url="/docs" if development else None,
        redoc_url="/redoc" if development else None,
        openapi_url="/openapi.json" if development else None,
    )

    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, error: ApiError):
        """
        Turn a domain error into a response.

        The rules in workflow.py, access.py and crud.py raise ApiError, which
        knows nothing about FastAPI. Keeping them framework-free means they can
        be read and tested as plain Python, and this is the one place that
        decides what an HTTP client sees.
        """
        return JSONResponse(status_code=error.status, content={"detail": error.detail})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, error: RequestValidationError):
        """
        Report a bad request as 400 with a readable message.

        FastAPI's default is 422 with a list of error objects. The API contract
        promises 400 and a single "detail" string everywhere, and a client that
        has to branch on the shape of an error is a client that will get it
        wrong.
        """
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"] if part not in ("body", "query"))
        message = first.get("msg", "Invalid request")
        detail = f"{location}: {message}" if location else message
        return JSONResponse(status_code=400, content={"detail": detail})

    @app.get("/health", tags=["health"])
    async def health():
        """Liveness probe used by start-dev.sh and the post-deploy smoke test."""
        return {"status": "ok", "service": service_name}

    return app


def lambda_handler(app, service_name):
    """
    Wrap the application so AWS can call it.

    Mangum translates a Lambda Function URL event into an ASGI request and the
    response back again. lifespan is off because Lambda gives no startup or
    shutdown hook worth using — the database engine is created lazily on first
    use instead.
    """
    return Mangum(StripServicePrefix(app, service_name), lifespan="off")
