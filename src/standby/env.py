from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

from .core import Link, List, Variable
from .exc import VariableNotSet

__all__ = ["Var", "SeparatedList", "Ref"]


T = TypeVar("T")


@dataclass(frozen=True)
class Var(Generic[T], Variable[T]):
    name: str
    parser: Callable[[str], T]

    def value(self) -> T:
        try:
            return self.parser(os.environ[self.name])
        except KeyError:
            raise VariableNotSet(self.name, repr(self))

    def __str__(self) -> str:
        return f"env.Var({self.name},{self.parser.__name__})"

    def __repr__(self) -> str:
        return f"env.Var({self.name},{self.parser.__name__})"


def _splitter_factory(sep: str) -> Callable[[str], list[str]]:
    def split_after_strip_if_not_empty(src: str) -> list[str]:
        if src := src.strip():
            return src.split(sep)
        else:
            return []

    return split_after_strip_if_not_empty


@dataclass(frozen=True)
class SeparatedList(List[T, str, str]):
    split_sep: str = ","
    splitter: Callable[[str], list[str]] = _splitter_factory(split_sep)

    def __str__(self) -> str:
        return f"env.SeparatedList({self.src},{self.splitter.__name__},{self.split_sep},{self.parser.__name__})"

    def __repr__(self) -> str:
        return f"env.SeparatedList({repr(self.src)},{self.splitter.__name__},{self.split_sep},{self.parser.__name__})"


@dataclass(frozen=True)
class Ref(Link[T, str]):
    src: Variable[str]
    parser: Callable[[str], T] = field(kw_only=True)
    linker: Callable[[str], Var[T]] = Var.factory(parser=parser)

    def __str__(self) -> str:
        return f"env.Ref({self.src},{self.linker.__name__},{self.parser.__name__})"

    def __repr__(self) -> str:
        return f"env.Ref({repr(self.src)},{self.linker.__name__},{self.parser.__name__})"
