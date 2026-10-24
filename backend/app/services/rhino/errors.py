"""Typed Rhino transport errors.

Messages are constructed from fixed templates + status codes only, so secrets,
API keys, request bodies and URLs never appear in an error string.
"""


class RhinoError(RuntimeError):
    code = "RHINO_ERROR"


class RhinoUnavailableError(RhinoError):
    """The Rhino.Compute node could not be reached (refused/timeout/DNS)."""

    code = "RHINO_UNAVAILABLE"


class RhinoCapabilityUnavailableError(RhinoError):
    """A real capability that is deliberately not implemented in this section."""

    code = "RHINO_CAPABILITY_UNAVAILABLE"

    def __init__(self, capability: str = "geometry") -> None:
        self.capability = capability
        super().__init__(f"rhino capability not implemented in this section: {capability}")


class RhinoRequestError(RhinoError):
    """The node answered but the request failed (non-2xx / undecodable body)."""

    code = "RHINO_REQUEST_FAILED"

    def __init__(self, status_code: int, reason: str = "http_error") -> None:
        self.status_code = status_code
        self.reason = reason
        super().__init__(f"rhino-compute request failed (status={status_code}, reason={reason})")
