"""
Handle the parts unrelated to interprocess communication in the parent process
(leave the parts related to interprocess communication to .communicate.Process)
and also Plover's extension plugin entry point.
"""


from __future__ import annotations

import sys
import subprocess
import traceback
import typing
if typing.TYPE_CHECKING:
	from plover.engine import StenoEngine  # type: ignore
	from typing import Optional, List, Dict, Union, Tuple, Any
	from .lib import Entry
	from .dictionary import Dictionary

from subprocess_connection import Message

from .lib import with_print_exception, Outline, inject_translation


class Manager:
	def __init__(self, engine: StenoEngine)->None:
		self._engine: StenoEngine=engine
		self._message: Optional[Message]=None
		self._dictionary: Optional[Dictionary]=None

		from plover import config  # type: ignore
		config.Config._OPTIONS["plover_search_translation_column_width"]=config.json_option(
			"plover_search_translation_column_width",
			lambda config, key: None,
			"Plugin: Search Translation",
			"column_width",
			lambda config, key, value: value
			)

		# The last translation that the user picked (explicitly by pressing [Pick]
		# or implicitly by pick_on_write)
		# Dictionaries can set this, but other programs should not
		self.last_translation: Optional[str]=None

	def start(self)->None:
		"""
		Called when Plover starts (or the extension plugin is enabled)
		"""
		assert self._message is None
		self._message=Message(
				subprocess.Popen([sys.executable, "-m", "plover_search_translation.process"],
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					)
				)

		self._message.register_call(self.show_error)
		self._message.register_call(self.remove_translation)
		self._message.register_call(self.picked)

		self._message.register_func(self.add_translation)
		self._message.register_func(self.edit_translation)
		self._message.register_func(self.search)
		self._message.register_func(self.lookup)

		self._message.register_call(self.save_column_width)
		self._message.register_func(self.get_column_width)

		self._message.start()

		self._dictionary=None

		global instance
		instance=self

	def ensure_active_dictionary(self, dictionary: Dictionary)->None:
		assert self._engine.dictionaries[dictionary.path] is dictionary

	@with_print_exception #if stop() fails then Plover will not exit...?
	def stop(self)->None:
		"""
		Called (from Plover) when Plover stops (or the extension plugin is disabled)
		"""
		global instance
		instance=None
		assert self._message
		self._message.stop()
		self._message=None

	def save_column_width(self, value: Any)->None:
		self._engine["plover_search_translation_column_width"]=value

	def get_column_width(self)->Any:
		return self._engine["plover_search_translation_column_width"]

	def show_error(self, message: str)->None:
		from plover import log  # type: ignore
		log.error(message)

	def picked(self, entry: Optional[Entry])->None:
		"""
		This function is called when the subprocess picks an entry.
		"""
		assert self._dictionary is not None

		self._dictionary=None

		if entry is None:
			# Window closed (canceled)
			return

		assert entry.valid()
		mapping=entry.translation

		try:
			inject_translation(self._engine, mapping)
			self.last_translation=mapping
		except:
			traceback.print_exc()

	def resend_last(self)->None:
		if self.last_translation is None:
			raise RuntimeError("There's no last_translation!")
		inject_translation(self._engine, self.last_translation)

	def add_translation(self, entry: Entry)->bool:
		assert self._dictionary is not None
		if not self._dictionary.add(entry):
			return False
		self._dictionary.save()
		return True

	def edit_translation(self, old: Entry, new: Entry)->bool:
		assert self._dictionary is not None
		if not self._dictionary.edit(old, new):
			return False
		self._dictionary.save()
		return True

	def remove_translation(self, entry: Entry)->None:
		assert self._dictionary is not None
		self._dictionary.remove(entry)
		self._dictionary.save()

	def search(self, query: str)->List[Entry]:
		assert self._dictionary is not None
		return self._dictionary.search(query)

	def lookup(self, outline: Outline)->Optional[str]:
		assert outline
		try:
			return self._engine.dictionaries.raw_lookup(outline)
		except:
			print(">>", outline)
			traceback.print_exc()
			return None

	def close_dialog(self)->None:
		assert self._message
		assert self._dictionary is not None
		self._message.func.close_dialog()
		self._dictionary=None

	def open_dialog(self, dictionary: Union[str, Dictionary])->None:
		if self._dictionary is not None:
			raise RuntimeError(f"Another search dialog is visible -- {self._dictionary.path}")
		self._dictionary=(
				self._engine.dictionaries[dictionary]
				if isinstance(dictionary, str) else dictionary)
		assert self._dictionary is not None
		assert self._message is not None
		self._message.call.open_dialog()

	def is_showing(self, dictionary: Dictionary)->bool:
		return self._dictionary is dictionary



instance: Optional[Manager]=None

def get()->Manager:
	if instance is None:
		raise RuntimeError("Extension plugin for plover-search-translation is not running")
	return instance
