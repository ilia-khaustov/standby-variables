import importlib
import types

import standby as sb
from standby import (
    Const,
    Link,
    List,
    Variable,
    env,
    exc,
    hint,
)


def test_dunder_all_exports():
    expected = [
        "Const",
        "Link",
        "List",
        "Variable",
        "env",
        "exc",
        "hint",
    ]
    # Ensure the __all__ names are present
    assert sorted(sb.__all__) == sorted(expected)
    for name in expected:
        assert hasattr(sb, name)


def test_imported_symbols_match_module():
    # Just ensure we can import and reference everything
    assert Const is sb.Const
    assert Link is sb.Link
    assert List is sb.List
    assert Variable is sb.Variable

    assert isinstance(env, types.ModuleType)
    assert hasattr(env, "Var")
    # ensure re-import works (package properly installed)
    assert importlib.import_module("standby.env") is env

    assert isinstance(exc, types.ModuleType)
    assert hasattr(exc, "StandbyError")
    # ensure re-import works (package properly installed)
    assert importlib.import_module("standby.exc") is exc

    assert isinstance(hint, types.ModuleType)
    assert hasattr(hint, "Default")
    # ensure re-import works (package properly installed)
    assert importlib.import_module("standby.hint") is hint
