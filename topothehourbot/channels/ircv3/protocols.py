from __future__ import annotations

__all__ = ["IRCv3Stream"]

from abc import abstractmethod
from typing import Protocol

from channels import SupportsSend
from ircv3 import IRCv3CommandProtocol


class IRCv3Stream(SupportsSend[IRCv3CommandProtocol | str], Protocol):

    @property
    @abstractmethod
    def latency(self) -> float:
        raise NotImplementedError
