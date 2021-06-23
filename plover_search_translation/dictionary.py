"""
Dictionary entry point for Plover.
"""

import sys
import json
from typing import Tuple, Dict, List, Optional, TypeVar, Callable, Any
import typing
from subprocess import Popen
import subprocess
from threading import Lock, Thread
import functools

from plover.steno_dictionary import StenoDictionary  # type: ignore

from . import manager
from .lib import Entry, with_print_exception


current_dictionary: Optional["Dictionary"]=None

T=TypeVar("T", bound=Callable)

def with_lock(function: T)->T:
	@functools.wraps(function)
	def result(self, *args, **kwargs)->Any:
		successful=self.lock.acquire(timeout=1)
		assert successful  # might be False in case of programming error (recursive lock?)
		try:
			return function(self, *args, **kwargs)
		finally:
			self.lock.release()
	return typing.cast(T, result)  # TODO?


class Dictionary(StenoDictionary):
	"""
	Dictionary class.
	"""
	def __init__(self)->None:
		super().__init__()
		
		self.search_stroke: str=""
		self.accept_stroke: str=""
		self.pick_on_write: bool=False
		"""
		Whether to pick an entry (and close the dialog immediately)
		when the dialog is open and the user write an outline in the current_dictionary.
		"""
		self.entries: List[Entry]=[]
		self.lock: Lock=Lock()
		"""
		A lock to ensure that there's no race condition when the dictionary is accessed
		or modified.
		"""

		self._longest_key=1

	@with_lock
	def __del__(self)->None:
		if manager.instance and manager.instance.is_showing(self):
			print("weird?")

	def _getitem(self, key: Tuple[str, ...])->str:
		"""
		Lookup an item by its brief (outline).

		Also return the command to close the dialog if it's opening.
		"""
		if key==(self.search_stroke,):
			manager.get().ensure_active_dictionary(self)
			return (
					"{:command:plover_search_translation_show_dialog:" +
					self.path.translate({
						ord("{"): r"\{",
						ord("}"): r"\}",
						}) +
					"}{^}")

		result=self._dict[key]  # might raise KeyError
		assert result is not None
		if self.pick_on_write and manager.instance and manager.instance.is_showing(self):
			result="{:command:plover_search_translation_close_dialog}"+result
			# (must close the dialog before sending the commands)
		return result

	@with_lock
	def __getitem__(self, key: Tuple[str, ...])->str:
		"""
		Like `_getitem`, but locked.
		"""
		return self._getitem(key)

	def get(self, key: Tuple[str, ...], default: Optional[str]=None)->Optional[str]:
		"""
		Lookup an item by its brief (outline).

		Uses another public method `__getitem__`, must not lock.
		"""
		try: result=self[key]
		except KeyError: return default
		assert result is not None
		return result

	def __contains__(self, key)->bool:
		"""
		Check if an outline is in this dictionary.

		Uses another public method `get`, must not lock.
		"""
		return self.get(key) is not None

	def _error_on_edit(self)->None:
		raise RuntimeError("Editing the dictionary is not supported. Use the plugin's editing tools instead.")

	def __setitem__(self, key, value)->None:
		self._error_on_edit()

	def __delitem__(self, key)->None:
		self._error_on_edit()

	def update(self, *args, **kwargs)->None:
		self._error_on_edit()

	def clear(self)->None:
		self._error_on_edit()


	def _add(self, entry: Entry)->None:
		"""
		Internal method. Does not lock.
		"""
		if entry.brief:
			assert entry.brief!=(self.search_stroke,)
			assert entry.brief not in self._dict
			self._dict[entry.brief]=entry.translation
			if self._longest_key<len(entry.brief): self._longest_key=len(entry.brief)
		self.entries.append(entry)

	def _remove(self, entry: Entry)->None:
		"""
		Internal method. Does not lock.
		"""
		if entry.brief:
			assert entry.brief!=(self.search_stroke,)
			assert self._dict[entry.brief]==entry.translation
			del self._dict[entry.brief]
			if self._longest_key==entry.brief:
				self._longest_key=max(len(outline) for outline in self.dict)
		old_length=len(self.entries)
		self.entries=[x for x in self.entries if entry!=x]
		assert old_length-1==len(self.entries), (self.entries, old_length, entry)

	@with_print_exception
	@with_lock
	def add(self, entry: Entry)->None:
		"""
		Add an entry to the dictionary.
		"""
		self._add(entry)

	@with_print_exception
	@with_lock
	def remove(self, entry: Entry)->None:
		"""
		Remove an entry from the dictionary.
		"""
		self._remove(entry)

	def _load_nolock(self, filename: str)->None:
		with open(filename, "r", encoding='u8') as f:
			data=json.load(f)
		self.search_stroke=data["search_stroke"]
		self.accept_stroke=data["accept_stroke"]
		if "pick_on_write" in data:
			self.pick_on_write=data["pick_on_write"]

		self.entries=[]
		self._longest_key=1
		for x in data["entries"]:
			entry=Entry.from_tuple(x)
			self._add(entry)  # handle brief
		assert self.longest_key>=1

	@with_lock
	@with_print_exception
	def _load(self, filename: str)->None:
		"""
		This is not a public method, but it's called from super-class implementation of load.
		"""
		self._load_nolock(filename)

	def _save_nolock(self, filename: str)->None:
		with open(filename, "w", encoding='u8') as f:
			#data={
			#		"search_stroke": self.search_stroke,
			#		"accept_stroke": self.accept_stroke,
			#		"entries": [x.tuple() for x in self.entries]
			#		}
			#json.dump(data, f,
			#		indent=0, ensure_ascii=False)
			f.write('{\n'
					'"search_stroke": ' + json.dumps(self.search_stroke) + ',\n'
					'"accept_stroke": ' + json.dumps(self.accept_stroke) + ',\n'
					'"pick_on_write": ' + json.dumps(self.pick_on_write) + ',\n'
					'"entries": [\n' +
					",\n".join(
						json.dumps(entry.tuple(), ensure_ascii=False) for entry in self.entries
						) +
					'\n'
					']\n'
					'}\n'
					)

	@with_lock
	@with_print_exception
	def _save(self, filename: str)->None:
		"""
		This is not a public method, but it's called from super-class implementation of save.
		"""
		self._save_nolock(filename)

	def _search(self, query: str)->List[Entry]:
		"""
		Return the entries that match the query.

		Internal method, does not lock.
		"""
		return sorted(
				[entry for entry in self.entries if query in entry.description],
				key=lambda entry: len(entry.description))[:20]

	@with_lock
	def search(self, query: str)->List[Entry]:
		"""
		Return the entries that match the query.
		"""
		return self._search(query)
