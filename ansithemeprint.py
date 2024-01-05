#! /usr/bin/env python3
# Requires: python3 (>= 3.8)

"""
Print themed strings to the console
"""

import errno
from getpass import getpass
from pathlib import PurePath
import subprocess
import sys
from typing import List, Optional, Sequence, Union

from cmttypes import FilePath, FilePathAuditError, SecurityChecks, SecurityPolicy, SecurityStatus
import cmtio
try:
	# python3-yaml is installed by cmt-install; thus we cannot rely on yaml being importable
	# pylint: disable-next=unused-import
	import yaml # noqa
	from cmtio_yaml import secure_read_yaml
	use_fallback_theme = False
except ModuleNotFoundError:
	use_fallback_theme = True

class ANSIThemeString:
	"""
	A themed string for printing with ANSI control codes

		Parameters:
			string: A string
			themeref: The reference to use when doing a looking in themes
	"""

	def __init__(self, string: str, themeref: str) -> None:
		if not isinstance(string, str) or not isinstance(themeref, str):
			raise TypeError("ANSIThemeString only accepts (str, str)")
		self.string = string
		self.themeref = themeref

	def __str__(self) -> str:
		return self.string

	def __len__(self) -> int:
		return len(self.string)

	def __repr__(self) -> str:
		return f"ANSIThemeString(string=\"{self.string}\", themeref=\"{self.themeref}\")"

	def format(self, themeref: str) -> "ANSIThemeString":
		self.themeref = themeref
		return self

	def get_themeref(self) -> str:
		return self.themeref

	def upper(self) -> "ANSIThemeString":
		return ANSIThemeString(self.string.upper(), self.themeref)

	def lower(self) -> "ANSIThemeString":
		return ANSIThemeString(self.string.upper(), self.themeref)

	def capitalize(self) -> "ANSIThemeString":
		return ANSIThemeString(self.string.capitalize(), self.themeref)

theme = None
themepath = None

fallback_theme = {
	"term": {
		"default": "\033[0m",                           # reset
		"programname": "\033[1;37m",                    # white + bright
		"version": "\033[0;32m",                        # green
		"candidateversion": "\033[1;36m",               # cyan + bright
		# FIXME: having command the same colour as action is probably not a good choice
		"command": "\033[1;36m",                        # cyan + bright
		"option": "\033[0;36m",                         # cyan
		"argument": "\033[0;32m",                       # green
		"separator": "\033[38;5;240m",                  # grey + dim
		"description": "\033[0m",                       # reset
		"hostname": "\033[1;37m",                       # white + bright
		"path": "\033[0;36m",                           # cyan
		"url": "\033[1;4;37m",                          # white + bright + underline
		"header": "\033[0;4;37m",                       # white + underline
		"underline": "\033[0;4;37m",                    # white + underline
		"emphasis": "\033[1;37m",                       # white + bright
		"skip": "\033[38;5;240m\033[1m",                # grey + dim + bold
		"ok": "\033[1;37m",                             # white + bright
		"notok": "\033[1;31m",                          # red + bright
		"success": "\033[1;32m",                        # green + bright
		"note": "\033[0;32m",                           # green
		"error": "\033[1;31m",                          # red + bright
		"warning": "\033[1;33m",                        # yellow + bright
		"critical": "\033[1;41;93m",                    # red + bright + inverted
		"errorvalue": "\033[0;31m",                     # red
		"phase": "\033[1;33m",                          # yellow + bright
		"action": "\033[1;36m",                         # cyan + bright
		"play": "\033[0;36m",                           # cyan
		"none": "\033[38;5;240m\033[1m",                # grey + dim + bold
		"unknown": "\033[0;31m",                        # red
		"reset": "\033[0m",                             # reset all attributes
		"yaml_list": "\033[1;33m",                      # yellow + bright
		"yaml_key": "\033[1;36m",                       # cyan + bright
		"yaml_key_separator": "\033[0;37m",             # white
		"yaml_value": "\033[0m",                        # reset
		"namespace": "\033[0;36m",                      # cyan
	}
}

def clear_screen() -> int:
	"""
	Clear the screen

		Returns:
			retval (int): 0 on success, errno on failure
	"""

	try:
		cpath = cmtio.secure_which(FilePath("/usr/bin/clear"), fallback_allowlist = [],
					   security_policy = SecurityPolicy.ALLOWLIST_STRICT)
	except FileNotFoundError:
		return errno.ENOENT

	return subprocess.run([cpath], check = False).returncode

def __themearray_to_raw_string(themearray: List[ANSIThemeString]) -> str:
	string: str = ""
	for themestring in themearray:
		if not isinstance(themestring, ANSIThemeString):
			raise TypeError(f"__themarray_to_string() only accepts arrays of AnsiThemeString; this themearray consists of:\n{themearray}")

		theme_string = str(themestring)
		string += theme_string

	return string

def __themearray_to_string(themearray: List[ANSIThemeString], color: bool = True) -> str:
	if theme is None or themepath is None:
		sys.exit("__themearray_to_string() used without calling init_ansithemestring() first; this is a programming error.")

	string: str = ""
	for themestring in themearray:
		if not isinstance(themestring, ANSIThemeString):
			raise TypeError(f"__themarray_to_string() only accepts arrays of AnsiThemeString; this themearray consists of:\n{themearray}")

		theme_attr_ref = themestring.themeref
		theme_string = str(themestring)

		if theme is not None and color:
			if theme_attr_ref in theme["term"]:
				attr = theme["term"][theme_attr_ref]
				reset = theme["term"]["reset"]
				string += f"{attr}{theme_string}{reset}"
			else:
				raise KeyError(f"attribute (“term“, “{theme_attr_ref}“) does not exist in {themepath}")
		else:
			string += theme_string

	if len(string) > 0:
		string = string.replace("\x0033", "\033")

	return string

def themearray_override_formatting(themearray: List[ANSIThemeString], formatting: Optional[str]) -> List[ANSIThemeString]:
	new_themearray = []

	for themestr in themearray:
		if formatting is not None:
			themestr = themestr.format(formatting)
		new_themearray.append(themestr)

	return new_themearray

def themearray_len(themearray: List[ANSIThemeString]) -> int:
	"""
	Return the length of a themearray

		Parameters:
			themearray (list[ANSIThemeString]): The themearray to return the length of
		Return:
			The length of the themearray
	"""

	return sum(map(len, themearray))

def themearray_ljust(themearray: List[ANSIThemeString], width: int) -> List[ANSIThemeString]:
	"""
	Return a ljust:ed themearray (will always pad with ANSIThemeString("", "default"))

		Parameters:
			themearray (list[ANSIThemeString]): The themearray to ljust
		Return:
			The ljust:ed themearray
	"""

	tlen = themearray_len(themearray)
	if tlen < width:
		themearray = themearray + [ANSIThemeString("".ljust(width - tlen), "default")]
	return themearray

def ansithemestring_join_tuple_list(items: Sequence[Union[str, ANSIThemeString]],
				    formatting: str = "default", separator: ANSIThemeString = ANSIThemeString(", ", "separator")) -> List[ANSIThemeString]:
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

		if not first:
			if separator is not None:
				themearray.append(separator)
		else:
			first = False
		themearray.append(tmpitem)

	return themearray

def ansithemeinput(themearray: List[ANSIThemeString], color: str = "auto") -> str:
	"""
	Print a themearray and input a string;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[(str, str)]): The themearray to print
			color (str):
				"always": Always use ANSI-formatting
				"never": Never use ANSI-formatting
				"auto": Use ANSI-formatting except when redirected (not implemented yet)
		Returns:
			string (str): The inputted string
	"""

	if theme is None or themepath is None:
		sys.exit("ansithemeinput() used without calling init_ansithemeprint() first; this is a programming error.")

	string = __themearray_to_string(themearray, color = color)
	try:
		tmp = input(string) # nosec
	except KeyboardInterrupt:
		print()
		sys.exit(errno.ECANCELED)
	tmp = tmp.replace("\x00", "<NUL>")
	return tmp

def ansithemeinput_password(themearray: List[ANSIThemeString], color: str = "auto") -> str:
	"""
	Print a themearray and input a password;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[(str, str)]): The themearray to print
		Returns:
			string (str): The inputted password
			color (str):
				"always": Always use ANSI-formatting
				"never": Never use ANSI-formatting
				"auto": Use ANSI-formatting except when redirected (not implemented yet)
	"""

	if theme is None or themepath is None:
		sys.exit("ansithemeinput_password() used without calling init_ansithemeprint() first; this is a programming error.")

	string = __themearray_to_string(themearray, color = color)
	try:
		tmp = getpass(string)
	except KeyboardInterrupt:
		print()
		sys.exit(errno.ECANCELED)
	if tmp is not None:
		tmp = tmp.replace("\x00", "<NUL>")
	return tmp

def ansithemeprint(themearray: List[ANSIThemeString], stderr: bool = False, color: str = "auto") -> None:
	"""
	Print a themearray;
	a themearray is a list of format strings of the format:
	(string, theme_attr_ref); context is implicitly understood to be term

		Parameters:
			themearray (list[ANSIThemeString]): The themearray to print
			stderr (bool): True to print to stderr, False to print to stdout
			color (str):
				"always": Always use ANSI-formatting
				"never": Never use ANSI-formatting
				"auto": Use ANSI-formatting except when redirected (not implemented yet)
	"""

	if theme is None or themepath is None:
		sys.exit("ansithemeprint() used without calling init_ansithemeprint() first; this is a programming error.")

	if color == "auto":
		if stderr and not sys.stderr.isatty():
			use_color = False
		elif not stderr and not sys.stdout.isatty():
			use_color = False
		else:
			use_color = True
	elif color == "always":
		use_color = True
	elif color == "never":
		use_color = False
	else:
		sys.exit("Incorrect value for color passed to ansithemeprint(); the only valid values are ”always”, ”auto”, and ”never”; this is a programming error.")

	string = __themearray_to_string(themearray, color = use_color)

	if stderr:
		print(string, file = sys.stderr)
	else:
		print(string)

def init_ansithemeprint(themefile: Optional[FilePath]) -> None:
	"""
	Initialise ansithemeprint

		Parameters:
			themefile (str): Path to the theme to use
	"""

	global theme # pylint: disable=global-statement
	global themepath # pylint: disable=global-statement

	# If we get None as theme we use the builtin fallback theme
	if themefile is None:
		theme = fallback_theme
		themepath = FilePath("<built-in default>")
		return

	themepath = themefile

	# The themes directory itself may be a symlink. This is expected behaviour when installing from a git repo,
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

	violations = cmtio.check_path(theme_dir, checks = checks)
	if violations != [SecurityStatus.OK]:
		violations_joined = cmtio.join_securitystatus_set(",", set(violations))
		raise FilePathAuditError(f"Violated rules: {violations_joined}", path = theme_dir)

	# We do not want to check that parent resolves to itself,
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

	if use_fallback_theme:
		theme = fallback_theme
		themepath = FilePath("<built-in default>")
	else:
		try:
			theme = secure_read_yaml(themefile, checks = checks)
		except FileNotFoundError:
			theme = fallback_theme
			ansithemeprint([ANSIThemeString("Warning", "warning"),
					ANSIThemeString(": themefile ”", "default"),
					ANSIThemeString(f"{themefile}", "path"),
					ANSIThemeString("” does not exist; using built-in fallback theme.", "default")], stderr = True)
			return
