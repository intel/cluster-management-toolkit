#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
YAML I/O helpers for Intel Kubernetes Toolkit
"""

from typing import Dict, Iterator, Optional
import yaml

import iktio
from ikttypes import FilePath

# pylint: disable-next=too-many-arguments
def secure_write_yaml(path: FilePath, data, permissions: Optional[int] = None, replace_empty = False, replace_null = False, sort_keys = True) -> None:
	"""
	Dump a dict to a file in YAML-format in a safe manner

		Parameters:
			path (FilePath): The path to write to
			data (dict): The dict to dump
			permissions (int): File permissions (None uses system defaults)
			replace_empty (bool): True strips empty strings
			replace_null (bool): True strips null
		Raises:
			ikttypes.FilePathAuditError
	"""

	yaml_str = yaml.safe_dump(data, default_flow_style = False, sort_keys = sort_keys)
	if replace_empty == True:
		yaml_str = yaml_str.replace(r"''", "")
	if replace_null == True:
		yaml_str = yaml_str.replace(r"null", "")
	iktio.secure_write_string(path, yaml_str, permissions = permissions)

def secure_read_yaml(path: FilePath, checks = None, directory_is_symlink: bool = False) -> Dict:
	"""
	Read data in YAML-format from a file in a safe manner

		Parameters:
			path (FilePath): The path to read from
			directory_is_symlink (bool): The directory that the path points to is a symlink
		Returns:
			yaml_data (yaml): The read YAML-data
		Raises:
			yaml.composer.ComposerError
			yaml.parser.ParserError
			FileNotFoundError
			ikttypes.FilePathAuditError
	"""

	string = iktio.secure_read_string(path, checks = checks, directory_is_symlink = directory_is_symlink)
	return yaml.safe_load(string)

def secure_read_yaml_all(path: FilePath, checks = None, directory_is_symlink: bool = False) -> Iterator[Dict]:
	"""
	Read all dicts in YAML-format from a file in a safe manner
	Note: since the return type from safe_load_all() is an iterator evaluation doesn't happen until
	      iterating; this means that exceptions must be handled when iterating rather than when getting
	      the return value

		Parameters:
			path (FilePath): The path to read from
			directory_is_symlink (bool): The directory that the path points to is a symlink
		Returns:
			iterator[dict]: An iterator of dicts
		Raises:
			FileNotFoundError
			ikttypes.FilePathAuditError
	"""

	string = iktio.secure_read_string(path, checks = checks, directory_is_symlink = directory_is_symlink)
	return yaml.safe_load_all(string)
