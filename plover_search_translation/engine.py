from typing import Tuple, List, Sequence, Any
from dataclasses import dataclass
from pathlib import Path
import tempfile
import json

data_file_path=Path(tempfile.gettempdir())/"search-translation-store.json"

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
