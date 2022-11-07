import asyncio
import logging
import sys

from source import TopOTheHourBot

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


async def main(runtime: float = 32400) -> None:

    # Runtime default is 32400 seconds, or 9 hours. It's rare that Hasan will
    # go beyond 7-8, but, it's just to play it safe. The runtime must be
    # managed, here - within the script - since this is executed from a cron
    # job.

    # Access and client secret tokens omitted for obvious reasons. See here for
    # more details: https://dev.twitch.tv/docs/irc

    # A quick and easy access token can be obtained from this link after
    # creating an app under localhost (just needs read + write permissions):
    # https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=<YOUR CLIENT ID>&redirect_uri=http://localhost:3000&scope=chat%3Aread+chat%3Aedit

    token = ...
    client_secret = ...

    bot = TopOTheHourBot(token, client_secret=client_secret)

    try:
        await bot.connect()
        await asyncio.sleep(runtime)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
