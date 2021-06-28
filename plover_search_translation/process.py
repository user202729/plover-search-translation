#!/bin/python
"""
This module should run the GUI subprocess.
"""


from dataclasses import dataclass

import functools
from typing import List, Callable, Optional, TypeVar
import typing
import faulthandler
faulthandler.enable()

import time

from PyQt5.QtCore import Qt  # type: ignore
from PyQt5.QtWidgets import QApplication  # type: ignore

import html

from subprocess_connection import Message

from .lib import Entry, throttle
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

message=Message()


@dataclass(frozen=True)
class State: pass

@dataclass(frozen=True)
class SingletonState(State):
	name: str

WINDOW_CLOSED=SingletonState("WINDOW_CLOSED")
WINDOW_OPEN=SingletonState("WINDOW_OPEN")
PROGRAMMATICALLY_EDITING_DESCRIPTION=SingletonState("PROGRAMMATICALLY_EDITING_DESCRIPTION")

assert WINDOW_CLOSED is not WINDOW_OPEN  # (of course)

@dataclass(frozen=True)
class Editing(State):
	entry: Entry
	row: int


state: State=WINDOW_CLOSED

def set_state(new_state: State)->None:
	global state
	state=new_state




def show_error(error: str)->None:
	message.call.show_error(error)

def set_description_text(new_text: str)->None:
	"""
	Set the text of the description text field without triggering repopulate_matches.

	The logic is handled in description_search_changed.
	"""
	assert state is WINDOW_OPEN, state
	old_state=state
	set_state(PROGRAMMATICALLY_EDITING_DESCRIPTION)
	dialog.description.setText(new_text)
	set_state(old_state)


from pathlib import Path
import json
column_width_save_path=Path("/tmp/Plover-search-translation-column-width-values.json")

def saved_column_width_values()->Optional[List[int]]:
	return message.func.get_column_width()

def save_column_width()->None:
	horizontal_header=dialog.matches.horizontalHeader()
	n=horizontal_header.count()
	message.call.save_column_width(
			[horizontal_header.sectionSize(index) for index in range(n-1)]
			)

def load_column_width()->None:
	horizontal_header=dialog.matches.horizontalHeader()
	n=horizontal_header.count()
	values=saved_column_width_values()
	if values is None: return
	for index in range(n-1):
		dialog.matches.horizontalHeader().resizeSection(
				index,
				values[index]
				)

@message.register_call
@execute_on_main_thread
def open_dialog()->None:
	assert not dialog.isVisible()
	assert state is WINDOW_CLOSED, state
	set_state(WINDOW_OPEN)
	dialog.output.setText("")
	dialog.description.setFocus()
	set_description_text("")
	dialog.brief.setText("")
	dialog.briefConflictLabel.setText("")
	dialog.matches.setRowCount(0)
	repopulate_matches("")
	dialog.show()
	load_column_width()

@message.register_func_with_callback
@execute_on_main_thread
def close_dialog(callback, args, kwargs)->None:
	dialog.hide()
	assert state is WINDOW_OPEN or isinstance(state, Editing)
	save_column_width()
	set_state(WINDOW_CLOSED)
	callback(None)
	time.sleep(0.05)  # some window manager might have problems without this

def rejected()->None:
	assert state is WINDOW_OPEN or isinstance(state, Editing)
	save_column_width()
	set_state(WINDOW_CLOSED)
	message.call.picked(None)

dialog.rejected.connect(rejected)

from .lib import text_to_outline

def add_translation()->None:
	assert state is WINDOW_OPEN or isinstance(state, Editing)

	if not (dialog.output.text() and dialog.description.text()):
		show_error("Output and description must be filled")
		return

	new_entry=Entry(
		dialog.output.text(),
		dialog.description.text(),
		text_to_outline(dialog.brief.text()),
		)

	if state is WINDOW_OPEN:
		dialog.matches.insertRow(0)
		dialog.refresh_all_vertical_header()
		dialog.set_row_data(0, new_entry)
		message.call.add_translation(new_entry)
	else:
		assert isinstance(state, Editing), state
		old_entry=state.entry
		dialog.set_row_data(state.row, new_entry)
		set_state(WINDOW_OPEN)
		if old_entry!=new_entry:
			message.call.remove_translation(old_entry)
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

	if isinstance(state, Editing):
		show_error("Pick while editing not supported")
		return

	assert state is WINDOW_OPEN, state
	save_column_width()
	set_state(WINDOW_CLOSED)

	dialog.hide()
	message.call.picked(entry)

dialog.pickButton.clicked.connect(pick)

editing_entry_placeholder=Entry(
		"[...]",
		"[...]",
		("[...]",),
		)

def edit_translation()->None:
	if isinstance(state, Editing):
		return # clicking [edit] twice is equivalent to once
	assert state is WINDOW_OPEN, state

	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.set_row_data(row, editing_entry_placeholder)

	dialog.output.setText(entry.translation)
	set_description_text(entry.description)
	dialog.brief.setText("/".join(entry.brief))

	set_state(Editing(entry, row))


dialog.editButton.clicked.connect(edit_translation)

def delete_translation()->None:
	if isinstance(state, Editing):
		message.call.remove_translation(state.entry)
		dialog.matches.removeRow(state.row)
		set_state(WINDOW_OPEN)
		return

	assert state is WINDOW_OPEN, state

	row=get_row()
	if row is None: return

	entry=dialog.get_row_data(row)
	dialog.matches.removeRow(row)
	message.call.remove_translation(entry)

dialog.deleteButton.clicked.connect(delete_translation)

def repopulate_matches(query: str)->None:
	"""
	Fill the matches table with the matches from the dictionary.
	Must be called from the main thread.
	"""
	if state is WINDOW_CLOSED:
		return
	result: List[Entry] = message.func.search(query)
	dialog.matches.setRowCount(len(result))
	dialog.refresh_all_vertical_header()
	for row, entry in enumerate(result):
		dialog.set_row_data(row, entry)

@throttle(0.05)
@execute_on_main_thread
def repopulate_matches_delayed(query: str)->None:
	repopulate_matches(query)

def description_search_changed(text: str)->None:
	if state is PROGRAMMATICALLY_EDITING_DESCRIPTION or isinstance(state, Editing):
		return
	if state is WINDOW_CLOSED:
		# this might happen if the description text is modified right before the dialog is closed
		return
	assert state is WINDOW_OPEN, state
	repopulate_matches_delayed(text)

def brief_changed(text: str)->None:
	outline=text_to_outline(text)
	if not outline:
		text=""
	else:
		outline_str=html.escape("/".join(outline))
		result=message.func.lookup(outline)
		if result is None:
			text=f'<b><code>{outline_str}</code></b> is not mapped in any dictionary'
		else:
			result=html.escape(result)
			text=f'<b><code>{outline_str}</code></b> maps to <b><code>{result}</code></b>'
	dialog.briefConflictLabel.setText(text)

dialog.description.textChanged.connect(description_search_changed)
dialog.brief.textChanged.connect(brief_changed)

message.start(on_stop=lambda: app.exit(0))

returncode=app.exec_()
assert returncode==0
