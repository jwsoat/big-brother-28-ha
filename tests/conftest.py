"""Load const.py/logic.py directly, without importing homeassistant.

The real custom_components/big_brother_28/__init__.py imports `homeassistant`,
which isn't installed in this test environment. Registering fake modules in
sys.modules *before* any test imports `custom_components.big_brother_28.*`
means Python's import system finds these cached stand-ins instead of
executing the real __init__.py.
"""
import importlib.util
import pathlib
import sys
import types

COMPONENT_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "big_brother_28"
)


def _register_stub_package() -> None:
    if "custom_components" not in sys.modules:
        pkg = types.ModuleType("custom_components")
        pkg.__path__ = []
        sys.modules["custom_components"] = pkg

    if "custom_components.big_brother_28" not in sys.modules:
        pkg = types.ModuleType("custom_components.big_brother_28")
        pkg.__path__ = [str(COMPONENT_DIR)]
        sys.modules["custom_components.big_brother_28"] = pkg


def _load_module(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, COMPONENT_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_register_stub_package()
_load_module("custom_components.big_brother_28.const", "const.py")
_load_module("custom_components.big_brother_28.logic", "logic.py")
