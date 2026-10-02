"""Bounded child-output filtering, including secrets split across read chunks."""
def pump(source, sink, secrets):
    secrets = sorted({x for x in secrets if x}, key=len, reverse=True)
    keep = max(map(len, secrets), default=1)
    pending = b""
    try:
        while True:
            chunk = source.readline(1024 * 1024)
            data = pending + chunk
            for secret in secrets:
                data = data.replace(secret, b"*" * len(secret))
            if not chunk or chunk.endswith(b"\n"):
                sink.write(data)
                pending = b""
            else:
                cut = max(0, len(data) - keep)
                sink.write(data[:cut])
                pending = data[cut:]
            if not chunk:
                break
    finally:
        source.close()
        sink.close()
