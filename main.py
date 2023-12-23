"""The TopOTheHourBot CLI

Background execution and closure example, with log file:

```bash
$ python3.12 -u -OO ./main.py "$TWITCH_OAUTH_TOKEN" > ./main.log 2>&1 &
$ kill -SIGINT [PID]
```

Flag ``-u`` is required to force stdout and stderr to be unbuffered. Nothing
will be written to the log if not provided. Change the logging level in the
``basicConfig()`` call below if desired (note that ``DEBUG`` logs all input and
output, which should never be used for deployment).

Flag ``-OO`` is recommended to remove all ``assert`` and ``__debug__``-
dependent statements, which can speed up processing (ircv3 makes extensive use
of ``assert`` statements during ``cast()``s).
"""

import asyncio
import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

import topothehourbot

logging.basicConfig(
    format="[%(asctime)s] [%(name)s] %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)


def main() -> None:
    parser = ArgumentParser(
        prog="main",
        description="Execute TopOTheHourBot",
        epilog="Use `kill -SIGINT [PID]` to close TopOTheHourBot from the"
               " background. This simulates a KeyboardInterrupt, allowing"
               " exception handlers (like those used to save pickles) to run.",
    )

    parser.add_argument(
        "oauth_token",
        help="A Twitch IRC OAuth token. Storing the token in the system"
             " environment variables and invoking it by its name is advised."
             " See here for details on generating one:"
             " https://dev.twitch.tv/docs/irc/authenticate-bot/",
    )
    parser.add_argument(
        "--pickle_directory",
        type=Path,
        default=topothehourbot.DEFAULT_PICKLE_DIRECTORY,
        help="A local directory to read and write pickled data between sessions"
             " of execution. Defaults to topothehourbot/pickles/. The directory"
             " is created if it does not already exist.",
    )

    namespace = parser.parse_args()

    main_coro = topothehourbot.main(
        namespace.oauth_token,
        pickle_directory=namespace.pickle_directory,
    )

    return asyncio.run(main_coro)


if __name__ == "__main__":
    main()
