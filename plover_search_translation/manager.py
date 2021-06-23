"""
Handle the parts unrelated to interprocess communication in the parent process
(leave the parts related to interprocess communication to .communicate.Process)
and also Plover's extension plugin entry point.
"""


from __future__ import annotations

import traceback
import typing
if typing.TYPE_CHECKING:
	from plover.engine import StenoEngine  # type: ignore
	from typing import Optional, List, Dict, Union, Tuple, Any
	from .lib import Entry
	from .dictionary import Dictionary

from .communicate import Process

from .lib import with_print_exception


class Manager:
	def __init__(self, engine: StenoEngine):
		self._engine: StenoEngine=engine
		self._process: Optional[Process]=None
		self._dictionary: Optional[Dictionary]=None

		from plover import config  # type: ignore
		config.Config._OPTIONS["plover_search_translation_column_width"]=config.json_option(
			"plover_search_translation_column_width",
			lambda config, key: None,
			"Plugin: Search Translation",
			"column_width",
			lambda config, key, value: value
			)

	def start(self):
		"""
		Called when Plover starts (or the extension plugin is enabled)
		"""
		assert self._process is None
		self._process=Process()

		self._process.on_pick=self.on_pick
		self._process.on_add=self.on_add
		self._process.on_remove=self.on_remove
		self._process.on_search=self.on_search
		self._process.lookup=self.lookup
		self._process.show_error=self.show_error

		self._process.get_column_width=self.get_column_width
		self._process.save_column_width=self.save_column_width

		self._dictionary=None

		global instance
		instance=self

	def ensure_active_dictionary(self, dictionary: Dictionary)->None:
		assert self._engine.dictionaries[dictionary.path] is dictionary

	@with_print_exception #if stop() fails then Plover will not exit...?
	def stop(self):
		"""
		Called (from Plover) when Plover stops (or the extension plugin is disabled)
		"""
		global instance
		instance=None
		self._process.exit()
		self._process=None

	def save_column_width(self, value: Any)->None:
		self._engine["plover_search_translation_column_width"]=value

	def get_column_width(self)->Any:
		return self._engine["plover_search_translation_column_width"]

	def show_error(self, message: str)->None:
		from plover import log  # type: ignore
		log.error(message)

	def on_pick(self, entry: Optional[Entry])->None:
		assert self._dictionary is not None

		self._dictionary=None

		if entry is None:
			# Window closed (canceled)
			return

		assert entry.valid()
		mapping=entry.translation

		try:
			with self._engine:
				from plover.steno import Stroke  # type: ignore
				from plover.translation import _mapping_to_macro, Translation  # type: ignore
				stroke = Stroke([]) # required, because otherwise Plover will try to merge the outlines together
				# and the outline [] (instead of [Stroke([])]) can be merged to anything
				macro = _mapping_to_macro(mapping, stroke)
				if macro is not None:
					self._engine._translator.translate_macro(macro)
					return
				t = (
					#self._engine._translator._find_translation_helper(stroke) or
					#self._engine._translator._find_translation_helper(stroke, system.SUFFIX_KEYS) or
					Translation([stroke], mapping)
				)
				self._engine._translator.translate_translation(t)
				self._engine._translator.flush()
				#self._engine._trigger_hook('stroked', stroke)

		except:
			traceback.print_exc()

	def on_add(self, entry: Entry)->None:
		assert self._dictionary is not None
		self._dictionary.add(entry)
		self._dictionary.save()

	def on_remove(self, entry: Entry)->None:
		assert self._dictionary is not None
		self._dictionary.remove(entry)
		self._dictionary.save()

	def on_search(self, query: str)->List[Entry]:
		assert self._dictionary is not None
		return self._dictionary.search(query)

	def lookup(self, outline: Tuple[str, ...])->Optional[str]:
		assert outline
		try:
			return self._engine.dictionaries.raw_lookup(outline)
		except:
			print(">>", outline)
			traceback.print_exc()
			return None

	def close_dialog(self)->None:
		assert self._process
		assert self._dictionary is not None
		self._process.close_dialog()
		self._dictionary=None

	def show(self, dictionary: Union[str, Dictionary])->None:
		if self._dictionary is not None:
			raise RuntimeError(f"Another search dialog is visible -- {self._dictionary.path}")
		self._dictionary=(
				self._engine.dictionaries[dictionary]
				if isinstance(dictionary, str) else dictionary)
		assert self._dictionary is not None
		assert self._process is not None
		self._process.open_dialog()

	def is_showing(self, dictionary: Dictionary)->bool:
		return self._dictionary is dictionary



instance: Optional[Manager]=None

def get()->Manager:
	if instance is None:
		raise RuntimeError("Extension plugin for plover-search-translation is not running")
	return instance
