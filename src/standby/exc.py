__all__ = ["StandbyError", "VariableNotSet", "ValueNotValid"]


class StandbyError(Exception):
    pass


class VariableNotSet(StandbyError):
    pass


class ValueNotValid(StandbyError):
    pass
