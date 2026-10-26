"""Probe asyncio thread completion independently of application code."""

import asyncio
import faulthandler


def worker() -> str:
    """Return a trivial value on a worker thread."""
    print("worker ran", flush=True)
    return "thread result"


async def main() -> None:
    """Receive the worker value through the event loop."""
    result = await asyncio.wait_for(asyncio.to_thread(worker), timeout=2)
    print(f"event loop received: {result}", flush=True)


if __name__ == "__main__":
    faulthandler.dump_traceback_later(5)
    try:
        asyncio.run(main())
    finally:
        faulthandler.cancel_dump_traceback_later()
