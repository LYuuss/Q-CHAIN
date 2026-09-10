"""Small, bounded JSON transport used by both the node and CLI."""

import json
import urllib.error
import urllib.request

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


class HttpJsonError(Exception):
    def __init__(self, status_code, body, raw_body):
        self.status_code = status_code
        self.body = body
        self.raw_body = raw_body
        super().__init__(f"HTTP {status_code}: {body if body is not None else raw_body}")


def parse_json_body(raw_body):
    try:
        data = json.loads(raw_body)
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _read_body(response):
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Peer response exceeds the size limit.")
    return body.decode("utf-8")


def _request(url, payload=None, timeout=5):
    request = urllib.request.Request(
        url,
        data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
        method="GET" if payload is None else "POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = parse_json_body(_read_body(response))
            if data is None:
                raise ValueError("Peer response must be a JSON object.")
            return data
    except urllib.error.HTTPError as error:
        raw_body = _read_body(error)
        raise HttpJsonError(error.code, parse_json_body(raw_body), raw_body) from error


def fetch_json(url, timeout=5):
    return _request(url, timeout=timeout)


def post_json(url, payload, timeout=5):
    return _request(url, payload, timeout)
