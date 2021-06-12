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

from subprocess_connection import Message

from .lib import Entry
from .gui import SearchTranslationDialog

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

search_result_queue: Queue[List[Entry]]=Queue(maxsize=1)

message=Message()

@execute_on_main_thread
def exit_():
	dialog.hide()
	app.exit(0)


def show_error(error: str)->None:
	message.call.show_error(error)

disable_description_change_hook: bool=False
def set_description_text(new_text: str)->None:
	global disable_description_change_hook
	disable_description_change_hook=True
	dialog.description.setText(new_text)
	disable_description_change_hook=False


@message.register_call
@execute_on_main_thread
def open_dialog(normal_window: bool=True)->None:
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

@message.register_call
@execute_on_main_thread
def close_window()->None:
	dialog.hide()
	message.call.window_closed()


def rejected()->None:
	message.call.picked(None)

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
	message.call.add_translation(new_entry)

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
	message.call.picked(entry)

dialog.pickButton.clicked.connect(pick)

def edit_translation()->None:
	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.matches.removeRow(row)

	dialog.output.setText(entry.translation)
	set_description_text(entry.description)
	dialog.brief.setText("/".join(entry.brief))

	message.call.remove_translation(entry)

dialog.editButton.clicked.connect(edit_translation)

def delete_translation()->None:
	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.matches.removeRow(row)
	message.call.remove_translation(entry)

dialog.deleteButton.clicked.connect(delete_translation)

def description_search_changed(text: str)->None:
	if disable_description_change_hook:
		return

	result: List[Entry] = message.func.search(text)
	dialog.matches.setRowCount(len(result))
	for row, entry in enumerate(result):
		dialog.set_row_data(row, entry)

dialog.description.textChanged.connect(description_search_changed)

message.start()

returncode=app.exec_()
assert returncode==0
