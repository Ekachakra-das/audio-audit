"""Shared import-time shims for resemble_enhance optional dependencies."""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import yaml


def _debug(msg, enabled):
    if enabled:
        print(msg, file=sys.stderr)


def apply_resemble_import_shims(emit_tqdm_progress=False, debug=False):
    # Resemble imports deepspeed but inference can run without it in this project.
    if "deepspeed" not in sys.modules:
        mock_ds = MagicMock()
        for m in [
            "deepspeed",
            "deepspeed.runtime",
            "deepspeed.runtime.engine",
            "deepspeed.runtime.zero.config",
            "deepspeed.accelerator",
            "deepspeed.runtime.utils",
        ]:
            sys.modules[m] = mock_ds
        _debug("DEBUG: Installed deepspeed mock", debug)

    if "tqdm" not in sys.modules:
        tqdm_mod = ModuleType("tqdm")

        def _trange(start, stop=None, step=1, **_kwargs):
            if stop is None:
                r = range(start)
            else:
                r = range(start, stop, step)
            total = len(r)
            last_percent = -1
            for idx, value in enumerate(r, start=1):
                if emit_tqdm_progress and total > 0:
                    percent = int((idx * 100) / total)
                    if percent != last_percent:
                        print(f"{percent}%|", file=sys.stderr)
                        sys.stderr.flush()
                        last_percent = percent
                yield value

        def _tqdm(it, **_kwargs):
            try:
                total = len(it)
            except Exception:
                total = None
            last_percent = -1
            for idx, value in enumerate(it, start=1):
                if emit_tqdm_progress and total:
                    percent = int((idx * 100) / total)
                    if percent != last_percent:
                        print(f"{percent}%|", file=sys.stderr)
                        sys.stderr.flush()
                        last_percent = percent
                yield value

        tqdm_mod.trange = _trange
        tqdm_mod.tqdm = _tqdm
        sys.modules["tqdm"] = tqdm_mod
        _debug("DEBUG: Installed tqdm shim", debug)

    if "omegaconf" not in sys.modules:
        omega_mod = ModuleType("omegaconf")

        class OmegaConfCompat:
            @staticmethod
            def load(path):
                p = Path(path)
                if not p.exists():
                    return {}
                with p.open("r", encoding="utf-8") as f:
                    # ReSemble hparams can contain python tags (e.g. pathlib.PosixPath).
                    return yaml.unsafe_load(f) or {}

            @staticmethod
            def merge(base, override):
                base_dict = {}
                if isinstance(base, dict):
                    base_dict.update(base)
                elif hasattr(base, "__dict__"):
                    base_dict.update(vars(base))
                if isinstance(override, dict):
                    base_dict.update(override)
                return base_dict

            @staticmethod
            def save(data, path):
                p = Path(path)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("w", encoding="utf-8") as f:
                    yaml.safe_dump(data, f, sort_keys=False)

        omega_mod.OmegaConf = OmegaConfCompat
        sys.modules["omegaconf"] = omega_mod
        _debug("DEBUG: Installed omegaconf shim", debug)

    if "rich" not in sys.modules:
        rich_mod = ModuleType("rich")
        rich_mod.__path__ = []
        rich_console_mod = ModuleType("rich.console")
        rich_panel_mod = ModuleType("rich.panel")
        rich_table_mod = ModuleType("rich.table")
        rich_logging_mod = ModuleType("rich.logging")

        class Console:
            def print(self, *_args, **_kwargs):
                return None

        class Table:
            def __init__(self, *args, **kwargs):
                self.rows = []

            def add_column(self, *_args, **_kwargs):
                return None

            def add_row(self, *args, **_kwargs):
                self.rows.append(args)

        class Panel:
            def __init__(self, obj, **_kwargs):
                self.obj = obj

        class RichHandler:
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        rich_console_mod.Console = Console
        rich_panel_mod.Panel = Panel
        rich_table_mod.Table = Table
        rich_logging_mod.RichHandler = RichHandler

        sys.modules["rich"] = rich_mod
        sys.modules["rich.console"] = rich_console_mod
        sys.modules["rich.panel"] = rich_panel_mod
        sys.modules["rich.table"] = rich_table_mod
        sys.modules["rich.logging"] = rich_logging_mod
        _debug("DEBUG: Installed rich shim", debug)

    if "tabulate" not in sys.modules:
        tabulate_mod = ModuleType("tabulate")
        tabulate_mod.__version__ = "0.9.0"
        tabulate_mod.tabulate = lambda *_args, **_kwargs: ""
        sys.modules["tabulate"] = tabulate_mod
        _debug("DEBUG: Installed tabulate shim", debug)
