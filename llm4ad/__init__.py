from . import base

__version__ = '1.0.0'

# NOTE: `method`, `task` and the `tools` subpackages eagerly auto-import *every*
# submodule they contain (see their __init__.py files). That transitively pulls
# in torch, wandb, tensorboard and sklearn -- roughly 280s on the first import
# inside a fresh process. The evaluation, graph-build and external-expert-import
# paths only ever need `llm4ad.base`, so these heavy subpackages are deferred
# until first accessed (PEP 562). Real algorithm runs such as
# `from llm4ad.method.eoh import EoH` still import them on demand, unchanged.
import importlib as _importlib

_LAZY_SUBMODULES = ("method", "task", "tools")


def __getattr__(name):
    if name in _LAZY_SUBMODULES:
        module = _importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(globals().keys()) + list(_LAZY_SUBMODULES)))
