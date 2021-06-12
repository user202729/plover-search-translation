"""
This module is run in the subprocess to display the dialog.

The logic to eliminate redundant communication
(such as adding the current entry to the table when the user click [Add])
is handled in .process module.
"""

from __future__ import annotations

from typing import Tuple, List, Any
import typing
import functools


from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import QTableWidgetItem, QDialog, QShortcut

from .search_translation_dialog_ui import Ui_SearchTranslationDialog
from .lib import text_to_outline, Entry


qt_key_to_value = {
		Qt.Key_1: 1,
		Qt.Key_2: 2,
		Qt.Key_3: 3,
		Qt.Key_4: 4,
		Qt.Key_5: 5,
		Qt.Key_6: 6,
		Qt.Key_7: 7,
		Qt.Key_8: 8,
		Qt.Key_9: 9,
		Qt.Key_0: 10,
		}

class SearchTranslationDialog(QDialog, Ui_SearchTranslationDialog):
	TITLE = 'Search translation'
	ICON = ''
	ROLE = 'search_translation'
	SHORTCUT = "Ctrl+K"

	def __init__(self)->None:
		super().__init__()
		self.setupUi(self)
		self.shortcuts=[]
		for key, key_value in qt_key_to_value.items():
			shortcut=QShortcut(Qt.ALT | key, self)
			shortcut.activated.connect(functools.partial(self.shortcut_pressed, key_value-1))
			self.shortcuts.append(shortcut)

	#def eventFilter(self, event: QEvent)->None:
	#	print(self, event)
	#	if (event.type() != QEvent.KeyPress or
	#			event.modifiers() != Qt.AltModifier or
	#			event.key() not in qt_key_to_value):
	#		event.ignore()
	#		return
	#	event.accept()
	#	index: int=qt_key_to_value[event.key()]-1
	#	assert 0<=index
	#	if index>=self.matches.rowCount():
	#		return
	#	self.matches.setCurrentCell(index, 0)

	def shortcut_pressed(self, row: int)->None:
		assert 0<=row
		if row>=self.matches.rowCount():
			return
		self.matches.setCurrentCell(row, 0)

	# perhaps a separate QAbstractTableModel is better? ...
	def get_row_data(self, row: int)->Entry:
		result: List[Any]=[]
		for i in range(3):
			item=self.matches.item(row, i)
			if item is None:
				item=QTableWidgetItem()
				self.matches.setItem(row, i, item)
			result.append(item.text())
		result[2] = text_to_outline(result[2])
		return Entry.from_tuple(result)

	def row(self)->int:
		"""
		Get the index of the current row, or the first row if none is selected.

		Raise RuntimeError if there's no row.
		"""
		if self.matches.rowCount()==0:
			raise RuntimeError("No row?")
		row=self.matches.currentRow()
		if row==-1:
			return 0
		return row

	def set_row_data(self, row: int, entry: Entry)->None:
		data=entry.tuple()

		item=self.matches.verticalHeaderItem(row)
		if item is None:
			item=QTableWidgetItem()
			self.matches.setVerticalHeaderItem(row, item)
		item.setText(str(row+1))


		for i in range(3):
			item=self.matches.item(row, i)
			if item is None:
				item=QTableWidgetItem()
				self.matches.setItem(row, i, item)
			item.setText("/".join(data[2]) if i==2 else data[i])
