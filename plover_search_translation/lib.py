import functools
import time
import threading
import typing
from typing import Tuple, Dict, List, Optional, TypeVar, Callable, Sequence, Any
from dataclasses import dataclass
from pathlib import Path
import tempfile
import json

if typing.TYPE_CHECKING:
	import plover.engine  # type: ignore

Outline=Tuple[str, ...]

T=TypeVar("T", bound=Callable)

def with_print_exception(function: T)->T:
	"""
	Mostly a debugging tool. Catch the exceptions raised by the method and show+suppress it.
	"""
	@functools.wraps(function)
	def result(self, *args, **kwargs):
		try:
			return function(self, *args, **kwargs)
		except:
			import traceback
			from plover import log  # type: ignore
			log.error(traceback.format_exc())
	return typing.cast(T, result)  # TODO?

def text_to_outline(s: str)->Outline:
	return tuple(s.replace('/', ' ').split())


@dataclass(frozen=True)
class Entry:  # field order is important
	translation: str
	description: str
	brief: Outline

	def valid(self)->bool:
		return bool(self.description and self.translation)

	def __str__(self)->str:
		return f"({self.brief} -> {self.translation} | {self.description})"

	def tuple(self)->Tuple[str, str, Outline]:
		return (self.translation, self.description, self.brief)

	@staticmethod
	def from_tuple(data: Any)->"Entry":
		assert type(data[2]) in (list, tuple)
		return Entry(
				translation=data[0],
				description=data[1],
				brief=tuple(data[2])
				)


def throttle(seconds: float)->Callable[[T], T]:
	"""
	Wait for <seconds> seconds, collect all the function calls, then only call the last function.

	The delay is only approximate, may be longer if the actual function call takes a long time.

	Example:

	Time                    ---------------------------------------------> (s)
	Wrapped function call:    * *          *  * * ***     * *              ('*' = 1 call)
	Actual function call:     .......#     .......#.......#.......#        ('#' = 1 call)
	                          \______/
	                             |_______ ==  delay time
	"""

	def result(function: T)->T:
		thread=None
		function_args, function_kwargs=None, None
		lock=threading.Lock()  # should be locked when the function is called or when any of the variables above is modified

		def target(*args, **kwargs):
			nonlocal thread
			time.sleep(seconds)
			with lock:
				thread=None
				function(*function_args, **function_kwargs)

		@functools.wraps(function)
		def wrapped(*args, **kwargs)->Any:
			nonlocal thread, function_args, function_kwargs
			with lock:
				function_args, function_kwargs=args, kwargs
				if thread is None:
					thread=threading.Timer(seconds, target)
					thread.start()

		return typing.cast(T, wrapped)
	return result


def inject_translation(engine: "plover.engine.StenoEngine", mapping: str)->None:
	"""
	Inject a translation into the engine.

	``mapping`` is a string and can be either a translation or a macro.

	Might raise an error if `mapping` is invalid or similar.

	Does not trigger the `stroked` hook.
	"""
	with engine:
		from plover.steno import Stroke  # type: ignore
		from plover.translation import _mapping_to_macro, Translation  # type: ignore
		stroke = Stroke([]) # required, because otherwise Plover will try to merge the outlines together
		# and the outline [] (instead of [Stroke([])]) can be merged to anything
		macro = _mapping_to_macro(mapping, stroke)
		if macro is not None:
			engine._translator.translate_macro(macro)
			return
		t = (
			#engine._translator._find_translation_helper(stroke) or
			#engine._translator._find_translation_helper(stroke, system.SUFFIX_KEYS) or
			Translation([stroke], mapping)
		)
		engine._translator.translate_translation(t)
		engine._translator.flush()
		#engine._trigger_hook('stroked', stroke)
