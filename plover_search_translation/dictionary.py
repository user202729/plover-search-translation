"""
Dictionary entry point for Plover.
"""

import sys
import json
from typing import Tuple, Dict, List, Optional, TypeVar, Callable
import typing
from subprocess import Popen
import subprocess
from threading import Lock, Thread
import functools

from plover.steno_dictionary import StenoDictionary  # type: ignore
from subprocess_connection import Connection

from . import manager
from .lib import Entry, with_print_exception


process: Optional[Connection]=None

current_dictionary: Optional["Dictionary"]=None

T=TypeVar("T", bound=Callable)

def with_lock(function: T)->T:
	@functools.wraps(function)
	def result(self, *args, **kwargs):
		self.lock.acquire(timeout=1)  # might raise an error in case of programming error (recursive lock?)
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
		self.entries: List[Entry]=[]
		self.lock: Lock=Lock()

		self._longest_key=4

	def __del__(self)->None:
		if manager.instance and manager.instance.is_showing(self):
			print("weird?")

	@with_lock
	def __getitem__(self, key: Tuple[str, ...])->str:
		"""
		Lookup an item by its brief (outline).
		"""
		global process
		if len(key)==1:
			if key[0]==self.search_stroke:
				manager.get().ensure_active_dictionary(self)
				return (
						"{:command:plover_search_translation_show_dialog:" +
						self.path.translate({
							ord("{"): r"\{",
							ord("}"): r"\}",
							}) +
						"}{^}")

			#if key[0]==self.accept_stroke:
			#	if not self._show:
			#		raise KeyError

			#	assert process
			#	process.send(c.PICK_MESSAGE)
			#	data=process.recv()
			#	assert isinstance(data, str)

			#	if not data:
			#		raise RuntimeError("No translation is available")

			#	self._wait()
			#	return data

		if key in self.briefs:
			if manager.instance and manager.instance.is_showing(self):
				manager.instance.close_window()

			result,=[x for x in self.entries if x.brief==key]
			return result.translation

		raise KeyError

	def __setitem__(self, key, value)->None:
		raise RuntimeError("Editing the dictionary is not supported. Use the plugin's editing tools instead.")

	def __delitem__(self, key)->None:
		raise RuntimeError("Editing the dictionary is not supported. Use the plugin's editing tools instead.")

	def get(self, key: Tuple[str, ...], default: Optional[str]=None)->Optional[str]:
		"""
		Lookup an item by its brief (outline).
		"""
		try: result=self[key]
		except KeyError: return default
		if result is None: return default
		return result

	@property
	def briefs(self)->List[Tuple[str, ...]]:
		return [x.brief for x in self.entries]

	@with_lock
	def _add_no_save(self, entry: Entry)->None:
		"""
		Internal method. Add an entry without saving.
		"""
		assert entry not in self.briefs
		self.entries.append(entry)

	@with_lock
	def _remove_no_save(self, entry: Entry)->None:
		"""
		Internal method, remove an entry without saving.
		"""
		old_length=len(self.entries)
		self.entries=[x for x in self.entries if entry!=x]
		assert old_length-1==len(self.entries), (self.entries, old_length, entry)

	def _check_long_key(self)->None:
		assert all(len(x)<=self.longest_key for x in self.briefs), "Too long briefs are not supported"

	@with_print_exception
	def add(self, entry: Entry)->None:
		"""
		Add an entry to the dictionary, and save to disk.
		"""
		self._add_no_save(entry)
		self._check_long_key()
		self.save()

	@with_print_exception
	def remove(self, entry: Entry)->None:
		"""
		Remove an entry from the dictionary, and save to disk.
		"""
		self._remove_no_save(entry)
		self.save()

	@with_lock
	@with_print_exception
	def _load(self, filename: str)->None:
		with open(filename, "r", encoding='u8') as f:
			data=json.load(f)
		self.search_stroke=data["search_stroke"]
		self.accept_stroke=data["accept_stroke"]
		self.entries=[Entry.from_tuple(x) for x in data["entries"]]
		self._check_long_key()

	@with_lock
	def _save(self, filename: str)->None:
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
					'"entries": [\n' +
					",\n".join(
						json.dumps(entry.tuple(), ensure_ascii=False) for entry in self.entries
						) +
					'\n'
					']\n'
					'}\n'
					)

	def search(self, query: str)->List[Entry]:
		"""
		Return the entries that match the query.
		"""
		return sorted(
				[entry for entry in self.entries if query in entry.description],
				key=lambda entry: len(entry.description))[:20]
