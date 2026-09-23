"""
Serve the four services over HTTP on one port, for manual testing.

Part of: backend / developer tooling.

Why this exists: deployed, each service is its own Lambda behind its own
Function URL. Locally that would mean LocalStack, Docker and sudo. This mounts
the same four FastAPI applications under one uvicorn server at the same paths
CloudFront uses, so curl, Postman and the frontend all work in seconds.

What you get for free: each service's generated documentation at
/api/{service}/docs, which is the quickest way to see the whole API.

It is never deployed: this directory ships no Lambda.

Usage, from backend/_shared with the repo venv active:
    IS_LOCAL=true POSTGRES_NAME=postgres python serve_local.py
    IS_LOCAL=true POSTGRES_NAME=postgres python serve_local.py --port 8080
"""

import argparse
import importlib.util
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = ("users-service", "facilities-service", "engineers-service", "incidents-service")
DEFAULT_PORT = 8000

# Loopback only. This has no rate limiting and runs with the development signing
# key, so it must not be reachable from the network.
HOST = "127.0.0.1"


def load(service):
    """
    Import one service's application with its own directory first on sys.path.

    Each service holds its own copies of the shared modules, because a Lambda is
    packaged from one directory. The module cache is cleared between services so
    each binds to the copy inside its own folder.
    """
    sys.path.insert(0, os.path.join(BACKEND, service))
    for module in ("function", "app", "errors", "deps", "schemas", "db", "models", "auth",
                   "access", "workflow", "dashboard", "assignment_requests", "crud"):
        sys.modules.pop(module, None)
    spec = importlib.util.spec_from_file_location(
        f"{service}_function", os.path.join(BACKEND, service, "function.py"))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    sys.path.pop(0)
    return loaded.app


def build():
    """
    Mount the four services under the paths CloudFront uses.

    Mounting at /api/{service} means each application sees the path with the
    prefix already removed — the same view it gets in Lambda, where the
    middleware in app.py strips it.
    """
    root = FastAPI(title="ACME Facility Incidents — all services (local)")

    # Permissive CORS so a browser on :3000 can call this directly if it wants.
    # Deployed CORS is configured on the Function URL, not here.
    root.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    for service in SERVICES:
        root.mount(f"/api/{service}", load(service))

    @root.get("/")
    def index():
        """A list of what is mounted, for somebody who opens the port directly."""
        return {
            "services": {
                service: {
                    "health": f"/api/{service}/health",
                    "docs": f"/api/{service}/docs",
                }
                for service in SERVICES
            }
        }

    return root


def main():
    """Load every service, then serve until interrupted."""
    parser = argparse.ArgumentParser(description="Serve the four services over HTTP.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    application = build()

    print(f"Serving {len(SERVICES)} services on http://{HOST}:{args.port}\n", flush=True)
    for service in SERVICES:
        print(f"  http://{HOST}:{args.port}/api/{service}/health", flush=True)
        print(f"  http://{HOST}:{args.port}/api/{service}/docs   (API documentation)", flush=True)
    print("\nPress Ctrl+C to stop.\n", flush=True)

    uvicorn.run(application, host=HOST, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
