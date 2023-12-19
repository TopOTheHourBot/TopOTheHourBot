import asyncio
import logging
import sys

from topothehourbot import main

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


if __name__ == "__main__":
    asyncio.run(main("..."))
