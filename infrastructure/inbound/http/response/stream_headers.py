import time


def stream_headers(action: str, status_text: str, message: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Action": action,
        "X-Status": status_text,
        "X-Message": message,
        "X-Timestamp": str(time.time()),
    }
