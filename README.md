# standby-variables

Dynamic variables for static namespaces.

## About

standby-variables is a tiny library for declaring dynamic values (like environment variables) in static, typed namespaces (like Python classes).

- Treat environment configuration as first-class, typed values.
- Compose behavior with a small and expressive API.
- Keep your code statically analyzable: every variable has a concrete type, and mypy understands it.

You get:

- Plain attributes on classes that evaluate lazily.
- A consistent way to make variables optional or provide defaults.
- Validation and error messages that carry useful context.
- Building blocks to extend beyond environment variables.

## Rationale

Most applications mix a static structure (modules, classes) with dynamic sources (env vars, files, CLI args).
It’s tempting to sprinkle `os.environ.get(...)` everywhere - but that dilutes typing, validation, and clarity.

With standby-variables your dynamic values become explicit and composable:

- Declare what a variable is, how it’s parsed, and what to do if it’s missing.
- Chain behavior using two operators:
    * `>>` to apply "hints" (Default, Required, Validated)
    * `|` to provide a backup variable
- Keep strong typing across your configuration surface.
- Use dataclass-like descriptors that work as class attributes and cache nothing implicitly.

The result is readable configuration code that feels like constants, but evaluates at runtime.

## Basic usage and syntax

- Every dynamic value is a `Variable[T]` for some type `T`.
- You can "extract" the runtime value by either:
    * Calling the variable: `var()` (may return `None` if defined as not required),
    * Or forcing the value: `var.value()` (never returns `None`; raises if unavailable).
- String representations include context, and exceptions propagate that context upward, which makes debugging easier.

### Hints

- `Default(value)` returns the default when the source is missing.
- `Required(True)` (default) means the variable must be present.
- `Required(False)` means "optional": `var()` can return `None`.
- `Validated(predicate, raises=True)` ensures values pass a check.
- `Validated(predicate, raises=False)` can "nullify" invalid values (returning `None` via `.__call__`) which you can then back up with `|` or keep as `None` if optional.

Example:

```python
import os
from standby import Const
from standby.hint import Default, Required, Validated
from standby import env

# simulate environment
os.environ.setdefault("APP_PORT", "8080")

def parse_bool(s: str) -> bool:
    return s.strip() in {"1", "true", "yes", "on", "True"}

class Settings:
    # A required int, with a default when missing
    PORT: int =~ (env.Var("APP_PORT", int) >> Default(8000))

    # Optional bool: returns None if missing
    DEBUG: bool | None =~ (env.Var("APP_DEBUG", parse_bool) >> Required(False))

    # A purely static value with validation
    TIMEOUT: int =~ (Const(10) >> Validated(lambda v: v > 0))

print(Settings.PORT)   # 8080 (from env), defaults to 8000 if unset
print(Settings.DEBUG)  # None if APP_DEBUG is missing; True/False otherwise
print(Settings.TIMEOUT)  # 10
```

Backups with `|`:

```python
from standby import env, Const

class Settings:
    class API:
        # Prefer ENV var; if missing, use a constant fallback
        URL: str =~ (env.Var("API_URL", str) | Const("https://api.example.com"))
        
print(Settings.API.URL)  # Returns ENV value if present, otherwise fallback
```

Forcing with `.value()`:

```python
from standby import env
from standby.exc import VariableNotSet

try:
    must_have_port = env.Var[int]("MUST_HAVE_PORT", int).value()
except VariableNotSet as e:
    # Rich context in e.args for easier debugging
    print("Missing env:", e.args)
```

## Type safety

Every variable is parameterized by its type, and mypy can verify usage end-to-end.

You might have noticed a weird operator `=~` used in example of `Settings` class.

In fact, it is two distinct operators: `=` and `~` joined together due to subjective preference.
It is possible to have `~` attached to Variable definition like:

    URL: str = ~(...)  # this is why expression is inside parenthesis

The role of this operator is to instruct type checker that nothing wrong happens when we define `Variable[T]` as its
wrapped type `T`. When you access a variable via parent class/instance, Python invokes `__get__()` descriptor 
method which is implemented for all basic primitives in `standby`. So, reading the value `T` "dynamically" happens just 
by accessing its container `Variable[T]` which is initialized together with its parent class. You can think about it as 
a special case of "class property".

```python
from standby import Const
from standby.hint import Default, Required, Validated
from standby import env

def parse_bool(s: str) -> bool:
    return s.strip() in {"1", "true", "yes", "on", "True"}

class Settings:
    # Expression has real type Variable[int] but defined inside a class as just int 
    PORT: int =~ (env.Var("APP_PORT", int) >> Default(8000))

    # Expression has real type Variable[bool] but is set to "bool | None" because it's hinted with Required(false)
    # Currently, unary operator casting to "T | None" is not implemented
    # Type checker (mypy) allows result of cast(T, ...) to be assigned a "T | None" type
    DEBUG: bool | None =~ (env.Var("APP_DEBUG", bool) >> Required(False))
```


## Environment variables

The `standby.env` module provides handy tools to read from `os.environ`.

- `env.Var[T](name, parser)` reads `os.environ[name]` and parses it into type `T`.
- `env.SeparatedList[T]` takes a source `Variable[str]`, splits by a given `split_sep` (`,` by default), and parses each element.
- `env.Ref[T]` takes a source `Variable[str]` and uses its value to find another environment variable with that name.

```python
import base64
from standby import Const
from standby.hint import Default, Required
from standby import env

# Required int with a default
POOL_SIZE = env.Var[int]("DB_POOL_SIZE", int) >> Default(5)

# Optional boolean
USE_CACHE = env.Var[bool]("USE_CACHE", lambda s: s == "1") >> Required(False)

# ALLOWED_HOSTS="example.com, api.example.com, localhost"
ALLOWED_HOSTS = env.SeparatedList[str](
    src=env.Var("ALLOWED_HOSTS", str),  # read raw string from env
    split_sep=",",
    parser=lambda s: s.strip(),     # trim each piece
)

# Default to ["localhost"] if the variable is missing
ALLOWED_HOSTS_WITH_DEFAULT = ALLOWED_HOSTS >> Default(["localhost"])

# If ALLOWED_HOSTS is missing, and you want "optional list" semantics:
OPTIONAL_HOSTS = ALLOWED_HOSTS >> Required(False)  # .__call__ returns None

# SECRET_ENV_VAR="<AUTO_GENERATED_VARIABLE_WITH_SECRET_VALUE_IN_BASE64>"
SECRET = env.Ref(
    src=env.Var("SECRET_ENV_VAR", str),  # taking the secret var name here
    parser=base64.b64decode,  # decoding it to bytes
)

decoded_secret: bytes = SECRET()

```

## Link and List customization

`env.Ref` and `env.SeparatedList` are built from `standby` primitives: `Link` and `List`.
Links let one variable refer to another variable’s name.
This is handy for indirection (think: "the name of the variable that contains the key").

- `Link[T, S]`: a generic link-variable where:
    * `src` yields some `S`;
    * `linker` maps that `S` to another `Variable[T]`.
- `List[T, P, S]`: a generic list-variable where:
    * `src` yields some `S`;
    * `S` is split in parts of `P` by a `splitter` function given as keyword arg;
    * Each `P` part is parsed to `T` by a `parser` function given as keyword arg;
    * `T` items are used to create a new `Variable[list[T]]`.

Custom link can be used like this:

```python
import os
from standby import Link, env, exc, hint, Variable

# Suppose "WORKERS_VAR" contains the name of another env var that holds an int.
# e.g. WORKERS_VAR="MAX_WORKERS", and MAX_WORKERS="16"
ENV_INT = env.Var.factory(parser=int)
MAX_WORKERS = Link(
    src=env.Var("WORKERS_VAR", str),  # the name of the target var
    linker=ENV_INT,  # how to create Var[int] from the name
)
try:
    print(MAX_WORKERS())
except exc.VariableNotSet:
    # Missing source raises exception
    raise

# Now let's parse a list with worker args
# Supposing it is stored in environment variable with a name we don't know now
# We know that this variable will be also put in environment as WORKER_ARGS_VAR

# Prepare parser for our list
ENV_LIST_STR = env.SeparatedList.factory(split_sep=",", parser=str)

# Define a Link variable
OPTIONAL_WORKER_ARGS: Variable[list[str]] = Link(
    src=env.Var("WORKER_ARGS_VAR", str) >> hint.Required(False),
    linker=ENV_LIST_STR
)

# WORKER_ARGS_VAR is not set and not required
# Link returns None:
assert OPTIONAL_WORKER_ARGS() is None

# Now, set WORKER_ARGS_VAR to empty string
os.environ["WORKER_ARGS_VAR"] = ""

# env.SeparatedList considers empty/whitespace source as empty list
# (natively, Python str.split implementation returns a list [""] with empty string)
assert OPTIONAL_WORKER_ARGS() == []
```

Custom lists:

```python
import os
from pathlib import Path
from standby import List
from standby.env import Var

# PATH-like variables
os.environ["PLUGIN_PATHS"] = "/opt/plugins:/usr/local/plugins:/tmp/plugins"

PATH_LIST = List[Path, str, str](
    src=Var("PLUGIN_PATHS", str),
    splitter=lambda s: s.split(":"),     # use ':' as a separator
    parser=Path,                         # create a Path from each part
)

print(PATH_LIST())  # [PosixPath('/opt/plugins'), PosixPath('/usr/local/plugins'), PosixPath('/tmp/plugins')]

# empty string returns a list with single element as expected from Python str.split() 
os.environ["PLUGIN_PATHS"] = ""

print(PATH_LIST())  # [PosixPath('.')]


```

Summary on semantics:

- If the source variable of a `List` or `Link` is missing:
    * Without hints, a `VariableNotSet` error is raised;
    * With `Required(False)` on the source, it returns `None`;
    * With `Default([...])` on the result variable, the default is used.

## Development

This project uses a src/ layout and provides optional development dependencies for testing and type checking.

### Setup

#### Create and activate a virtual environment
    
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate

#### Install in editable mode with dev extras

    pip install -e .[dev]

### Run tests with coverage

Run tests:

    pytest

By default, pytest is configured (via pyproject.toml) to:

- discover tests in the test/ directory,
- run with branch coverage for the standby package,
- show missing lines (term-missing)

To run without coverage flags, use:

    pytest -q

### Type checking

Run mypy on the package sources:

    mypy

or explicitly:

    mypy src/standby


### Linting

Check linting with ruff:

    ruff lint

Check and fix if possible:

    ruff link --fix


### Tox

Tox allows to run all checks on all supported Python versions:

    tox

Make sure you have all Python versions installed before running Tox.

Recommended way is to use [pyenv](https://github.com/pyenv/pyenv).