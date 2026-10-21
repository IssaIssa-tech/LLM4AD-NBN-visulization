from __future__ import annotations

import importlib as _importlib
import inspect as _inspect

__all__: list[str] = []

# Method subpackages (e.g. eoh, funsearch, partevo). Imported lazily because
# eagerly importing all of them transitively pulls in torch / wandb /
# tensorboard / sklearn (~100s in a fresh process). ``from
# llm4ad.method.eoh import EoH`` still works unchanged; the heavy modules are
# only imported when the requested subpackage is actually accessed.
_SUBMODULES = (
    "eoh",
    "funsearch",
    "hillclimb",
    "lhns",
    "llamea",
    "mcts_ahd",
    "meoh",
    "mles",
    "moead",
    "nsga2",
    "partevo",
    "randsample",
    "reevo",
)


def _load(name: str):
    module = _importlib.import_module(f".{name}", __name__)
    # Mirror the old eager re-export: classes defined by the submodule become
    # importable as ``llm4ad.method.<ClassName>``.
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
