import asyncio

from main_flow.http import run_http


def main() -> None:
    try:
        asyncio.run(run_http())
    except KeyboardInterrupt:
        pass  # Ctrl+C: uvicorn already shut down gracefully and cleanup ran


if __name__ == "__main__":
    main()
