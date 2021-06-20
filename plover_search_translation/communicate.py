#!/bin/python
"""
Run in the parent process. Handle the part related to the GUI and signals, but not related to the logic.

The parts related to the logic is handled in .manager.
"""

import sys
import subprocess
from threading import Thread, Lock
from queue import Queue
from typing import List, Optional, Tuple

from subprocess_connection import Message

from plover_search_translation.lib import Entry

class Process:
	"""
	This object should live in the parent process, and it will spawn a subprocess to display the dialog.
	"""

	def __init__(self)->None:
		self._message: Message=Message(
				subprocess.Popen([sys.executable, "-m", "plover_search_translation.process"],
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					)
				)

		self._message.call.show_error=lambda message: self.show_error(message)
		self._message.call.add_translation=lambda entry: self.on_add(entry)
		self._message.call.remove_translation=lambda entry: self.on_remove(entry)
		self._message.call.picked=lambda entry: self.on_pick(entry)

		self._message.func.search=lambda query: self.on_search(query)
		self._message.func.lookup=lambda outline: self.lookup(outline)

		self._message.start()

	def open_dialog(self)->None:
		self._message.call.open_dialog()

	def close_window(self)->None:
		"""
		Close the currently-opening window (only return when the window is closed).
		"""
		self._message.func.close_window()

	def exit(self)->None:
		self._message.stop()

	def __del__(self)->None:
		self.exit()
		
	# These methods should be overridden/modified.
	def show_error(self, message: str)->None:
		pass

	def on_pick(self, entry: Optional[Entry])->None:
		pass

	def on_add(self, entry: Entry)->None:
		pass

	def on_remove(self, entry: Entry)->None:
		pass

	def on_search(self, query: str)->List[Entry]:
		raise NotImplementedError

	def lookup(self, outline: Tuple[str, ...])->Optional[str]:
		raise NotImplementedError






if __name__=="__main__":
	import time
	process=Process()

	process.on_add=lambda entry: print("Added", entry)  # type: ignore
	process.on_pick=lambda entry: print("Picked", entry)  # type: ignore
	process.on_remove=lambda entry: print("Removed", entry)  # type: ignore

	def on_search(query: str)->List[Entry]:
		return [
				Entry("a", "b", ("c", "d")),
				Entry("e", "f", ("g", "h")),
				]
	def lookup(outline: Tuple[str, ...])->Optional[str]:
		return None
	process.on_search=on_search  # type: ignore
	process.lookup=lookup  # type: ignore

	process.open_dialog()

	time.sleep(5)
	print("exiting")
	process.exit()


