from __future__ import annotations

__all__ = [
    "HasanAbiExtensionConfiguration",
    "HasanAbiExtension",
]

import dataclasses
import operator
import random
import re
from asyncio import TaskGroup
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass
from re import Pattern
from typing import Final

from channels import Channel, Stream, stream
from ircv3.dialects import twitch
from ircv3.dialects.twitch import LocalServerCommand

from ..system import Client, ClientExtension
from ..utilities import Configuration
from .utilities import IntegerCounter, RealCounter


@dataclass(slots=True, kw_only=True)
class HasanAbiExtensionConfiguration(Configuration):

    target: str = "#hasanabi"

    supervisors: set[str] = dataclasses.field(default_factory=lambda: {"lyystra", "astryyl", "bytesized_", "emjaye"})
    bots: set[str] = dataclasses.field(default_factory=lambda: {"fossabot", "blammobot", "frierenbot"})

    segue_rating_inference: bool = True
    segue_rating_inference_decay: float = 8.5
    segue_rating_inference_threshold: int = 40

    roleplay_rating_total: int = 0
    roleplay_rating_inference: bool = True
    roleplay_rating_inference_decay: float = 7.5
    roleplay_rating_inference_threshold: int = 20


class HasanAbiExtension(ClientExtension[LocalServerCommand]):
    """TopOTheHourBot's Hasan-specific operations

    Does a few different things:
    - Defines a small set of mod-only commands
    - Averages batch ratings given by chat when Hasan performs an ad segue
    - Sums batch +1 and -1 scores given by chat when Hasan distinctively stays
      in and out of character during roleplay sessions

    Contains only one instance variable, ``roleplay_rating_total``, that is the
    summation of all roleplay scores across time. All other attributes are
    statically-defined at the class level.
    """

    __slots__ = ("config")
    config: HasanAbiExtensionConfiguration

    def __init__(
        self,
        client: Client,
        *,
        config: HasanAbiExtensionConfiguration = HasanAbiExtensionConfiguration(),
    ) -> None:
        super().__init__(client)
        self.config = config

    segue_rating_initial: Final[RealCounter] = RealCounter(0, 0)
    segue_rating_pattern: Final[Pattern[str]] = re.compile(
        r"""
        (?:^|\s)               # Should proceed the beginning or whitespace
        (
          [-+]?                # Optional + or -
          (?:
            (?:\d+(?:\.\d*)?)  # Integer with optional decimal part
            |
            (?:\.\d+)          # Decimal part only
          )
        )
        \s?/\s?10              # Denominator of 10
        (?:$|[\s,.!?])         # Should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )

    @stream.compose
    async def handle_segue_ratings(
        self,
        channel: Channel[RealCounter],
        *,
        decay: float,
        threshold: int = 0,
    ) -> AsyncIterator[Coroutine]:
        assert not channel.closed

        with channel.closure():
            counter = await (
                aiter(channel)
                    .finite_timeout(decay)
                    .reduce(self.segue_rating_initial, operator.add)
            )

        segue_rating_value = counter.value
        segue_rating_count = counter.count
        if segue_rating_count < threshold:
            return

        try:
            segue_rating = segue_rating_value / segue_rating_count
        except ZeroDivisionError:
            segue_rating = float("inf")

        if segue_rating <= 5:
            if segue_rating <= 2.5:
                reactions = (
                    "yikes, hassy .. unPOGGERS",
                    "awful one, hassy :(",
                    "that wasn't very, uhm .. good, hassy Concerned",
                )
            else:
                reactions = (
                    "sorry, hassy .. :/",
                    "uhm .. good try, hassy PoroSad",
                    "not .. great, hassy .. Okayyy Clap",
                )
        else:
            if segue_rating <= 7.5:
                reactions = (
                    "not bad, hassy ! :D",
                    "nice, hassy ! peepoPog Clap",
                    "good one, hassy ! hasScoot",
                )
            else:
                reactions = (
                    "incredible, hassy !! pepoDance",
                    "holy smokes, hassy !! :O",
                    "wowieee, hassy !! peepoExcite",
                )

        yield self.message(
            f"DANKIES 🔔 {segue_rating_count:,d} chatters rated this ad segue an average"
            f" of {segue_rating:.2f}/10 - {random.choice(reactions)}",
            target=self.config.target,
        )

    roleplay_rating_initial: Final[IntegerCounter] = IntegerCounter(0, 0)
    roleplay_rating_pattern: Final[Pattern[str]] = re.compile(
        r"""
        (?:^|\s)        # Should proceed the beginning or whitespace
        ([-+]1)         # -1 or +1
        (?:$|[\s,.!?])  # Should precede the end, whitespace, or some punctuation
        """,
        flags=re.VERBOSE,
    )

    @stream.compose
    async def handle_roleplay_ratings(
        self,
        channel: Channel[IntegerCounter],
        *,
        decay: float,
        threshold: int = 0,
    ) -> AsyncIterator[Coroutine]:
        assert not channel.closed

        with channel.closure():
            counter = await (
                aiter(channel)
                    .finite_timeout(decay)
                    .reduce(self.roleplay_rating_initial, operator.add)
            )

        roleplay_rating_delta = counter.value
        roleplay_rating_count = counter.count
        if roleplay_rating_count < threshold:
            return

        self.config.roleplay_rating_total += roleplay_rating_delta
        roleplay_rating_total = self.config.roleplay_rating_total

        if roleplay_rating_total > 0:
            reactions = (
                "FeelsSnowyMan",
                ":D",
                "Gladge",
                "veryCat",
                "FeelsOkayMan",
            )
        else:
            reactions = (
                "FeelsSnowMan",
                ":(",
                "Sadge",
                "Awkward",
                "FeelsBadMan",
            )

        yield self.message(
            f"donScoot 🔔 hassy {"gained" if roleplay_rating_delta >= 0 else "lost"}"
            f" {roleplay_rating_delta:+,d} points for this roleplay moment - hassy has"
            f" {roleplay_rating_total:,d} points in total {random.choice(reactions)}",
            target=self.config.target,
        )

    @stream.compose
    async def handle_private_messages(self) -> AsyncIterator[Stream | Coroutine]:
        supervisors = self.config.supervisors
        bots = self.config.bots
        name = self.name

        segue_ratings = Channel[RealCounter]().close()
        roleplay_ratings = Channel[IntegerCounter]().close()

        with self.attachment() as channel:
            async for message in (
                aiter(channel)
                    .filter(twitch.is_server_private_message)
                    .filter(lambda message: message.sender.name not in bots)
                    .filter(lambda message: message.sender.name != name)
            ):
                comment = message.comment

                # TODO: In catastrophic need of clean-up - potentially create
                # a "Command" type for splitting this out?

                if (
                    comment.startswith("$")
                    and (
                        message.sender.name in supervisors
                        or message.sender.is_moderator
                        or message.sender.is_broadcaster
                    )
                ):
                    match comment[1:].split():
                        case ["ping", *_]:
                            yield self.message(
                                f"{self.latency:.0f}ms",
                                target=message,
                            )
                        case ["copy" | "echo" | "shadow", *words]:
                            yield self.message(
                                " ".join(words),
                                target=message,
                            )
                        case ["code", *handles]:
                            yield self.message(
                                f"{" ".join(map(lambda handle: "@" + handle.lstrip("@"), handles))}"
                                f" you can find the bot's source code on GitHub"
                                f" https://github.com/TopOTheHourBot/",
                                target=message,
                            )
                        case ["segue", "infer", *_]:
                            segue_rating_inference = not self.config.segue_rating_inference
                            self.config.segue_rating_inference = segue_rating_inference
                            yield self.message(
                                f"Segue inference has been toggled {"on" if segue_rating_inference else "off"}",
                                target=message,
                            )
                        case ["segue", "start", raw_decay, *_]:
                            try:
                                decay = float(raw_decay)
                            except ValueError:
                                yield self.message(
                                    f"Could not parse decay '{raw_decay}' as number",
                                    target=message,
                                )
                            else:
                                if segue_ratings.closed:
                                    segue_ratings.open()
                                    yield self.handle_segue_ratings(segue_ratings, decay=decay)
                                    yield self.message(
                                        f"Segue ratings are now tallying with decay time of {decay:.2f} seconds",
                                        target=message,
                                    )
                                else:
                                    yield self.message(
                                        "Segue ratings are already being tallied",
                                        target=message,
                                    )
                        case ["segue", "stop", *_]:
                            if segue_ratings.closed:
                                yield self.message(
                                    "Segue ratings were not tallying",
                                    target=message,
                                )
                            else:
                                segue_ratings.close()
                                yield self.message(
                                    "Segue ratings have stopped tallying",
                                    target=message,
                                )
                        case ["roleplay", "total", *_]:
                            yield self.message(
                                f"Hasan has accrued {self.config.roleplay_rating_total:,d} roleplay points"
                                " since December 17, 2023",
                                target=message,
                            )
                        case ["roleplay", "infer", *_]:
                            roleplay_rating_inference = not self.config.roleplay_rating_inference
                            self.config.roleplay_rating_inference = roleplay_rating_inference
                            yield self.message(
                                f"Roleplay moment inference has been toggled {"on" if roleplay_rating_inference else "off"}",
                                target=message,
                            )
                        case ["roleplay", "start", raw_decay, *_]:
                            try:
                                decay = float(raw_decay)
                            except ValueError:
                                yield self.message(
                                    f"Could not parse decay '{raw_decay}' as number",
                                    target=message,
                                )
                            else:
                                if roleplay_ratings.closed:
                                    roleplay_ratings.open()
                                    yield self.handle_roleplay_ratings(roleplay_ratings, decay=decay)
                                    yield self.message(
                                        f"Roleplay scores are now tallying with decay time of {decay:.2f} seconds",
                                        target=message,
                                    )
                                else:
                                    yield self.message(
                                        "Roleplay scores are already being tallied",
                                        target=message,
                                    )
                        case ["roleplay", "stop", *_]:
                            if roleplay_ratings.closed:
                                yield self.message(
                                    "Roleplay scores were not tallying",
                                    target=message,
                                )
                            else:
                                roleplay_ratings.close()
                                yield self.message(
                                    "Roleplay scores have stopped tallying",
                                    target=message,
                                )
                    continue

                if (match := self.segue_rating_pattern.search(comment)):
                    rating = RealCounter(match.group(1)).clamp(0, 10)
                    if segue_ratings.closed:
                        if self.config.segue_rating_inference:
                            segue_ratings.open().send(rating)
                            yield self.handle_segue_ratings(
                                segue_ratings,
                                decay=self.config.segue_rating_inference_decay,
                                threshold=self.config.segue_rating_inference_threshold,
                            )
                    else:
                        segue_ratings.send(rating)

                if (match := self.roleplay_rating_pattern.search(comment)):
                    rating = IntegerCounter(match.group(1))
                    if roleplay_ratings.closed:
                        if self.config.roleplay_rating_inference:
                            roleplay_ratings.open().send(rating)
                            yield self.handle_roleplay_ratings(
                                roleplay_ratings,
                                decay=self.config.roleplay_rating_inference_decay,
                                threshold=self.config.roleplay_rating_inference_threshold,
                            )
                    else:
                        roleplay_ratings.send(rating)

    async def accumulate(self) -> None:
        """Execute all message handlers asynchronously, dispatching coroutines
        as they are yielded
        """
        merger = stream.merge(
            self.handle_private_messages(),
            suppress_exceptions=True,
        )
        async with TaskGroup() as tasks:
            async for coro in merger:
                if isinstance(coro, Stream):
                    merger.add(coro)
                else:
                    tasks.create_task(coro)

    async def distribute(self) -> None:
        """Join the target room and eternally distribute its localised commands
        to attachments
        """
        await self.join(self.config.target)
        async with TaskGroup() as tasks:
            tasks.create_task(self.accumulate())
            with self._diverter.closure() as diverter:
                with self._client.attachment() as channel:
                    async for command in (
                        aiter(channel)
                            .filter(twitch.is_local_server_command)
                            .filter(lambda command: command.room == self.config.target)
                    ):
                        diverter.send(command)
