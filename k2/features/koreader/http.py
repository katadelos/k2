"""HTTPS transport for upstream KOReader metadata and assets."""

from collections.abc import Mapping
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from ...adapters.network import tls_context


def _validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Downloads require HTTPS without a username or password.")


class _HttpsRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, url):
        _validate_url(url)
        return super().redirect_request(request, fp, code, message, headers, url)


def open_https(
    url: str, *, headers: Mapping[str, str] | None = None, timeout: float = 20
):
    """Open a validated HTTPS URL, enforcing the same policy on every redirect."""
    _validate_url(url)
    # Both the initial URL and redirect targets are restricted to HTTPS above.
    request = Request(url, headers=dict(headers or {}))  # noqa: S310
    opener = build_opener(_HttpsRedirects(), HTTPSHandler(context=tls_context()))
    return opener.open(request, timeout=timeout)
