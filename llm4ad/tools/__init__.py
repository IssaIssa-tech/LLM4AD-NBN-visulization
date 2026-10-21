from __future__ import annotations

import importlib as _importlib
import inspect as _inspect

__all__: list[str] = []

# ``llm`` eagerly imports every LLM backend (some pull in torch / heavy SDKs);
# ``profiler`` is light. Load both lazily so importing e.g.
# ``llm4ad.tools.profiler`` does not pay for the LLM backends.
_SUBMODULES = ("llm", "profiler")


def _load(name: str):
    module = _importlib.import_module(f".{name}", __name__)
    for attr_name, attr in vars(module).items():
        if _inspect.isclass(attr) and getattr(attr, "__module__", "") == module.__name__:
            globals()[attr_name] = attr
    return module


def __getattr__(name):
    if name in _SUBMODULES:
        module = _load(name)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(globals().keys()) + list(_SUBMODULES)))
