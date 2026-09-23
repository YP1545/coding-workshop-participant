"""
The one error type the business rules raise.

Part of: backend / core.

Why its own file: workflow.py, access.py and crud.py decide that something is
a 404 or a 409, and they should be able to say so without importing a web
framework. They raise ApiError; app.py turns it into a response. That keeps the
rules readable as plain Python and testable without starting an application.
"""


class ApiError(Exception):
    """
    An error that maps directly onto an HTTP response.

    Attributes:
        status (int): the HTTP status code to return.
        detail (str): the message the client sees. Never a driver message or a
            constraint name — those describe our tables, not their mistake.
    """

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail
