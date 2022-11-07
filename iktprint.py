#! /usr/bin/env python3
# Requires: python3 (>= 3.6)

"""
Print themed strings to the console
"""

import errno
from getpass import getpass
from pathlib import PurePath
import subprocess
import sys
from typing import List, Sequence, Union

from ikttypes import ANSIThemeString, FilePath, FilePathAuditError, SecurityChecks, SecurityPolicy
import iktio

theme = None
themepath = None

def clear_screen() -> int:
	"""
	Clear the screen

		Returns:
			retval (int): 0 on success, errno on failure
	"""

	try:
		cpath = iktio.secure_which(FilePath("/usr/bin/clear"), fallback_allowlist = [], security_policy = SecurityPolicy.ALLOWLIST_STRICT)
	except FileNotFoundError:
		return errno.ENOENT

	return subprocess.run([cpath], check = False).returncode

def __themearray_to_string(themearray) -> str:
	if theme is None or themepath is None:
		sys.exit("__themearray_to_string() used without calling init_iktprint() first; this is a programming error.")

	string: str = ""
	for themestring in themearray:
		#if not isinstance(themestring, ANSIThemeString):
		#	raise TypeError(f"__themarray_to_string() only accepts themestrings; this themearray consists of:\n{themearray}")

		if isinstance(themestring, ANSIThemeString):
			theme_attr_ref = themestring.themeref
			theme_string = str(themestring)
		elif isinstance(themestring, tuple):
			theme_string, theme_attr_ref = themestring.themeref

		if theme is not None:
			if theme_attr_ref in theme["term"]:
				attr = theme["term"][theme_attr_ref]
				reset = theme["term"]["reset"]
				string += f"{attr}{themestring}{reset}"
			else:
				raise Exception(f"attribute (“term“, “{theme_attr_ref}“) does not exist in {themepath}")
		else:
			string += themestring

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

	return sum(map(len, themearray))

def ansithemestring_join_tuple_list(items: Sequence[Union[str, ANSIThemeString]], formatting: str = "default", separator: ANSIThemeString = ANSIThemeString(", ", "separator")) -> List[ANSIThemeString]:
	"""
	Given a list of ANSIThemeStrings or strings + formatting, join them separated by a separator

		Parameters:
			items (list[Union(str, ANSIThemeString)]): The items to join into an ANSIThemeString list
			formatting (str): The formatting to use if the list is a string-list
			separator (ANSIThemeString): The list separator to use
		Return:
			themearray (list[ANSIThemeString]): The resulting ANSIThemeString list
	"""

	themearray = []
	first = True

	for item in items:
		if isinstance(item, str):
			tmpitem = ANSIThemeString(item, formatting)
		else:
			tmpitem = item

		if first == False:
			if separator is not None:
				themearray.append(separator)
		else:
			first = False
		themearray.append(tmpitem)

	return themearray

def iktinput(themearray: List[ANSIThemeString]) -> str:
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
	tmp = input(string) # nosec
	tmp = tmp.replace("\x00", "<NUL>")
	return tmp

def iktinput_password(themearray: List[ANSIThemeString]) -> str:
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
	tmp = getpass(string)
	if tmp is not None:
		tmp = tmp.replace("\x00", "<NUL>")
	return tmp

def iktprint(themearray: List[ANSIThemeString], stderr: bool = False) -> None:
#def iktprint(themearray, stderr: bool = False) -> None:
	"""
	Print a themearray;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[ANSIThemeString]): The themearray to print
			stderr (bool): True to print to stderr, False to print to stdout
	"""

	if theme is None or themepath is None:
		sys.exit("iktprint() used without calling init_iktprint() first; this is a programming error.")

	string = __themearray_to_string(themearray)

	if stderr == True:
		print(string, file = sys.stderr)
	else:
		print(string)

def init_iktprint(themefile: FilePath) -> None:
	"""
	Initialise iktprint

		Parameters:
			themefile (str): Path to the theme to use
	"""

	global theme # pylint: disable=global-statement
	global themepath # pylint: disable=global-statement

	themepath = themefile

	# The parsers directory itself may be a symlink. This is expected behaviour when installing from a git repo,
	# but we only allow it if the rest of the path components are secure
	checks = [
		SecurityChecks.PARENT_RESOLVES_TO_SELF,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.EXISTS,
		SecurityChecks.IS_DIR,
	]

	theme_dir = FilePath(str(PurePath(themefile).parent))

	violations = iktio.check_path(theme_dir, checks = checks)
	if len(violations) > 0:
		violation_strings = []
		for violation in violations:
			violation_strings.append(str(violation))
		violations_joined = ",".join(violation_strings)
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = theme_dir)

	# We don't want to check that parent resolves to itself,
	# because when we have an installation with links directly to the git repo
	# the themes directory will be a symlink
	checks = [
		SecurityChecks.RESOLVES_TO_SELF,
		SecurityChecks.PARENT_OWNER_IN_ALLOWLIST,
		SecurityChecks.OWNER_IN_ALLOWLIST,
		SecurityChecks.PARENT_PERMISSIONS,
		SecurityChecks.PERMISSIONS,
		SecurityChecks.EXISTS,
		SecurityChecks.IS_FILE,
	]

	try:
		theme = iktio.secure_read_yaml(themefile, checks = checks)
	except FileNotFoundError:
		print(f"Warning: themefile ”{themefile}” does not exist", file = sys.stderr)
		return
