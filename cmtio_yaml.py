#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
YAML I/O helpers
"""

import sys
from typing import Any, Dict, Iterator, List, Optional, Union
try:
	import yaml
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: Could not import yaml; you may need to (re-)run `cmt-install` or `pip3 install PyYAML`; aborting.")

import cmtio
from cmttypes import FilePath, SecurityChecks

# pylint: disable-next=too-many-arguments
def secure_write_yaml(path: FilePath, data: Union[Dict, List[Dict]], permissions: Optional[int] = None,
		      replace_empty: bool = False, replace_null: bool = False, sort_keys: bool = True, write_mode: str = "w") -> None:
	"""
	Dump a dict to a file in YAML-format in a safe manner

		Parameters:
			path (FilePath): The path to write to
			data (dict): The dict to dump
			permissions (int): File permissions (None uses system defaults)
			replace_empty (bool): True strips empty strings
			replace_null (bool): True strips null
			write_mode (str): [w, a, x] Write, Append, Exclusive Write
		Raises:
			cmttypes.FilePathAuditError
	"""

	if write_mode not in ("a", "w", "x"):
		raise ValueError(f"Invalid write mode “{write_mode}“; permitted modes are “a“ (append), “w“ (write) and “x“ (exclusive write)")

	yaml_str = yaml.safe_dump(data, default_flow_style = False, sort_keys = sort_keys)
	if replace_empty == True:
		yaml_str = yaml_str.replace(r"''", "")
	if replace_null == True:
		yaml_str = yaml_str.replace(r"null", "")
	cmtio.secure_write_string(path, yaml_str, permissions = permissions, write_mode = write_mode)

def secure_read_yaml(path: FilePath, checks: Optional[List[SecurityChecks]] = None, directory_is_symlink: bool = False) -> Any:
	"""
	Read data in YAML-format from a file in a safe manner

		Parameters:
			path (FilePath): The path to read from
			directory_is_symlink (bool): The directory that the path points to is a symlink
		Returns:
			yaml_data (any): The read YAML-data
		Raises:
			yaml.composer.ComposerError
			yaml.parser.ParserError
			FileNotFoundError
			cmttypes.FilePathAuditError
	"""

	string = cmtio.secure_read_string(path, checks = checks, directory_is_symlink = directory_is_symlink)
	return yaml.safe_load(string)

def secure_read_yaml_all(path: FilePath, checks: Optional[List[SecurityChecks]] = None, directory_is_symlink: bool = False) -> Iterator[Any]:
	"""
	Read all dicts in YAML-format from a file in a safe manner
	Note: since the return type from safe_load_all() is an iterator evaluation does not happen until
	      iterating; this means that exceptions must be handled when iterating rather than when getting
	      the return value

		Parameters:
			path (FilePath): The path to read from
			directory_is_symlink (bool): The directory that the path points to is a symlink
		Returns:
			iterator[any]: An iterator of data
		Raises:
			FileNotFoundError
			cmttypes.FilePathAuditError
	"""

	string = cmtio.secure_read_string(path, checks = checks, directory_is_symlink = directory_is_symlink)
	return yaml.safe_load_all(string)
