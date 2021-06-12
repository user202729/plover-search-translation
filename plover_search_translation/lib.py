import functools
import typing
from typing import Tuple, Dict, List, Optional, TypeVar, Callable, Sequence, Any
from dataclasses import dataclass
from pathlib import Path
import tempfile
import json

T=TypeVar("T", bound=Callable)

def with_print_exception(function: T)->T:
	"""
	Mostly a debugging tool. Catch the exceptions raised by the method and show it.
	"""
	@functools.wraps(function)
	def result(self, *args, **kwargs):
		try:
			return function(self, *args, **kwargs)
		except:
			import traceback
			traceback.print_exc()
			from plover import log  # type: ignore
			log.error(traceback.format_exc())
			raise
	return typing.cast(T, result)  # TODO?

def text_to_outline(s: str)->Tuple[str, ...]:
	return tuple(s.replace('/', ' ').split())


@dataclass
class Entry:  # field order is important
	translation: str
	description: str
	brief: Tuple[str, ...]

	def valid(self)->bool:
		return bool(self.description and self.translation)

	def __str__(self)->str:
		return f"({self.brief} -> {self.translation} | {self.description})"

	def tuple(self)->Tuple[str, str, Tuple[str, ...]]:
		return (self.translation, self.description, self.brief)

	@staticmethod
	def from_tuple(data: Any)->"Entry":
		assert type(data[2]) in (list, tuple)
		return Entry(
				translation=data[0],
				description=data[1],
				brief=tuple(data[2])
				)
