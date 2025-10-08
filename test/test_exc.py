import pytest

from standby.exc import (
    StandbyError,
    ValueNotValid,
    VariableNotSet,
)


def test_exception_hierarchy():
    assert issubclass(VariableNotSet, StandbyError)
    assert issubclass(ValueNotValid, StandbyError)


def test_exceptions_can_be_raised_and_caught():
    with pytest.raises(VariableNotSet) as e:
        raise VariableNotSet("NAME", "repr")
    assert e.value.args == ("NAME", "repr")

    with pytest.raises(ValueNotValid) as e:
        raise ValueNotValid("bad", "ctx")
    assert e.value.args == ("bad", "ctx")
