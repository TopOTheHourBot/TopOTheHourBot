from __future__ import annotations

__all__ = [
    "PathLike",
    "Configuration",
]

import dataclasses
import os
import pickle
from dataclasses import dataclass
from typing import Optional, Self

type PathLike = str | bytes | os.PathLike


@dataclass(slots=True, kw_only=True)
class Configuration:

    @classmethod
    def from_pickle(cls, path: PathLike, *, raise_not_found: bool = True) -> Self:
        try:
            with open(path, mode="rb") as file:
                parameters = pickle.load(file)
        except FileNotFoundError:
            if raise_not_found:
                raise
            return cls()
        else:
            assert isinstance(parameters, dict)
            return cls(**parameters)

    def into_pickle(self, path: PathLike, *, protocol: Optional[int] = pickle.HIGHEST_PROTOCOL) -> None:
        parameters = dataclasses.asdict(self)
        with open(path, mode="wb") as file:
            pickle.dump(parameters, file, protocol=protocol)
