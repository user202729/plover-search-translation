"""
Handle Plover's command entry points.
"""


from __future__ import annotations

import typing
if typing.TYPE_CHECKING:
	from plover.engine import StenoEngine  # type: ignore

def show_search_dialog(engine: StenoEngine, argument: str)->None:
	from . import manager
	manager.get().show(argument)

def close_window(engine: StenoEngine, argument: str)->None:
	assert not argument
	from . import manager
	manager.get().close_window()
