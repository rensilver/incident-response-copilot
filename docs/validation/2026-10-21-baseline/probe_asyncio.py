"""Probe asyncio thread completion without importing application or graph code."""

import asyncio
import faulthandler


def worker():
    print("worker ran", flush=True)
    return "thread result"


async def main():
    result = await asyncio.wait_for(asyncio.to_thread(worker), timeout=2)
    print(f"event loop received: {result}", flush=True)


if __name__ == "__main__":
    faulthandler.dump_traceback_later(5)
    try:
        asyncio.run(main())
    finally:
        faulthandler.cancel_dump_traceback_later()
