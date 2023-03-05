import asyncio
import logging
import sys

from source import TopOTheHourBot

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


async def main(runtime: float = 34200) -> None:

    # Runtime default is 34200 seconds, or 9.5 hours. It's rare that Hasan will
    # go beyond 7-8, but, it's just to play it safe. The runtime must be
    # managed, here - within the script - since this is executed from a cron
    # job.

    bot = TopOTheHourBot()
    try:
        await bot.connect()
        await asyncio.sleep(runtime)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
