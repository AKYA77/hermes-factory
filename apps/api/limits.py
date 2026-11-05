"""Bound incoming body size, including chunked bodies, before JSON decoding."""

from collections import deque
import hashlib
import time


class Limits:
    def __init__(self, app):
        self.app = app
        self.requests = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        key = hashlib.sha256(headers.get(b"authorization", b"")[:4096]).digest()
        now = time.monotonic()
        if key not in self.requests and len(self.requests) >= 4096:
            self.requests = {k: v for k, v in self.requests.items() if v and v[-1] > now - 60}
        if key not in self.requests and len(self.requests) >= 4096:
            return await self.reject(send, 429, b"too many clients")
        bucket = self.requests.setdefault(key, deque())
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= 120:
            return await self.reject(send, 429, b"rate limit exceeded")
        bucket.append(now)
        chunks = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > 65536:
                return await self.reject(send, 413, b"payload too large")
            chunks.append(body)
            if not message.get("more_body"):
                break
        delivered = False

        async def limited_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, limited_receive, send)

    @staticmethod
    async def reject(send, status, message):
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain"), (b"cache-control", b"no-store")],
            }
        )
        await send({"type": "http.response.body", "body": message})
