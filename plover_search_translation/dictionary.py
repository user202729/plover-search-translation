"""
Dictionary entry point for Plover.
"""

import sys
import json
from typing import Tuple, Dict, List, Optional, TypeVar, Callable, Any, Set, Iterable, Mapping
import typing
from subprocess import Popen
import subprocess
from threading import Lock, Thread
import functools
import re
import math

from plover.steno_dictionary import StenoDictionary  # type: ignore

from . import manager
from .lib import Entry, with_print_exception, Outline


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


WORD_RX=re.compile(r"\w+|\S")


def split_words(s: str)->List[str]:
	return WORD_RX.findall(s)


def ngrams(s: str, n: int)->Iterable[str]:
	"""
	Return all n-grams in the string.
	"""
	for i in range(len(s)-n+1):
		yield s[i:i+n]


def ngrams_padded(s: str, n: int)->Iterable[str]:
	return ngrams(' '+s+' ', n)


def edit_distance_mod(query: str, a: str)->int:
	"""
	Implement an algorithm similar to edit distance to compare string similarity.
	"""
	# missing in query (extra in description): cost 1
	# missing in description (extra in query): cost 3
	f=[*range(len(a)+1)]
	for j, c in enumerate(query):
		# currently f[i] is the distance between query (characters strictly before c) and a[:i]
		g=[0]*len(f)
		g[0]=f[0]+3
		for i in range(1, len(f)):
			g[i]=min(
					f[i]+3,
					g[i-1]+1
					)
			if c==a[i-1]:
				g[i]=min(g[i], f[i-1]-(
					# heuristic: better score for consecutive matches
					i and j and a[i-2]==query[j-1]))
		f=g
		# currently f[i] is the distance between query (characters strictly before c) + c and a[:i]
	return f[-1]  # (might be positive or negative because of the heuristic above)


def match_score(query: str, entry: Entry)->Any: # comparable (for the same value of query), larger is better
	"""
	Return the match score for searching.
	"""
	# quickly filter out unlikely entries first for performance
	if query==entry.translation or query==entry.description:
		return math.inf

	if len(query)<=3:
		if query in entry.description:
			return 10000-len(entry.translation)-len(entry.description)
		elif query in entry.translation:
			return -len(entry.translation)-len(entry.description)
		else:
			return -math.inf

	if not {*ngrams_padded(query, 4)}&{
			*ngrams_padded(entry.translation, 4),
			*ngrams_padded(entry.description, 4),
			}:
		return -math.inf

	return -edit_distance_mod(query, entry.translation+' '+entry.description)
	# smaller edit distance is better


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
		self.dict: Dict[Outline, Entry]={}
		"""
		Dictionary that maps from the brief to the entry object.
		"""

		self._longest_key=1

	@with_lock
	def __del__(self)->None:
		if manager.instance and manager.instance.is_showing(self):
			print("weird?")

	def _getitem(self, key: Outline)->str:
		"""
		Lookup an item by its brief (outline).

		Also return the command to close the dialog if it's opening.
		"""
		if key==(self.search_stroke,):
			manager.get().ensure_active_dictionary(self)
			return (
					"{:command:plover_search_translation_open_dialog:" +
					self.path.translate({
						ord("{"): r"\{",
						ord("}"): r"\}",
						}) +
					"}{^}")

		result=self.dict[key].translation  # might raise KeyError
		if self.pick_on_write and manager.instance and manager.instance.is_showing(self):
			result="{:command:plover_search_translation_close_dialog}"+result
			# (must close the dialog before sending the commands)
		return result

	@with_lock
	def __getitem__(self, key: Outline)->str:
		"""
		Like `_getitem`, but locked.
		"""
		return self._getitem(key)

	def get(self, key: Outline, default: Optional[str]=None)->Optional[str]:
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

	def _delitem(self, key: Outline)->None:
		"""
		Internal method. Does not lock.

		Compatible method for Plover dictionaries. ``add`` and ``remove`` has more functionalities.
		"""
		entry=self.dict[key]  # might raise KeyError
		self._remove(entry)

	def _setitem(self, key: Outline, value: str)->None:
		"""
		Internal method. Does not lock.

		Compatible method for Plover dictionaries. ``add`` and ``remove`` has more functionalities.

		This method tries to preserve the description of the entry.
		(however the description is still removed if the entry is edited through Plover dictionary editor)
		Same issue as plover_excel_dictionary.
		"""
		assert key
		if key in self.dict:
			entry=self.dict[key]
			self._remove(entry)
			description=entry.description
		else:
			description=""
		self._add(Entry(description=description, translation=value, brief=key))

	def __iter__(self)->Iterable[Tuple[Outline, str]]:
		"""
		Compatible method for Plover dictionaries.
		"""
		for key, entry in self.dict.items():
			yield key, entry.translation

	def items(self)->Iterable[Tuple[Outline, str]]:
		"""
		Compatible method for Plover dictionaries.
		"""
		return iter(self)

	def __len__(self)->int:
		return len(self.dict)

	@with_lock
	def __setitem__(self, key: Outline, value: str)->None:
		self._setitem(key, value)

	@with_lock
	def __delitem__(self, key: Outline)->None:
		self._delitem(key)

	@with_lock
	def update(self, *args, **kwargs)->None:
		for d in args:
			for key, value in (d.items() if hasattr(d, "items") else d):
				self._setitem(key, value)
		for key, value in kwargs.items():
			self._setitem(key, value)

	@with_lock
	def clear(self)->None:
		"""
		Clear the dictionary. ``search_stroke`` remains.
		"""
		self.entries=[]

	def _add(self, entry: Entry)->None:
		"""
		Internal method. Does not lock.
		"""
		if entry.brief:
			assert entry.brief!=(self.search_stroke,)
			assert entry.brief not in self.dict
			self.dict[entry.brief]=entry
			if self._longest_key<len(entry.brief): self._longest_key=len(entry.brief)
		self.entries.append(entry)

	def _remove(self, entry: Entry)->None:
		"""
		Internal method. Does not lock.
		"""
		if entry.brief:
			assert entry.brief!=(self.search_stroke,)
			assert self.dict[entry.brief]==entry
			del self.dict[entry.brief]
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

		(entry does only need to be equal in value to some existing entry, otherwise
		AssertionError is raised)
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
		if query=="":
			return self.entries[:100]
		return sorted(
				self.entries,
				key=lambda entry: match_score(query, entry),
				reverse=True)[:100]

	@with_lock
	def search(self, query: str)->List[Entry]:
		"""
		Return the entries that match the query.
		"""
		return self._search(query)
