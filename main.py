"""Execute TopOTheHourBot

Typical execution and closure from command line:

```bash
$ python3.12 -u -OO ./main.py > ./main.log 2>&1 &
$ kill -SIGINT [PID]
```

Flag ``-u`` is required to force stdout and stderr to be unbuffered. Nothing
will be written to the log if not provided. Change the logging level in the
``basicConfig()`` call below (note that ``DEBUG`` logs all input and output,
which is probably never wanted for deployment).

Flag ``-OO`` is optional and removes all ``assert`` and ``__debug__``-dependent
statements (which are used pretty frequently).
"""

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
