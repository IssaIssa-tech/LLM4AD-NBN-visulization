from __future__ import annotations

import importlib as _importlib
import inspect as _inspect

__all__: list[str] = []

# LLM backend modules are heavy (some import torch / provider SDKs); import
# them lazily so ``from llm4ad.tools.llm.llm_api_https import HttpsApi`` only
# pays for the requested backend.
_SUBMODULES = ("llm_api_https", "llm_api_openai", "local_ollama", "zhipu_ai")


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
