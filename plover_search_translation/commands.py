"""
Handle Plover's command entry points.
"""


from __future__ import annotations

import typing
if typing.TYPE_CHECKING:
	from plover.engine import StenoEngine  # type: ignore

def open_dialog(engine: StenoEngine, argument: str)->None:
	from . import manager
	manager.get().open_dialog(argument)

def close_dialog(engine: StenoEngine, argument: str)->None:
	assert not argument
	from . import manager
	manager.get().close_dialog()
