import asyncio

from source import TopOTheHourBot


async def main(runtime: float = 34200) -> None:

    # Runtime default is 34200 seconds, or 9.5 hours. It's rare that Hasan will
    # go beyond 7-8, but, it's just to play it safe. The runtime must be
    # managed, here - within the script - since this is executed from a cron
    # job.

    # Access and client secret tokens omitted for obvious reasons. See here for
    # more details: https://dev.twitch.tv/docs/irc

    token = ...
    client_secret = ...

    bot = TopOTheHourBot(
        token=token,
        client_secret=client_secret,
        initial_channels=("hasanabi",),
    )

    try:
        await bot.connect()
        await asyncio.sleep(runtime)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
