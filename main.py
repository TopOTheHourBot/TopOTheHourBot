"""The TopOTheHourBot CLI

Background execution and closure example, with log file:

```bash
$ python3.12 -u -OO ./main.py "$TWITCH_OAUTH_TOKEN" > ./main.log 2>&1 &
$ kill -SIGINT [PID]
```

Flag ``-u`` is required to force stdout and stderr to be unbuffered. Nothing
will be written to the log if not provided. Change the logging level in the
``basicConfig()`` call below if desired.

Flag ``-OO`` is recommended to remove all ``assert`` and ``__debug__``-
dependent statements, which can speed up processing (``ircv3`` makes extensive
use of ``assert`` statements during ``cast()``s).
"""

import asyncio
import itertools
import logging
import sys
from argparse import ArgumentParser

from topothehourbot import hasanabi, lyystra
from topothehourbot.api import ClientApp

logging.basicConfig(
    format="[%(asctime)s] [%(levelno)s] [%(name)s] [%(filename)s]"
           " [%(funcName)s] %(message)s",
    level=logging.DEBUG,
    stream=sys.stdout,
)


async def main(*, oauth_token: str, name: str) -> None:
    app = ClientApp(
        oauth_token=oauth_token,
        name=name,
    )
    for suite in itertools.chain(hasanabi.suites(), lyystra.suites()):
        app.add_callbacks(suite)
    await app.run()


def cli() -> None:
    parser = ArgumentParser(
        prog="main",
        description="Execute TopOTheHourBot",
        epilog="Use `kill -SIGINT [PID]` to close TopOTheHourBot from the"
               " background. This simulates a KeyboardInterrupt, allowing"
               " exception handlers to run.",
    )
    parser.add_argument(
        "oauth_token",
        help="A Twitch IRC OAuth token. Storing the token in the system"
             " environment variables and invoking it by its name is advised."
             " See here for details on generating one:"
             " https://dev.twitch.tv/docs/irc/authenticate-bot/",
    )
    parser.add_argument(
        "--name",
        default="topothehourbot",
        help="Login name of the client. Defaults to 'topothehourbot'.",
    )

    namespace = parser.parse_args()
    main_coro = main(
        oauth_token=namespace.oauth_token,
        name=namespace.name,
    )

    return asyncio.run(main_coro)


if __name__ == "__main__":
    cli()
