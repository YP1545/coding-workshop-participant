"""
The Lambda entry point: Mangum, and the path prefix.

Part of: backend / tests.

Why its own file: every other test drives the application through TestClient,
which skips the part AWS actually calls. This is the seam where a Function URL
event becomes an ASGI request, and where the "/api/{service}" prefix CloudFront
adds is removed. Both are invisible in development and would only show up as a
404 in production.
"""

import json

import pytest


def function_url_event(method, path, body=None, headers=None):
    """
    A Lambda Function URL event, in the shape AWS version 2.0 sends.

    Written out in full rather than trimmed to what Mangum happens to read, so
    the test keeps working if it starts reading more.
    """
    return {
        "version": "2.0",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers or {},
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.1",
                "userAgent": "test",
            },
            "requestId": "test-request",
            "stage": "$default",
            "apiId": "test",
            "domainName": "test.lambda-url.us-east-2.on.aws",
            "timeEpoch": 0,
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


@pytest.fixture(scope="module")
def handlers(database):
    """The four Lambda handlers, as AWS would import them."""
    from conftest import load_service

    return {name: load_service(f"{name}-service").handler
            for name in ("users", "facilities", "engineers", "incidents")}


@pytest.mark.parametrize("service", ["users", "facilities", "engineers", "incidents"])
def test_a_plain_path_reaches_the_handler(handlers, service):
    """What the local dev proxy sends, having stripped the prefix itself."""
    response = handlers[service](function_url_event("GET", "/health"), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"status": "ok", "service": f"{service}-service"}


@pytest.mark.parametrize("service", ["users", "facilities", "engineers", "incidents"])
def test_the_cloudfront_prefix_is_stripped(handlers, service):
    """
    What CloudFront sends: the prefix is left on.

    infra/cloudfront.tf routes /api/{service}* to the Function URL without
    rewriting the path, so without the middleware every deployed request would
    be a 404 while everything worked locally.
    """
    event = function_url_event("GET", f"/api/{service}-service/health")

    response = handlers[service](event, None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["service"] == f"{service}-service"


def test_the_bare_prefix_reaches_the_root(handlers):
    """"/api/users-service" with nothing after it must not become an empty path."""
    response = handlers["users"](function_url_event("GET", "/api/users-service"), None)

    # No route is defined at "/", so a 404 from the application is correct — the
    # point is that it was routed at all rather than crashing on an empty path.
    assert response["statusCode"] == 404


def test_a_similar_looking_path_is_not_stripped(handlers):
    """Only this service's own prefix is removed, not anything starting with /api."""
    response = handlers["users"](function_url_event("GET", "/api/users-service-other/health"), None)

    assert response["statusCode"] == 404


def test_a_real_request_survives_the_round_trip(handlers):
    """
    A POST with a body and headers, through the adapter.

    Proves Mangum is handing the body over and returning a JSON response, not
    just that routing works on a GET.
    """
    event = function_url_event(
        "POST", "/api/users-service/auth/login",
        body={"email": "nobody@acme.inc", "password": "whatever-is-wrong"},
        headers={"content-type": "application/json"},
    )

    response = handlers["users"](event, None)

    assert response["statusCode"] == 401
    assert json.loads(response["body"]) == {"detail": "Invalid email or password"}


def test_the_api_map_is_not_published(handlers, monkeypatch):
    """
    The generated documentation must not be reachable from a deployment.

    It lists every path, field and enum value, and needs no token — which is
    useful while building and is a free reconnaissance map once deployed. The
    app is built at import time, so this checks the decision rather than the
    built app: is_local() is what create_app branches on, and infra/locals.tf
    sets IS_LOCAL to "false" everywhere that is not a developer's machine.
    """
    import db

    monkeypatch.setenv("IS_LOCAL", "false")
    assert db.is_local() is False

    monkeypatch.setenv("IS_LOCAL", "true")
    assert db.is_local() is True


def test_documentation_is_available_while_developing(handlers):
    """The other half: it is there when IS_LOCAL is true, which is how the tests run."""
    response = handlers["users"](function_url_event("GET", "/api/users-service/openapi.json"), None)

    assert response["statusCode"] == 200
