from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from .core import Hint, Variable
from .exc import ValueNotValid, VariableNotSet

__all__ = ["Default", "Required", "Validated"]


R = TypeVar("R")
T = TypeVar("T")


@dataclass(frozen=True)
class Default(Hint[T]):
    value: T

    def wrap(self, variable: Variable[T]) -> Variable[T]:
        return self._Wrapper(variable, self.value)

    @dataclass(frozen=True)
    class _Wrapper(Variable[R]):
        variable: Variable[R]
        default: R

        def value(self) -> R:
            try:
                return self.variable.value()
            except VariableNotSet:
                return self.default

        def __str__(self) -> str:
            return f"Default({self.default})"

        def __repr__(self) -> str:
            return f"{repr(self.variable)}>>{self}"

        def __call__(self) -> R | None:
            try:
                value = self.variable()
            except VariableNotSet:
                return self.default
            return self.default if value is None else value


@dataclass(frozen=True)
class Required(Hint):
    is_required: bool = True

    def wrap(self, variable: Variable[T]) -> Variable[T]:
        return variable if self.is_required else self._Wrapper(variable)

    @dataclass(frozen=True)
    class _Wrapper(Variable[T]):
        variable: Variable[T]

        def __str__(self) -> str:
            return f"Required({False})"

        def __repr__(self) -> str:
            return f"{repr(self.variable)}>>{self}"

        def value(self) -> T:
            return self.variable.value()

        def __call__(self) -> T | None:
            try:
                return self.variable()
            except VariableNotSet:
                return None


@dataclass(frozen=True)
class Validated(Hint[T]):
    validator: Callable[[T], bool]
    raises: bool = True

    def wrap(self, variable: Variable[T]) -> Variable[T]:
        return self._Wrapper(variable, self.validator, self.raises)

    @dataclass(frozen=True)
    class _Wrapper(Variable[R]):
        variable: Variable[R]
        validator: Callable[[R], bool]
        raises: bool = True

        def __str__(self) -> str:
            return (f"Validated({self.validator.__name__},"
                    f"{'raises' if self.raises else 'returns None'} on invalid value)")

        def __repr__(self) -> str:
            return f"{repr(self.variable)}>>{self}"

        def value(self) -> R:
            if self.validator(value := self.variable.value()):
                return value
            else:
                raise ValueNotValid(value)

        def __call__(self) -> R | None:
            value = self.variable()
            if value is None:
                return None
            elif self.validator(value):
                return value
            elif self.raises:
                raise ValueNotValid(value, repr(self))
            else:
                return None
