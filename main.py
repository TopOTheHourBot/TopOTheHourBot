import asyncio
import logging
import sys

from source import TopOTheHourBot

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


async def main(runtime: float = 36000) -> None:

    # Runtime default is 36000 seconds, or 10 hours. It's rare that Hasan will
    # go beyond 8, but, it's just to play it safe. The runtime must be managed,
    # here - within the script - since this is executed from a cron job.

    # Access and client secret tokens omitted for obvious reasons. See here for
    # more details: https://dev.twitch.tv/docs/irc

    # Quick and easy access token can be obtained from this link after creating
    # an app (just needs chat read + write permissions):
    # https://id.twitch.tv/oauth2/authorize?response_type=token&client_id=<YOUR CLIENT ID>&redirect_uri=http://localhost:3000&scope=chat%3Aread+chat%3Aedit

    token = ...
    client_secret = ...

    bot = TopOTheHourBot(
        token,
        client_secret=client_secret,
        moderators={"braedye", "bytesized_", "emjaye"},
    )

    await bot.connect()
    await asyncio.sleep(runtime)
    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
