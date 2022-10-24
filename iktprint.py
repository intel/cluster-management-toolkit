#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
Print themed strings to the console
"""

import errno
from getpass import getpass
import os
import subprocess
import sys
import typing # pylint: disable=unused-import
import yaml

from ikttypes import FilePath, SecurityPolicy
import iktio

theme = None
themepath = None

def clear_screen() -> int:
	"""
	Clear the screen

		Returns:
			retval (int): 0 on success, errno on failure
	"""

	fallback_allowlist = ["/bin/clear", "/usr/bin/clear"]

	try:
		cpath = iktio.secure_which(FilePath("/usr/bin/clear"), fallback_allowlist = fallback_allowlist, security_policy = SecurityPolicy.ALLOWLIST_STRICT)
	except FileNotFoundError:
		return errno.ENOENT

	return subprocess.run([cpath], check = False).returncode

def __themearray_to_string(themearray):
	if theme is None or themepath is None:
		sys.exit("iktinput() used without calling init_iktprint() first; this is a programming error.")

	string = ""
	for _string, theme_attr_ref in themearray:
		if theme is not None:
			if theme_attr_ref in theme["term"]:
				attr = theme["term"][theme_attr_ref]
				reset = theme["term"]["reset"]
				string += f"{attr}{_string}{reset}"
			else:
				raise Exception(f"attribute (“term“, “{theme_attr_ref}“) does not exist in {themepath}")
		else:
			string += _string

	if len(string) > 0:
		string = string.replace("\x0033", "\033")

	return string

def themearray_len(themearray) -> int:
	"""
	Return the length of a themearray

		Parameters:
			themearray (list[(str, str)]): The themearray to return the length of
		Return:
			The length of the themearray
	"""

	return len("".join([_str for _str, _format in themearray]))

def iktinput(themearray) -> str:
	"""
	Print a themearray and input a string;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[(str, str)]): The themearray to print
		Returns:
			string (str): The inputted string
	"""

	if theme is None or themepath is None:
		sys.exit("iktinput() used without calling init_iktprint() first; this is a programming error.")

	string = __themearray_to_string(themearray)
	return input(string) # nosec

def iktinput_password(themearray):
	"""
	Print a themearray and input a password;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[(str, str)]): The themearray to print
		Returns:
			string (str): The inputted password
	"""

	if theme is None or themepath is None:
		sys.exit("iktinput_password() used without calling init_iktprint() first; this is a programming error.")

	string = __themearray_to_string(themearray)
	return getpass(string)

def iktprint(themearray, stderr: bool = False):
	"""
	Print a themearray;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[(str, str)]): The themearray to print
			stderr (bool): True to print to stderr, False to print to stdout
	"""

	if theme is None or themepath is None:
		sys.exit("iktprint() used without calling init_iktprint() first; this is a programming error.")

	string = __themearray_to_string(themearray)

	if stderr == True:
		print(string, file = sys.stderr)
	else:
		print(string)

def init_iktprint(themefile: FilePath):
	"""
	Initialise iktprint

		Parameters:
			themefile (str): Path to the theme to use
	"""

	global theme # pylint: disable=global-statement
	global themepath # pylint: disable=global-statement

	themepath = themefile

	if os.path.isfile(themefile) is False:
		print(f"Warning: themefile ”{themefile}” does not exist", file = sys.stderr)
		return

	with open(themefile, encoding = "utf-8") as f:
		theme = yaml.safe_load(f)
