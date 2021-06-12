import functools
import typing
from typing import Tuple, Dict, List, Optional, TypeVar, Callable

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

