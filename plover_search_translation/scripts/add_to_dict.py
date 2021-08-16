#!/bin/python
def main()->None:
	import argparse
	from pathlib import Path

	parser=argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument("target_dictionary", type=Path, help="Path to target (JST) dictionary to add to.")
	parser.add_argument("source_json_dictionary", type=Path, help="Path to source (JSON) dictionary.")
	parser.add_argument("-d", "--description", type=str, default="Imported from {source_stem}",
			help="What to fill in the description field. "
			"Interpreted as a Python f-string with "
			"{outline}, {translation} / {output}, {source_stem}, {source_absolute} "
			"optional keyword variable.")
	parser.add_argument("--create-backup-file", action="store_true", default=True)
	parser.add_argument("--no-create-backup-file", action="store_false", dest="create_backup_file")
	parser.add_argument("--restore-from-backup-file", action="store_true")
	args=parser.parse_args()

	import json
	from ..dictionary import Dictionary
	from ..lib import Entry
	from typing import Dict
	import typing
	import tempfile

	backup_path= Path(tempfile.gettempdir()) / (args.target_dictionary.stem + "__backup")
	if args.restore_from_backup_file:
		try:
			content: str=backup_path.read_text()
		except:
			raise RuntimeError(f"Cannot read from backup file at {backup_path}")
		args.target_dictionary.write_text(content)
		return

	if args.create_backup_file:
		backup_path.write_text(args.target_dictionary.read_text())

	source_data: Dict[str, str]=json.loads(args.source_json_dictionary.read_text())
	for translation in source_data.values():
		if not isinstance(translation, str):
			raise RuntimeError(f"Invalid source_json_dictionary {args.source_json_dictionary}")

	dictionary=Dictionary.load(str(args.target_dictionary))
	fixed_parameters=dict(
			source_stem=args.source_json_dictionary.stem,
			source_absolute=args.source_json_dictionary.absolute(),
			)

	invalid_entry=dictionary._add_multiple(
			Entry(
				translation=translation,
				description=args.description.format(
					outline=outline,
					translation=translation, output=translation,
					**fixed_parameters
					),
				brief=tuple(outline.split("/"))
				)
			for outline, translation in source_data.items())
	if invalid_entry is not None:
		raise RuntimeError(f"Invalid entry: {invalid_entry}")
	dictionary.save()


if __name__=="__main__":
	main()
