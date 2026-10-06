"""A minimal pytest substitute that runs inside Pyodide.

Why not ship pytest itself: its event-loop handling under Pyodide's webloop is
the most fragile part of the stack, and the course's test suite only uses four
pytest features (``tmp_path``, ``pytest.raises``, ``pytest.fail``, and an anyio
backend fixture). All four are a few lines to provide.

The usual cost of leaving pytest is losing assertion rewriting - the
introspection that turns ``assert a == b`` into a readable diff. Here that
costs almost nothing, because nearly every assertion in the suite already
carries an explicit message written to teach:

    assert provider.call_count == 2, (
        "A tool call must cause another provider call. ..."
    )

For the handful of bare assertions, we recover the source line instead, which
is enough to locate the failure.

This module is injected into the Pyodide filesystem and imported by the
worker; it is not part of the learner-visible course.
"""

from __future__ import annotations

import asyncio
import builtins
import inspect
import io
import linecache
import sys
import traceback
from pathlib import Path

# --------------------------------------------------------------- pytest shim


class _Raises:
    """Context manager standing in for ``pytest.raises``."""

    def __init__(self, expected):
        self.expected = expected
        self.value = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            name = getattr(self.expected, "__name__", str(self.expected))
            raise AssertionError(f"DID NOT RAISE {name}")
        if not issubclass(exc_type, self.expected):
            return False  # propagate: wrong exception type
        self.value = exc
        return True


class _Mark:
    """``pytest.mark.anyio`` and friends - decorators that do nothing here."""

    def __getattr__(self, _name):
        def decorator(fn=None, **_kwargs):
            return fn if fn is not None else (lambda f: f)

        decorator.__call__ = decorator
        return decorator


class _PytestModule:
    """The subset of the pytest API this course actually uses."""

    mark = _Mark()
    raises = _Raises

    @staticmethod
    def fixture(fn=None, **_kwargs):
        # Fixtures in this suite only provide the anyio backend name, which
        # the runner supplies directly. Keep the decorator inert.
        def wrap(f):
            f.__is_fixture__ = True
            return f

        return wrap(fn) if fn is not None else wrap

    @staticmethod
    def fail(message="", pytrace=True):
        raise AssertionError(message)

    @staticmethod
    def skip(reason=""):
        raise _Skipped(reason)


class _Skipped(Exception):
    pass


def install_pytest_shim() -> None:
    """Make ``import pytest`` resolve to the shim."""
    sys.modules["pytest"] = _PytestModule()


# ------------------------------------------------------------------ running


def _assertion_source(tb) -> str:
    """Return the source line of the deepest frame in a test file."""
    frames = traceback.extract_tb(tb)
    for frame in reversed(frames):
        if "/tests/" in frame.filename or frame.name.startswith("test_"):
            line = linecache.getline(frame.filename, frame.lineno).strip()
            return line
    return ""


def _describe_failure(exc: BaseException, tb) -> str:
    """Produce the most useful single message for a failed test."""
    if isinstance(exc, AssertionError):
        message = str(exc).strip()
        if message:
            return message
        # Bare assert: show the source line, the next best thing to pytest's
        # assertion rewriting.
        source = _assertion_source(tb)
        return f"assertion failed: {source}" if source else "assertion failed"
    return f"{type(exc).__name__}: {exc}"


class TestResult:
    __slots__ = ("name", "passed", "message", "error_type", "traceback")

    def __init__(self, name, passed, message="", error_type="", tb=""):
        self.name = name
        self.passed = passed
        self.message = message
        self.error_type = error_type
        self.traceback = tb

    def to_dict(self):
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "errorType": self.error_type,
            "traceback": self.traceback,
        }


_TMP_COUNTER = 0


def _fresh_tmp_path() -> Path:
    """A per-test scratch directory, mirroring pytest's ``tmp_path``."""
    global _TMP_COUNTER
    _TMP_COUNTER += 1
    path = Path(f"/tmp/ha-{_TMP_COUNTER}")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_kwargs(fn) -> dict:
    """Supply the fixtures this suite uses, by parameter name."""
    kwargs = {}
    for name in inspect.signature(fn).parameters:
        if name == "tmp_path":
            kwargs[name] = _fresh_tmp_path()
        elif name == "anyio_backend":
            kwargs[name] = "asyncio"
        elif name == "monkeypatch":
            kwargs[name] = _MonkeyPatch()
    return kwargs


class _MonkeyPatch:
    """Enough of monkeypatch for attribute patching, with undo."""

    def __init__(self):
        self._undo = []

    def setattr(self, target, name, value, raising=True):
        old = getattr(target, name, None)
        self._undo.append((target, name, old))
        setattr(target, name, value)

    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


async def run_test_file(module_name: str) -> list[dict]:
    """Import a test module and run every ``test_*`` in it."""
    install_pytest_shim()

    # Always re-import: the learner's code changes between runs.
    for name in [n for n in sys.modules if n == module_name or n.startswith("test_")]:
        sys.modules.pop(name, None)

    results: list[TestResult] = []
    try:
        module = __import__(module_name)
    except BaseException as exc:  # a syntax error in learner code lands here
        return [
            TestResult(
                module_name,
                False,
                _describe_failure(exc, exc.__traceback__),
                type(exc).__name__,
                traceback.format_exc(limit=6),
            ).to_dict()
        ]

    tests = [
        (name, obj)
        for name, obj in vars(module).items()
        if name.startswith("test_") and callable(obj)
    ]
    tests.sort(key=lambda pair: getattr(pair[1], "__code__", None).co_firstlineno
               if hasattr(pair[1], "__code__") else 0)

    for name, fn in tests:
        # Each test gets fresh module state for the learner's modules, so one
        # test cannot leak into the next.
        try:
            kwargs = _build_kwargs(fn)
            outcome = fn(**kwargs)
            if inspect.isawaitable(outcome):
                await outcome
            results.append(TestResult(name, True))
        except _Skipped as exc:
            results.append(TestResult(name, True, f"skipped: {exc}"))
        except BaseException as exc:
            results.append(
                TestResult(
                    name,
                    False,
                    _describe_failure(exc, exc.__traceback__),
                    type(exc).__name__,
                    traceback.format_exc(limit=6),
                )
            )
        finally:
            patcher = kwargs.get("monkeypatch") if "kwargs" in dir() else None
            if isinstance(patcher, _MonkeyPatch):
                patcher.undo()

    return [r.to_dict() for r in results]


def reset_learner_modules(names: list[str]) -> None:
    """Drop cached learner modules so edited code is re-imported."""
    for name in names:
        sys.modules.pop(name, None)
