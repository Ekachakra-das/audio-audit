
import sys
from unittest.mock import MagicMock
import types

class RecursiveMock(MagicMock):
    pass
    # Упрощенная версия, чтобы избежать RecursionError.
    # MagicMock сам по себе умеет возвращать моки на любые атрибуты.

# Создаем главный мок
mock_ds = MagicMock()

# Настраиваем sys.modules, чтобы Python думал, что модуль уже загружен
# Ставим заглушки на все основные пути, которые могут быть импортированы
modules_to_patch = [
    "deepspeed",
    "deepspeed.runtime",
    "deepspeed.runtime.engine",
    "deepspeed.runtime.zero",
    "deepspeed.runtime.zero.config",
    "deepspeed.ops",
    "deepspeed.ops.adam",
    "deepspeed.ops.op_builder",
    "deepspeed.accelerator",
    "deepspeed.runtime.utils"
]

def apply_mock():
    for module_name in modules_to_patch:
        sys.modules[module_name] = mock_ds
