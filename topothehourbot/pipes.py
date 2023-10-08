from __future__ import annotations

__all__ = [
    "Pipe",
    "Transport",
]

from abc import abstractmethod
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from channels import SupportsRecv, SupportsSend, SupportsSendAndRecv
from ircv3 import IRCv3CommandProtocol
from ircv3.dialects.twitch import ClientPrivmsg

T1_co = TypeVar("T1_co", covariant=True, bound=ClientPrivmsg | str)
T2_co = TypeVar("T2_co", covariant=True, bound=IRCv3CommandProtocol | str)
T_contra = TypeVar("T_contra", contravariant=True, bound=IRCv3CommandProtocol)


class Pipe(Protocol[T_contra, T1_co, T2_co]):

    @abstractmethod
    def __call__(
        self,
        isstream: SupportsRecv[T_contra],
        omstream: SupportsSend[T1_co],
        osstream: SupportsSend[T2_co],
        /,
    ) -> Coroutine:
        raise NotImplementedError


@dataclass(slots=True, eq=False, repr=False, match_args=False)
class Transport(SupportsSend[T_contra], Generic[T_contra, T1_co, T2_co]):

    pipe: Pipe[T_contra, T1_co, T2_co]
    iosstream: SupportsSendAndRecv[T_contra, T_contra]
    omstream: SupportsSend[T1_co]
    osstream: SupportsSend[T2_co]

    def send(self, command: T_contra) -> Coroutine:
        return self.iosstream.send(command)

    def open(self) -> Coroutine:
        return self.pipe(self.iosstream, self.omstream, self.osstream)
