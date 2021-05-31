#!/bin/python
"""
Run in the parent process. Handle the part related to the GUI and signals, but not related to the logic.
"""

import sys
import subprocess
from threading import Thread, Lock
from queue import Queue
from typing import List, Optional

from subprocess_connection import Connection
from plover_search_translation import connection_constants as c
from plover_search_translation.engine import Entry

class Process:
	"""
	This object should live in the parent process, and it will spawn a subprocess to display the dialog.
	"""

	def __init__(self)->None:
		self._listen_thread: Thread=Thread(target=self._listen_thread_run)
		"""
		The _listen_thread. Callback functions will be called in this thread.
		"""
		self._connection_send_lock: Lock=Lock()
		self._close_window_queue: Queue=Queue()
		self._connection: Connection=Connection(
				subprocess.Popen([sys.executable, "-m", "plover_search_translation.process"],
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					)
				)
		self._listen_thread.start()

	def open_dialog(self)->None:
		self._connection.send((
				c.OPEN_DIALOG_MESSAGE,
				None
				))

	def _listen_thread_run(self)->None:
		while True:
			try:
				message_type, message_content=self._connection.recv()
			except EOFError:
				print("Subprocess exited?")
				break

			if message_type==c.ADD_TRANSLATION_MESSAGE:
				assert isinstance(message_content, Entry)
				self.on_add(message_content)

			elif message_type==c.REMOVE_TRANSLATION_MESSAGE:
				assert isinstance(message_content, Entry)
				self.on_remove(message_content)

			elif message_type==c.PICK_BUTTON_MESSAGE:
				assert message_content is None or isinstance(message_content, Entry)
				self.on_pick(message_content)

			elif message_type==c.SEARCH_MESSAGE:
				assert isinstance(message_content, str)
				search_result=self.on_search(message_content)
				with self._connection_send_lock:
					self._connection.send((c.SEARCH_MESSAGE, search_result))

			elif message_type==c.SHOW_ERROR_MESSAGE:
				assert isinstance(message_content, str)
				self.show_error(message_content)
				
			elif message_type==c.EXIT_MESSAGE:
				break

			elif message_type==c.CLOSE_WINDOW_MESSAGE:
				# subprocess done closing the window
				self._close_window_queue.put(None)

			else:
				raise RuntimeError(f"Message type {message_type} is not recognized")

	def close_window(self)->None:
		"""
		Close the currently-opening window (only return when the window is closed).
		"""
		assert self._close_window_queue.empty()
		with self._connection_send_lock:
			self._connection.send((c.CLOSE_WINDOW_MESSAGE, None))
		self._close_window_queue.get(timeout=1)

	def exit(self)->None:
		with self._connection_send_lock:
			if self._connection._send_pipe.closed:
				return
			self._connection.send((c.EXIT_MESSAGE, None))
			self._connection.process.wait(timeout=1)
			self._connection.close()
			self._listen_thread.join(timeout=1)

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






if __name__=="__main__":
	import time
	process=Process()

	process.on_add=lambda entry: print("Added", entry)
	process.on_pick=lambda entry: print("Picked", entry)
	process.on_remove=lambda entry: print("Removed", entry)

	def on_search(query: str)->List[Entry]:
		return [
				Entry("a", "b", ("c", "d")),
				Entry("e", "f", ("g", "h")),
				]
	process.on_search=on_search

	process.open_dialog()

	time.sleep(5)
	print("exiting")
	process.exit()


