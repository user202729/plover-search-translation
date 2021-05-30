"""
Handle Plover's command entry points.
"""


from __future__ import annotations

import typing
if typing.TYPE_CHECKING:
	from plover.engine import StenoEngine

def show_search_dialog(engine: StenoEngine, argument: str)->None:
	from . import manager
	manager.get().show(argument)
