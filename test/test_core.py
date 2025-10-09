from __future__ import annotations

from typing import Callable, assert_type

import pytest

from standby.core import Const, Link, List
from standby.env import Var
from standby.exc import ValueNotValid, VariableNotSet
from standby.hint import Default, Required, Validated


def test_const_value_and_str_repr():
    c = Const[int](5)
    assert c.value() == 5
    assert c() == 5
    assert "Const(5)" == str(c)
    assert "Const[int](5)" == repr(c)


def test_rshift_hints_default(monkeypatch: pytest.MonkeyPatch):
    # Default: __call__ returns default when unavailable
    v = Var[int]("SBY_DEFAULT", int) >> Default(7)
    monkeypatch.delenv("SBY_DEFAULT", raising=False)
    assert v() == 7
    # When available, original value
    monkeypatch.setenv("SBY_DEFAULT", "8")
    assert v() == 8


def test_rshift_hints_required(monkeypatch: pytest.MonkeyPatch):
    # Required(True) returns self (identity)
    c = Const[int](10)
    same = c >> Required(True)
    assert same is c

    # Required(False): __call__ returns None if missing
    v_not_req = Var[int]("SBY_NOT_REQ", int) >> Required(False)
    monkeypatch.delenv("SBY_NOT_REQ", raising=False)
    assert v_not_req() is None
    # but .value() still raises
    with pytest.raises(VariableNotSet):
        (Var[int]("SBY_NOT_REQ", int) >> Required(False)).value()


def test_rshift_hints_validated(monkeypatch: pytest.MonkeyPatch):
    # Validated: passes when truthy and validator ok
    val_ok = Const[int](9) >> Validated(lambda x: x > 5)
    assert val_ok() == 9
    # Validated: falsy value passes
    val_ok_falsy = Const[int](0) >> Validated(lambda x: x >= 0)
    assert val_ok_falsy() == 0
    # Validated: None is passed as-is
    val_ok_none = Const[None](None) >> Validated(lambda x: x > 0)
    assert val_ok_none() is None
    # Validated: bad value is caught
    val_bad = Const[int](0) >> Validated(lambda x: x > 0)
    with pytest.raises(ValueNotValid) as e:
        val_bad()
    assert e.value.args[0] == 0
    assert "Validated(" in e.value.args[1]
    # Validated: bad value passed as None if raises set to False
    val_bad = Const[int](0) >> Validated(lambda x: x > 0, raises=False)
    assert val_bad() is None


def test_rshift_required_vs_validated(monkeypatch: pytest.MonkeyPatch):
    # Required(True) captures missing before Validated
    monkeypatch.delenv("SBY_REQ", raising=False)
    with pytest.raises(VariableNotSet):
        (Var[int]("SBY_REQ", int) >> Required(True) >> Validated(bool))()

    # Required(True) captures missing after Validated also
    monkeypatch.delenv("SBY_REQ", raising=False)
    with pytest.raises(VariableNotSet):
        (Var[int]("SBY_REQ", int) >> Validated(bool) >> Required(True))()

    # Required(False) re-raises after Validated raises on non-empty value
    with pytest.raises(ValueNotValid):
        (Const[int](1) >> Validated(lambda v: v > 1) >> Required(False))()


def test_rshift_validated_vs_default(monkeypatch: pytest.MonkeyPatch):
    positive_or_none = Validated(lambda x: x > 0, raises=False)
    # Validated: on raises=False value replaced with Default even if it fails validation
    val_bad = Const[int](0) >> positive_or_none >> Default(0)
    assert val_bad() == 0
    # Validated at the end of the chain captures invalid value
    val_none = Const[int](0) >> positive_or_none >> Default(0) >> positive_or_none
    assert val_none() is None


def test_or_backup(monkeypatch: pytest.MonkeyPatch):
    # main missing -> use backup
    main = Var[int]("SBY_MAIN", int)
    backup = Const[int](3)
    v = main | backup
    monkeypatch.delenv("SBY_MAIN", raising=False)
    assert v() == 3

    # main returns None (not required) -> use backup
    main_none = Var[int]("SBY_MAIN2", int) >> Required(False)
    v2 = main_none | backup
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    assert v2() == 3

    # main present -> keep main
    monkeypatch.setenv("SBY_MAIN", "11")
    assert (main | backup)() == 11

    # both missing and at least one required -> raise
    monkeypatch.delenv("SBY_MAIN", raising=False)
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    with pytest.raises(VariableNotSet):
        (main | main_none)()
    with pytest.raises(VariableNotSet):
        (main_none | main)()

    # both missing and not required -> return None
    monkeypatch.delenv("SBY_MAIN", raising=False)
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    assert ((main | main) >> Required(False))() is None
    assert (main_none | main_none)() is None


def test_or_backup_vs_validated(monkeypatch: pytest.MonkeyPatch):
    main = Var[int]("SBY_MAIN", int)
    backup = Const[int](10)

    # invalid value raises despite the backup
    monkeypatch.setenv("SBY_MAIN", "11")
    with pytest.raises(ValueNotValid):
        (main >> Validated(lambda x: x < 10) | backup)()

    # invalid value is replaced with backup if raises set to False regardless of backup value
    monkeypatch.setenv("SBY_MAIN", "11")
    less_than_10_or_none = Validated(lambda x: x < 10, raises=False)
    assert (main >> less_than_10_or_none | backup)() == 10

    # backup group validated together captures invalid value
    monkeypatch.setenv("SBY_MAIN", "11")
    assert ((main >> less_than_10_or_none | backup) >> less_than_10_or_none)() is None


def test_or_backup_value(monkeypatch: pytest.MonkeyPatch):
    # main missing -> use backup
    main = Var[int]("SBY_MAIN", int)
    backup = Const[int](3)
    v = main | backup
    monkeypatch.delenv("SBY_MAIN", raising=False)
    assert v.value() == 3

    # main returns None (not required) -> use backup
    main_none = Var[int]("SBY_MAIN2", int) >> Required(False)
    v2 = main_none | backup
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    assert v2.value() == 3

    # main present -> keep main
    monkeypatch.setenv("SBY_MAIN", "11")
    assert (main | backup).value() == 11

    # both missing -> raise
    monkeypatch.delenv("SBY_MAIN", raising=False)
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    with pytest.raises(VariableNotSet):
        (main | main_none).value()
    with pytest.raises(VariableNotSet):
        (main_none | main).value()

    # both missing and not required -> raise as value() should not return None
    monkeypatch.delenv("SBY_MAIN", raising=False)
    monkeypatch.delenv("SBY_MAIN2", raising=False)
    with pytest.raises(VariableNotSet):
        ((main | main_none) >> Required(False)).value()
    with pytest.raises(VariableNotSet):
        ((main_none | main) >> Required(False)).value()
    with pytest.raises(VariableNotSet):
        (main_none | main >> Required(False)).value()
    with pytest.raises(VariableNotSet):
        (main_none | main_none).value()


def test_list_behaviour(monkeypatch: pytest.MonkeyPatch):
    # Non-empty list
    monkeypatch.setenv("SBY_LIST2", "a,b,c")
    l1 = List[str, str, str](src=Var("SBY_LIST2", str), splitter=lambda s: s.split(","), parser=lambda s: s)
    assert l1() == ["a", "b", "c"]
    assert "List(" in str(l1)
    assert "List(" in repr(l1)

    # Empty or whitespace-only source -> empty list
    monkeypatch.setenv("SBY_EMPTY", "   ")
    l2 = List[str, str, str](
        src=Var("SBY_EMPTY", str), splitter=lambda s: s.strip().split(",") if s.strip() else [], parser=lambda s: s
    )
    assert l2() == []

    # Error from source is enriched
    monkeypatch.delenv("SBY_MISSING", raising=False)
    l3 = List[str, str, str](src=Var("SBY_MISSING", str), splitter=lambda s: [s], parser=lambda s: s)
    with pytest.raises(VariableNotSet) as e:
        l3()
    # args from original plus appended repr(list)
    assert e.value.args[0] == "SBY_MISSING"
    assert "env.Var(SBY_MISSING,str)" in e.value.args[1]
    assert "List(" in e.value.args[2]

    # If source is not required: return None
    monkeypatch.delenv("SBY_MISSING", raising=False)
    missing_var = Var("SBY_MISSING", str)
    l4_src_not_req = List[str, str, str](src=missing_var >> Required(False), splitter=lambda s: [s], parser=lambda s: s)
    assert l4_src_not_req() is None

    # List.value() raises VariableNotSet
    with pytest.raises(VariableNotSet) as e:
        l4_src_not_req.value()
    assert "env.Var(SBY_MISSING,str)" in e.value.args[1]
    assert "List(" in e.value.args[2]

    # If list itself is not required: return None
    monkeypatch.delenv("SBY_MISSING", raising=False)
    l5_not_req = List[str, str, str](src=missing_var, splitter=lambda s: [s], parser=lambda s: s) >> Required(False)
    assert l5_not_req() is None

def test_link_behaviour_success_and_errors(monkeypatch: pytest.MonkeyPatch):
    # Success
    monkeypatch.setenv("SBY_NAME", "SBY_VALUE")
    monkeypatch.setenv("SBY_VALUE", "123")
    link = Link[int, str](src=Var("SBY_NAME", str), linker=Var.factory(parser=int))
    assert link() == 123
    assert "Link(" in str(link)
    assert "Link(" in repr(link)

    # Source empty and not required -> None
    empty_src = Link[int, str](src=(Var("SBY_NONE", str) >> Required(False)), linker=Var.factory(parser=int))
    monkeypatch.delenv("SBY_NONE", raising=False)
    assert empty_src() is None
    # value() still raises -> VariableNotSet, enriched
    with pytest.raises(VariableNotSet) as e:
        empty_src.value()
    assert "env.Var(SBY_NONE,str)" in e.value.args[1]
    assert "Link(" in e.value.args[2]

    # Target missing -> VariableNotSet, enriched
    monkeypatch.setenv("SBY_NAME", "SBY_MISS_TARGET")
    monkeypatch.delenv("SBY_MISS_TARGET", raising=False)
    with pytest.raises(VariableNotSet) as e2:
        link()
    assert e2.value.args[0] == "SBY_MISS_TARGET"
    assert "env.Var(SBY_MISS_TARGET,int)" in e2.value.args[1]
    assert "Link(" in e2.value.args[2]


def test_descriptor_get_and_factory_and_invert(monkeypatch: pytest.MonkeyPatch):
    class Conf:
        A = Const[int](1)
        B = Var[int]("SBY_B", int) >> Default(5)

    monkeypatch.delenv("SBY_B", raising=False)

    # __get__ via class access (instance is None)
    assert Conf.A == 1
    assert Conf.B == 5
    # __get__ via instance access (instance is object)
    inst = Conf()
    assert inst.A == 1
    assert inst.B == 5

    # assert_type (static) - benign at runtime
    assert_type(Conf.A, int)
    assert_type(inst.B, int)

    # factory for Var
    mk_int_var: Callable[[str], Var[int]] = Var.factory(parser=int)
    assert mk_int_var.__name__ == Var.__name__
    mk = mk_int_var("SBY_FACTORY")
    monkeypatch.setenv("SBY_FACTORY", "77")
    assert isinstance(mk, Var)
    assert mk() == 77

    # __invert__ returns the same object (cast to value type)
    c = Const[int](9)
    assert ~c is c


def test_withdefault_value_returns_default_or_source(monkeypatch: pytest.MonkeyPatch):
    # Missing source -> .value() returns default
    monkeypatch.delenv("SBY_DEF_VAL", raising=False)
    v = Var[int]("SBY_DEF_VAL", int) >> Default(9)
    assert v.value() == 9

    # Present source -> .value() returns parsed source
    monkeypatch.setenv("SBY_DEF_VAL", "12")
    assert v.value() == 12


def test_notrequired_value_behaviour(monkeypatch: pytest.MonkeyPatch):
    # Present source -> .value() returns parsed source
    monkeypatch.setenv("SBY_NR_VAL", "5")
    v_present = Var[int]("SBY_NR_VAL", int) >> Required(False)
    assert v_present.value() == 5

    # Missing source -> .value() still raises VariableNotSet
    monkeypatch.delenv("SBY_NR_VAL2", raising=False)
    v_missing = Var[int]("SBY_NR_VAL2", int) >> Required(False)
    with pytest.raises(VariableNotSet):
        v_missing.value()


def test_validated_value_success_and_failure():
    def is_positive(x: int) -> bool:
        return x > 0

    ok = Const[int](10) >> Validated(is_positive)
    assert ok.value() == 10

    bad = Const[int](0) >> Validated(is_positive)
    with pytest.raises(ValueNotValid) as e:
        bad.value()
    # .value() raises with the bad value only (no context appended)
    assert e.value.args == (0,)


def test_repr_chaining_with_rshift_and_or():
    # rshift with Default
    r1 = Var[int]("SBY_R1", int) >> Default(7)
    assert repr(r1) == "env.Var(SBY_R1,int)>>Default(7)"

    # rshift with Required(False)
    r2 = Var[int]("SBY_R2", int) >> Required(False)
    assert repr(r2) == "env.Var(SBY_R2,int)>>Required(False)"

    # rshift with Validated using a named function
    def is_positive(x: int) -> bool:
        return x > 0

    r3 = Const[int](1) >> Validated(is_positive)
    assert repr(r3) == "Const[int](1)>>Validated(is_positive,raises on invalid value)"

    # or/backup chaining after rshift
    combined = (Var[int]("SBY_CHAIN", int) >> Default(7)) | Const[int](3)
    assert repr(combined) == "env.Var(SBY_CHAIN,int)>>Default(7)|Const[int](3)"


def test_given_equivalence_and_behavior(monkeypatch: pytest.MonkeyPatch):
    # given(Default(...)) behaves like >> Default(...)
    monkeypatch.delenv("SBY_GIVEN", raising=False)
    g1 = Var[int]("SBY_GIVEN", int).given(Default(7))
    g2 = Var[int]("SBY_GIVEN", int) >> Default(7)
    assert g1() == 7
    assert g1.value() == 7
    assert repr(g1) == repr(g2)

    # When present, original value wins
    monkeypatch.setenv("SBY_GIVEN", "9")
    assert g1() == 9
    assert g1.value() == 9

    # multiple hints preserve order, and repr matches >> chain
    monkeypatch.delenv("SBY_GIVEN2", raising=False)
    g3 = Var[int]("SBY_GIVEN2", int).given(Required(False), Validated(lambda v: v > 0, raises=False))
    g4 = Var[int]("SBY_GIVEN2", int) >> Required(False) >> Validated(lambda v: v > 0, raises=False)
    assert g3() is None
    assert repr(g3) == repr(g4)


def test_otherwise_equivalence_and_behavior(monkeypatch: pytest.MonkeyPatch):
    main = Var[int]("SBY_OW", int)
    backup = Const[int](5)

    # otherwise(...) behaves like | backup
    ow1 = main.otherwise(backup)
    ow2 = main | backup

    monkeypatch.delenv("SBY_OW", raising=False)
    assert ow1() == 5
    assert ow1.value() == 5
    assert repr(ow1) == repr(ow2)

    # main present -> keep main
    monkeypatch.setenv("SBY_OW", "12")
    assert ow1() == 12
    assert ow1.value() == 12

    # multiple backups preserve order, and repr matches | chain
    monkeypatch.delenv("SBY_OW", raising=False)
    backup2 = Const[int](1)
    ow3 = main.otherwise(backup, backup2)
    ow4 = main | backup | backup2
    assert repr(ow3) == repr(ow4)
