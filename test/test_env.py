
import pytest

from standby.core import Const
from standby.env import Ref, SeparatedList, Var, _splitter_factory
from standby.exc import VariableNotSet


def test_var_success_and_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SBY_INT", "42")
    v = Var[int]("SBY_INT", int)
    assert v() == 42
    assert v.value() == 42
    assert "env.Var(SBY_INT,int)" in str(v)
    assert "env.Var(SBY_INT,int)" in repr(v)

    monkeypatch.delenv("SBY_MISSING", raising=False)
    v_missing = Var[int]("SBY_MISSING", int)
    with pytest.raises(VariableNotSet) as e:
        v_missing()
    # args contain env var name and repr of Var
    assert e.value.args[0] == "SBY_MISSING"
    assert "env.Var(SBY_MISSING,int)" in e.value.args[1]


def test_splitter_factory_behavior():
    split = _splitter_factory(",")
    assert split(" a, b ,c ") == [
        "a, b ,c".strip().split(",")[0],
        " a, b ,c ".strip().split(",")[1],
        " a, b ,c ".strip().split(",")[2],
    ]
    # easier: empty and whitespace-only produce empty list
    assert split("") == []
    assert split("   ") == []

    # Use with parser to trim elements
    sep_list = SeparatedList[str](src=Const(" x, y ,  z "), parser=lambda s: s.strip())
    assert sep_list() == ["x", "y", "z"]


def test_separated_list_with_ints(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SBY_LIST", "1,2, 3")
    lst = SeparatedList[int](src=Var("SBY_LIST", str), parser=int)
    assert lst() == [1, 2, 3]
    # string forms
    assert "env.SeparatedList(" in str(lst)
    assert "env.SeparatedList(" in repr(lst)


def test_ref_str_and_repr_only():
    # Do not trigger value() because default linker uses a field placeholder.
    r = Ref[int](src=Const("ANY"), parser=int)
    assert "env.Ref(" in str(r)
    assert "env.Ref(" in repr(r)


def test_ref_value_with_explicit_linker(monkeypatch: pytest.MonkeyPatch):
    # Provide a correct linker explicitly
    monkeypatch.setenv("SBY_TARGET", "100")
    monkeypatch.setenv("SBY_REFNAME", "SBY_TARGET")
    ref = Ref[int](src=Var("SBY_REFNAME", str), parser=int, linker=Var.factory(parser=int))
    assert ref() == 100

    # Missing target produces enriched VariableNotSet error
    monkeypatch.setenv("SBY_REFNAME", "SBY_MISSING_TARGET")
    with pytest.raises(VariableNotSet) as e:
        ref_missing = Ref[int](src=Var("SBY_REFNAME", str), parser=int, linker=Var.factory(parser=int))
        ref_missing()
    # args initially from Var: (name, repr(var)), then Link adds repr(link/ref)
    assert e.value.args[0] == "SBY_MISSING_TARGET"
    assert "env.Var(SBY_MISSING_TARGET,int)" in e.value.args[1]
    assert "env.Link(" in e.value.args[2] or "env.Ref(" in e.value.args[2]
