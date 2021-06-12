#!/bin/python
"""
This module should run the GUI subprocess.
"""


import threading
import functools
from typing import List, Dict, Callable, Tuple, Optional, TypeVar
import typing
import faulthandler
faulthandler.enable()

from PyQt5.QtCore import Qt  # type: ignore
from PyQt5.QtWidgets import QApplication  # type: ignore

from plover_search_translation.gui import SearchTranslationDialog

from subprocess_connection import Connection
from plover_search_translation import connection_constants as c
from plover_search_translation.engine import Entry

from PyQt5.QtCore import pyqtSignal, QVariant, QObject
class SignalObject(QObject):
	signal = pyqtSignal(QVariant)
signal_object=SignalObject()  # must keep a reference to the object
signal_data=signal_object.signal


def execute_function(x):
	x()
signal_data.connect(execute_function)

F=TypeVar("F", bound=Callable)
def execute_on_main_thread(f: F)->F:  # note: returns immediately, does not wait for the call to complete
	@functools.wraps(f)
	def result(*args, **kwargs):
		signal_data.emit(functools.partial(f, *args, **kwargs))
	return typing.cast(F, result)

app=QApplication([])
app.setQuitOnLastWindowClosed(False)
dialog=SearchTranslationDialog()

from queue import Queue

search_result_queue: Queue[List[Entry]]=Queue()

connection=Connection()

@execute_on_main_thread
def exit_():
	dialog.hide()
	app.exit(0)


def show_error(message: str)->None:
	connection.send((c.SHOW_ERROR_MESSAGE, message))

disable_description_change_hook: bool=False
def set_description_text(new_text: str)->None:
	global disable_description_change_hook
	disable_description_change_hook=True
	dialog.description.setText(new_text)
	disable_description_change_hook=False


@execute_on_main_thread
def show_dialog(normal_window: bool=True)->None:
	assert not dialog.isVisible()
	if not normal_window:
		dialog.setWindowFlag(Qt.FramelessWindowHint)
		dialog.setWindowFlag(Qt.BypassWindowManagerHint)
	dialog.output.setText("")
	dialog.description.setFocus()
	set_description_text("")
	dialog.brief.setText("")
	dialog.matches.setRowCount(0)
	dialog.show()
	if not normal_window:
		dialog.activateWindow()

@execute_on_main_thread
def close_window()->None:
	dialog.hide()
	connection.send((c.CLOSE_WINDOW_MESSAGE, None))

def listener_thread_run()->None:
	while True:
		message_type, message_content=connection.recv()

		if message_type==c.OPEN_DIALOG_MESSAGE:
			show_dialog()

		elif message_type==c.SEARCH_MESSAGE:
			assert search_result_queue.empty()
			assert isinstance(message_content, list)
			search_result_queue.put(message_content)

		elif message_type==c.EXIT_MESSAGE:
			exit_()
			connection.send((c.EXIT_MESSAGE, None))
			break

		elif message_type==c.CLOSE_WINDOW_MESSAGE:
			close_window()

		else:
			show_error(f"Message type {message_type} is not recognized")


listener_thread=threading.Thread(target=listener_thread_run)
listener_thread.start()

def rejected()->None:
	connection.send((
		c.PICK_BUTTON_MESSAGE,
		None
		))

dialog.rejected.connect(rejected)

from .lib import text_to_outline

def add_translation()->None:
	if not (dialog.output.text() and dialog.description.text()):
		show_error("Output and description must be filled")
		return
	dialog.matches.insertRow(0)
	new_entry=Entry(
		dialog.output.text(),
		dialog.description.text(),
		text_to_outline(dialog.brief.text()),
		)
	dialog.set_row_data(0, new_entry)
	connection.send((
		c.ADD_TRANSLATION_MESSAGE,
		new_entry
		))

	dialog.output.setText("")
	dialog.description.setFocus()
	dialog.brief.setText("")

dialog.addButton.clicked.connect(add_translation)

def get_row()->Optional[int]:
	try:
		return dialog.row()
	except RuntimeError:
		show_error("Empty table")
		return None

def pick()->None:
	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.hide()
	connection.send((
		c.PICK_BUTTON_MESSAGE,
		entry
		))

dialog.pickButton.clicked.connect(pick)

def edit_translation()->None:
	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.matches.removeRow(row)

	dialog.output.setText(entry.translation)
	set_description_text(entry.description)
	dialog.brief.setText("/".join(entry.brief))

	connection.send((
		c.REMOVE_TRANSLATION_MESSAGE,
		entry
		))

dialog.editButton.clicked.connect(edit_translation)

def delete_translation()->None:
	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.matches.removeRow(row)
	connection.send((
		c.REMOVE_TRANSLATION_MESSAGE,
		entry
		))

dialog.deleteButton.clicked.connect(delete_translation)

def description_search_changed(text: str)->None:
	if disable_description_change_hook:
		return

	connection.send((
		c.SEARCH_MESSAGE,
		text
		))
	# the listener thread will handle the result
	result: List[Entry]=search_result_queue.get(timeout=1)
	dialog.matches.setRowCount(len(result))
	for row, entry in enumerate(result):
		dialog.set_row_data(row, entry)

dialog.description.textChanged.connect(description_search_changed)


returncode=app.exec_()
assert returncode==0
