from __future__ import annotations

import abc
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import partial, wraps
from typing import Any, Callable, Generic, Self, TypeVar, cast, overload

from .exc import StandbyError, VariableNotSet

P = TypeVar("P")
S = TypeVar("S")
T = TypeVar("T")


class Variable(Generic[T], ABC):
    @abstractmethod
    def value(self) -> T:  # pragma: no cover
        raise NotImplementedError()

    @abstractmethod
    def __str__(self) -> str:  # pragma: no cover
        raise NotImplementedError()

    @abstractmethod
    def __repr__(self) -> str:  # pragma: no cover
        raise NotImplementedError()

    def __call__(self) -> T | None:
        return self.value()

    @overload
    def __get__(self, instance: None, owner: type[object]) -> T: ...

    @overload
    def __get__(self, instance: object, owner: type[object]) -> T: ...

    def __get__(self, instance: object | None, owner: type[object]) -> T | None:
        return self()

    def __rshift__(self, hint: Hint[T]) -> Variable[T]:
        return hint.wrap(self)

    def __or__(self, backup: Variable[T]) -> _BackupWrapper[T]:
        return _BackupWrapper(self, backup)

    def __invert__(self) -> T:
        return cast(T, self)

    @classmethod
    def factory(cls, *args: Any, **kwargs: Any) -> Callable[[Any], Self]:
        return wraps(cls)(partial(cls, *args, **kwargs))


@dataclass(frozen=True)
class _BackupWrapper(Variable[T]):
    variable: Variable[T]
    backup: Variable[T]

    def __str__(self) -> str:
        return repr(self.backup)

    def __repr__(self) -> str:
        return f"{repr(self.variable)}|{self}"

    def value(self) -> T:
        try:
            return self.variable.value()
        except VariableNotSet:
            return self.backup.value()

    def __call__(self) -> T | None:
        try:
            value = self.variable()
        except VariableNotSet:
            value = self.backup()
            if value is None:
                # VariableNotSet means that wrapped variable is required
                raise  # even if backup is not
            return value
        return self.backup() if value is None else value


class Hint(Generic[T], abc.ABC):
    @abc.abstractmethod
    def wrap(self, variable: Variable[T]) -> Variable[T]:  # pragma: no cover
        raise NotImplementedError()


@dataclass(frozen=True)
class Const(Variable[T]):
    val: T

    def value(self) -> T:
        return self.val

    def __str__(self) -> str:
        return f"Const({self.val})"

    def __repr__(self) -> str:
        return f"Const[{type(self.val).__name__}]({self.val})"


@dataclass(frozen=True)
class List(Generic[T, P, S], Variable[list[T]]):
    src: Variable[S]
    splitter: Callable[[S], list[P]] = field(kw_only=True)
    parser: Callable[[P], T] = field(kw_only=True)

    def value(self) -> list[T]:
        try:
            return list(map(self.parser, self.splitter(self.src.value())))
        except StandbyError as exc:
            exc.args += (repr(self),)
            raise exc

    def __call__(self) -> list[T] | None:
        try:
            value = self.src()
        except StandbyError as exc:
            exc.args += (repr(self),)
            raise exc
        return list(map(self.parser, self.splitter(value))) if value is not None else None

    def __str__(self) -> str:
        return f"List({str(self.src)},{self.splitter.__name__},{self.parser.__name__})"

    def __repr__(self) -> str:
        return f"List({repr(self.src)},{self.splitter.__name__},{self.parser.__name__})"


@dataclass(frozen=True)
class Link(Generic[T, S], Variable[T]):
    src: Variable[S]
    linker: Callable[[S], Variable[T]] = field(kw_only=True)

    def value(self) -> T:
        try:
            return self.linker(self.src.value()).value()
        except StandbyError as exc:
            exc.args += (repr(self),)
            raise exc

    def __call__(self) -> T | None:
        try:
            if src := self.src():
                return self.linker(src)()
            return None
        except StandbyError as exc:
            exc.args += (repr(self),)
            raise exc

    def __str__(self) -> str:
        return f"Link({self.src},{self.linker.__name__})"

    def __repr__(self) -> str:
        return f"Link({repr(self.src)},{self.linker.__name__})"
