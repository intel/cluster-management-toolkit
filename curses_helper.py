#! /usr/bin/env python3

"""
Curses-based User Interface helpers
"""

# Before calling into this helper you need to call init_colors()

import copy
import curses
import curses.textpad
from datetime import datetime
from enum import IntFlag
import errno
from operator import attrgetter
from pathlib import Path, PurePath
import sys
import traceback
from typing import Any, cast, Dict, List, Optional, NamedTuple, NoReturn, Set, Tuple, Type, Union

try:
	from natsort import natsorted
except ModuleNotFoundError:
	sys.exit("ModuleNotFoundError: You probably need to install python3-natsort; did you forget to run cmt-install?")

from cmtio import check_path, join_securitystatus_set
from cmtio_yaml import secure_read_yaml
from cmtlog import CMTLogType, CMTLog
from cmttypes import deep_get, DictPath, FilePath, FilePathAuditError, ProgrammingError, LogLevel, Retval
from cmttypes import SecurityChecks, SecurityStatus, StatusGroup, loglevel_to_name, stgroup_mapping

from ansithemeprint import ANSIThemeString, ansithemeprint

import cmtlib

theme: Dict = {}
themefile: Optional[FilePath] = None

mousemask = 0

# A reference to text formatting
class ThemeAttr(NamedTuple):
	"""
	A reference to formatting for a themed string

		Parameters:
			context: The context to use when doing a looking in themes
			key: The key to use when doing a looking in themes
	"""

	context: str
	key: str

class ThemeString:
	"""
	A themed string

		Parameters:
			string: A string
			themeattr: The themeattr used to format the string
			selected (Optional[bool]): Should the selected or unselected formatting be used
	"""

	def __init__(self, string: str, themeattr: ThemeAttr, selected: bool = False) -> None:
		if not isinstance(string, str):
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("ThemeString()", "emphasis"),
					 ANSIThemeString(" initialised with invalid argument(s):", "error")],
					[ANSIThemeString("string (type: ", "error")],
					[ANSIThemeString(f"{type(string)}", "argument")],
					[ANSIThemeString(", expected str):", "error")],
					[ANSIThemeString(f"{string}", "default")],
					[ANSIThemeString("themeattr (type: ", "error")],
					[ANSIThemeString(f"{type(themeattr)}", "argument")],
					[ANSIThemeString(", expected ThemeAttr):", "error")],
					[ANSIThemeString(f"{themeattr}", "default")],
					[ANSIThemeString("selected (type: ", "error")],
					[ANSIThemeString(f"{type(selected)}", "argument")],
					[ANSIThemeString(", expected bool):", "error")],
					[ANSIThemeString(f"{selected}", "default")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise TypeError(f"ThemeString only accepts (str, ThemeAttr[, bool]); received ThemeString({string}, {themeattr}, selected)")
		self.string = string
		self.themeattr = themeattr
		self.selected = selected

	def __str__(self) -> str:
		return self.string

	def __len__(self) -> int:
		return len(self.string)

	def __repr__(self) -> str:
		return f"ThemeString(\"{self.string}\", {repr(self.themeattr)}, {self.selected})"

	def get_themeattr(self) -> ThemeAttr:
		"""
		Return the ThemeAttr attribute of the ThemeString

			Returns:
				themeattr (ThemeAttr): The ThemeAttr attribute of the ThemeString
		"""

		return self.themeattr

	def get_selected(self) -> bool:
		"""
		Return the selected attribute of the ThemeString

			Returns:
				selected  (bool): The selected attribute of the ThemeString
		"""

		return self.selected

	def __eq__(self, obj) -> bool:
		if not isinstance(obj, ThemeString):
			return False

		return repr(obj) == repr(self)

class ThemeRef:
	"""
	A reference to a themed string; while the type definition is the same as ThemeAttr its use is different.

		Parameters:
			context: The context to use when doing a looking in themes
			key: The key to use when doing a looking in themes
			selected (Optional[bool]): Should the selected or unselected formatting be used
	"""

	def __init__(self, context: str, key: str, selected: bool = False) -> None:
		if not isinstance(context, str) or not isinstance(key, str) or (selected is not None and not isinstance(selected, bool)):
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("ThemeRef()", "emphasis"),
					 ANSIThemeString(" initialised with invalid argument(s):", "error")],
					[ANSIThemeString("context (type: ", "error")],
					[ANSIThemeString(f"{type(context)}", "argument")],
					[ANSIThemeString(", expected str):", "error")],
					[ANSIThemeString(f"{context}", "default")],
					[ANSIThemeString("key (type: ", "error")],
					[ANSIThemeString(f"{type(key)}", "argument")],
					[ANSIThemeString(", expected str):", "error")],
					[ANSIThemeString(f"{key}", "default")],
					[ANSIThemeString("selected (type: ", "error")],
					[ANSIThemeString(f"{type(selected)}", "argument")],
					[ANSIThemeString(", expected bool):", "error")],
					[ANSIThemeString(f"{selected}", "default")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise TypeError("ThemeRef only accepts (str, str[, bool])")
		self.context = context
		self.key = key
		self.selected = selected

	def __str__(self) -> str:
		string = ""
		array = deep_get(theme, DictPath(f"{self.context}#{self.key}"))
		if array is None:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("The ThemeRef(", "error")],
					[ANSIThemeString(f"{self.context}", "argument")],
					[ANSIThemeString(", ", "error")],
					[ANSIThemeString(f"{self.key}", "argument")],
					[ANSIThemeString(") does not exist.", "error")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise ValueError(f"The ThemeRef(\"{self.context}\", \"{self.key}\") does not exist")
		for string_fragment, _attr in array:
			string += string_fragment
		return string

	def __len__(self) -> int:
		return len(str(self))

	def __repr__(self) -> str:
		return f"ThemeRef(\"{self.context}\", \"{self.key}\", {self.selected})"

	def to_themearray(self) -> List[ThemeString]:
		"""
		Return the themearray representation of the ThemeRef

			Returns:
				themearray (ThemeArray): The themearray representation
		"""

		themearray = []
		array = deep_get(theme, DictPath(f"{self.context}#{self.key}"))
		if array is None:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("The ThemeRef(", "error")],
					[ANSIThemeString(f"{self.context}", "argument")],
					[ANSIThemeString(", ", "error")],
					[ANSIThemeString(f"{self.key}", "argument")],
					[ANSIThemeString(") does not exist.", "error")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise ValueError(f"The ThemeRef(\"{self.context}\", \"{self.key}\") does not exist")
		for string, themeattr in array:
			themearray.append(ThemeString(string, ThemeAttr(themeattr[0], themeattr[1]), self.selected))
		return themearray

	def get_selected(self) -> bool:
		"""
		Return the selected attribute of the ThemeRef

			Returns:
				selected (bool): The selected attribute of the ThemeRef
		"""

		return self.selected

	def __eq__(self, obj) -> bool:
		if not isinstance(obj, ThemeRef):
			return False

		return repr(obj) == repr(self)

class ThemeArray:
	"""
	An array of themed strings and references to themed strings

		Parameters:
			list[Union[ThemeString, ThemeRef]]: The themearray
			selected (Optional[bool]): Should the selected or unselected formatting be used; passing selected overrides the individual components
	"""

	def __init__(self, array: List[Union[ThemeRef, ThemeString]], selected: Optional[bool] = None) -> None:
		if array is None:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("ThemeArray()", "emphasis"),
					 ANSIThemeString(" initialised with an empty array:", "error")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise ValueError("A ThemeArray cannot be None")

		newarray: List[Union[ThemeRef, ThemeString]] = []
		for item in array:
			if not isinstance(item, (ThemeRef, ThemeString)):
				CMTLog(CMTLogType.DEBUG, [
						[ANSIThemeString("ThemeArray()", "emphasis"),
						 ANSIThemeString(" initialised with invalid type ", "error"),
						 ANSIThemeString(f"{type(item)}", "argument"),
						 ANSIThemeString("; substring:", "error")],
						[ANSIThemeString(f"{item}", "default")],
						[ANSIThemeString("Backtrace:", "error")],
						[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
				       ], severity = LogLevel.ERR, facility = str(themefile))
				raise TypeError("All individual elements of a ThemeArray must be either ThemeRef or ThemeString")
			if selected is None:
				newarray.append(item)
			elif isinstance(item, ThemeString):
				newarray.append(ThemeString(item.string, item.themeattr, selected = selected))
			elif isinstance(item, ThemeRef):
				newarray.append(ThemeRef(item.context, item.key, selected = selected))

		self.array = newarray

	def append(self, item: Union[ThemeRef, ThemeString]) -> None:
		"""
		Append a ThemeRef or ThemeString to the ThemeArray

			Parameters:
				item (union(ThemeRef, ThemeString)): The item to append
		"""

		if not isinstance(item, (ThemeRef, ThemeString)):
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("ThemeArray.append()", "emphasis"),
					 ANSIThemeString(" called with invalid type ", "error"),
					 ANSIThemeString(f"{type(item)}", "argument"),
					 ANSIThemeString("; substring:", "error")],
					[ANSIThemeString(f"{item}", "default")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise TypeError("All individual elements of a ThemeArray must be either ThemeRef or ThemeString")
		self.array.append(item)

	def __add__(self, array: List[Union[ThemeRef, ThemeString]]) -> "ThemeArray":
		tmparray: List[Union[ThemeRef, ThemeString]] = []
		for item in self.array:
			tmparray.append(item)
		for item in array:
			tmparray.append(item)
		return ThemeArray(tmparray)

	def __str__(self) -> str:
		string = ""
		for item in self.array:
			string += str(item)
		return string

	def __len__(self) -> int:
		arraylen = 0
		for item in self.array:
			arraylen += len(item)
		return arraylen

	def __repr__(self) -> str:
		references = ""
		first = True
		for item in self.array:
			if first == True:
				references += f"{repr(item)}"
			else:
				references += f", {repr(item)}"
			first = False
		return f"ThemeArray({references})"

	def __eq__(self, obj) -> bool:
		if not isinstance(obj, ThemeArray):
			return False

		return repr(obj) == repr(self)

	def to_list(self) -> List[Union[ThemeRef, ThemeString]]:
		return self.array

def format_helptext(helptext: List[Tuple[str, str]]) -> List[Dict]:
	"""
	Given a helptext in the format [(key, description)], format it in a way suitable for windowwidget

		Parameters:
			helptext: list[(key, description)]: A list of rows with keypress + effect
		Returns:
			formatted_helptext (Dict): The formatted helptext
	"""

	formatted_helptext: List[Dict] = []

	for key, description in helptext:
		formatted_helptext.append({
			"lineattrs": WidgetLineAttrs.NORMAL,
			"columns": [[ThemeString(key, ThemeAttr("windowwidget", "highlight"))], [ThemeString(description, ThemeAttr("windowwidget", "default"))]],
			"retval": None,
		})

	return formatted_helptext

# pylint: disable-next=too-few-public-methods
class curses_configuration:
	"""
	Configuration options for the curses UI
	"""

	abouttext: Optional[List[Tuple[int, List[ThemeString]]]] = None
	mousescroll_enable: bool = False
	mousescroll_up: int = 0b10000000000000000
	mousescroll_down: int = 0b1000000000000000000000000000

def set_mousemask(mask: int) -> None:
	"""
	Enable/disable mouse support
	"""

	global mousemask # pylint: disable=global-statement
	curses.mousemask(mask)
	mousemask = mask

def get_mousemask() -> int:
	"""
	Get the default mouse mask
	"""

	return mousemask

__color = {
}

__pairs: Dict = {
}

color_map = {
	"black": curses.COLOR_BLACK,
	"red": curses.COLOR_RED,
	"green": curses.COLOR_GREEN,
	"yellow": curses.COLOR_YELLOW,
	"blue": curses.COLOR_BLUE,
	"magenta": curses.COLOR_MAGENTA,
	"cyan": curses.COLOR_CYAN,
	"white": curses.COLOR_WHITE,
}

def get_theme_ref() -> Dict:
	"""
	Get a reference to the theme
	"""

	return theme

def __color_name_to_curses_color(color: Tuple[str, str], color_type: str) -> int:
	col, attr = color

	if not isinstance(attr, str):
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Invalid color attribute used in theme; attribute has to be a string and one of:", "default")],
				[ANSIThemeString("“", "default"),
				 ANSIThemeString("normal", "emphasis"),
				 ANSIThemeString("“, “", "default"),
				 ANSIThemeString("bright", "emphasis"),
				 ANSIThemeString("“.", "default")],
				[ANSIThemeString("Using “", "default"),
				 ANSIThemeString("normal", "emphasis"),
				 ANSIThemeString("“ as fallback.", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		attr = "normal"
	elif attr not in ["normal", "bright"]:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Invalid color attribute “", "default"),
				 ANSIThemeString(f"{attr}", "emphasis"),
				 ANSIThemeString("“ used in theme; attribute has to be a string and one of:", "default")],
				[ANSIThemeString("“", "default"),
				 ANSIThemeString("normal", "emphasis"),
				 ANSIThemeString("“, “", "default"),
				 ANSIThemeString("bright", "emphasis"),
				 ANSIThemeString("“.", "default")],
				[ANSIThemeString("Using “", "default"),
				 ANSIThemeString("normal", "emphasis"),
				 ANSIThemeString("“ as fallback.", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		attr = "normal"
	if isinstance(col, str):
		col = col.lower()

	if not isinstance(col, str) or col not in color_map:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Invalid color type “", "default"),
				 ANSIThemeString(f"{col}", "emphasis"),
				 ANSIThemeString("“ used in theme; color has to be a string and one of:", "default"),
				 ANSIThemeString("“" + "“, ".join(color_map.keys()) +  "“", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		raise ValueError(f"Invalid color type used in theme; color has to be a string and one of: {', '.join(color_map.keys())}")

	if attr == "bright":
		curses_attr = 8
	else:
		curses_attr = 0

	curses_color = deep_get(color_map, DictPath(col))
	if curses_color is None:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Invalid {color_type} color “", "default"),
				 ANSIThemeString(f"{col}", "emphasis"),
				 ANSIThemeString("“ used in theme; valid colors are:", "default"),
				 ANSIThemeString("“" + "“, ".join(color_map.keys()) +  "“", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		raise ValueError(f"Invalid {color_type} color {col} used in theme; valid colors are: {', '.join(color_map.keys())}")
	return curses_color + curses_attr

def __convert_color_pair(color_pair: Tuple[Tuple[str, str], Tuple[str, str]]) -> Tuple[int, int]:
	fg, bg = color_pair

	curses_fg = __color_name_to_curses_color(fg, "foreground")
	curses_bg = __color_name_to_curses_color(bg, "background")

	return (curses_fg, curses_bg)

def __init_pair(pair: str, color_pair: Tuple[int, int], color_nr: int) -> None:
	fg, bg = color_pair
	bright_black_remapped = False

	try:
		curses.init_pair(color_nr, fg, bg)
		if fg == bg:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("__init_pair()", "emphasis"),
					 ANSIThemeString(" called with a color pair where fg == bg (", "error"),
					 ANSIThemeString(f"{fg}", "argument"),
					 ANSIThemeString(",", "error"),
					 ANSIThemeString(f"{bg}", "argument"),
					 ANSIThemeString(")", "error")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise ValueError(f"The theme contains a color pair ({pair}) where fg == bg ({bg})")
	except (curses.error, ValueError) as e:
		if str(e) in ("init_pair() returned ERR", "Color number is greater than COLORS-1 (7)."):
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("init_pair()", "emphasis"),
					 ANSIThemeString(" failed; attempting to limit fg & bg to ", "error"),
					 ANSIThemeString("0", "argument"),
					 ANSIThemeString("-", "error"),
					 ANSIThemeString("7", "argument"),
					 ANSIThemeString(")", "error")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.DEBUG, facility = str(themefile))

			# Most likely we failed due to the terminal only
			# supporting colours 0-7. If "bright black" was
			# requested, we need to remap it. Fallback to blue;
			# hopefully there are no cases of bright black on blue.
			if fg & 7 == curses.COLOR_BLACK:
				fg = curses.COLOR_BLUE
				bright_black_remapped = True
			if fg & 7 == bg & 7:
				CMTLog(CMTLogType.DEBUG, [
						[ANSIThemeString("__init_pair()", "emphasis"),
						 ANSIThemeString(" called with a color pair where fg == bg (", "error"),
						 ANSIThemeString(f"{fg}", "argument"),
						 ANSIThemeString(",", "error"),
						 ANSIThemeString(f"{bg}", "argument"),
						 ANSIThemeString(f"{bright_black_remapped}", "argument")],
						[ANSIThemeString("Backtrace:", "error")],
						[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
				       ], severity = LogLevel.ERR, facility = str(themefile))
				raise ValueError(f"The theme contains a color pair ({pair}) where fg == bg ({bg}; bright black remapped: {bright_black_remapped})") from e
			curses.init_pair(color_nr, fg & 7, bg & 7)
		else:
			raise

def read_theme(configthemefile: FilePath, defaultthemefile: FilePath) -> None:
	"""
	Read the theme file and initialise the theme dict

		Parameters:
			configthemefile (FilePath): The theme to read
			defaultthemefile (FilePath): The fallback if the other theme is not available
	"""

	global theme # pylint: disable=global-statement
	global themefile # pylint: disable=global-statement

	for item in [configthemefile, f"{configthemefile}.yaml", defaultthemefile]:
		if Path(item).is_file():
			themefile = cast(FilePath, item)
			break

	if themefile is None:
		print("Error: could not find a valid theme file; aborting.", file = sys.stderr)
		sys.exit(errno.ENOENT)

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

	violations = check_path(theme_dir, checks = checks)
	if violations != [SecurityStatus.OK]:
		violations_joined = join_securitystatus_set(",", set(violations))
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

	theme = secure_read_yaml(FilePath(themefile), checks = checks)

def init_curses() -> None:
	"""
	Initialise the curses helper; this configures all curses color pairs needed
	for the various ThemeAttrs
	"""

	color_last = 1

	# First we set the colour palette
	for col, curses_col in color_map.items():
		rgb = deep_get(theme, DictPath(f"colors#{col}"))
		if rgb is None:
			continue
		r, g, b = rgb
		try:
			curses.init_color(curses_col, r, g, b)
		except curses.error as e:
			if str(e) == "init_extended_color() returned ERR":
			# Most likely remapping the palette is not supported (16-color xterm?);
			# just ignore the remap attempt
				pass
			else:
				raise

	# Next we need to define all necessary colour pairs;
	# most of them come in selected and unselected variants
	for pair in theme["color_pairs_curses"]:
		if isinstance(theme["color_pairs_curses"][pair], list):
			unselected = __convert_color_pair(theme["color_pairs_curses"][pair])
			selected = unselected
		else:
			unselected = __convert_color_pair(theme["color_pairs_curses"][pair]["unselected"])
			selected = __convert_color_pair(theme["color_pairs_curses"][pair]["selected"])

		if unselected not in __pairs:
			__init_pair(pair, unselected, color_last)
			__pairs[unselected] = curses.color_pair(color_last)
			color_last += 1
		unselected_index = __pairs[unselected]
		if selected not in __pairs:
			__init_pair(pair, selected, color_last)
			__pairs[selected] = curses.color_pair(color_last)
			color_last += 1
		selected_index = __pairs[selected]
		__color[pair] = (unselected_index, selected_index)

def dump_themearray(themearray: List[Any]) -> NoReturn:
	"""
	Dump all individual parts of a ThemeArray;
	used for debug purposes

		Parameters:
			themearray (list): A themearray
	"""

	tmp = ""
	for substr in themearray:
		if isinstance(substr, ThemeString):
			tmp +=  "ThemeString:\n"
			tmp += f"          str: “{substr}“\n"
			tmp += f"       strlen: “{len(substr)}“\n"
			tmp += f"         attr: {substr.themeattr}\n"
			tmp += f"     selected: {substr.selected}\n"
		elif isinstance(substr, ThemeRef):
			tmp += f"   ThemeRef: {substr}\n"
			tmp += f"          str: “{str(substr)}“\n"
			tmp += f"          ctx: {substr.context}\n"
			tmp += f"          key: {substr.key}\n"
			tmp += f"     selected: {substr.selected}\n"
		elif isinstance(substr, tuple):
			tmp += f"      tuple: {substr}\n"
		elif isinstance(substr, list):
			tmp += f"       list: {substr}\n"
		else:
			tmp += f"TYPE {type(substr)}: {substr}\n"
	raise TypeError(f"themearray contains invalid substring(s):\n{tmp}\n{themearray}")

def color_log_severity(severity: LogLevel) -> ThemeAttr:
	"""
	Given severity, returns the corresponding ThemeAttr

		Parameters:
			severity (LogLevel): The severity
		Returns:
			themeattr (ThemeAttr): The corresponding ThemeAttr
	"""

	return ThemeAttr("logview", f"severity_{loglevel_to_name(severity).lower()}")

def color_status_group(status_group: StatusGroup) -> ThemeAttr:
	"""
	Given status group, returns the corresponding ThemeAttr

		Parameters:
			severity (LogLevel): The status group
		Returns:
			themeattr (ThemeAttr): The corresponding ThemeAttr
	"""

	return ThemeAttr("main", stgroup_mapping[status_group])

def window_tee_hline(win: curses.window, y: int, start: int, end: int, formatting: Optional[ThemeAttr] = None) -> None:
	"""
	Draw a horizontal line with "tees" ("├", "┤") at the ends

		Parameters:
			win (curses.window): The curses window to operate on
			y (int): The y-coordinate
			start (int): the starting point of the hline
			end (int): the ending point of the hline
			formatting (ThemeAttr): Optional ThemeAttr to apply to the line
	"""

	ltee = deep_get(theme, DictPath("boxdrawing#ltee"))
	rtee = deep_get(theme, DictPath("boxdrawing#rtee"))
	hline = deep_get(theme, DictPath("boxdrawing#hline"))

	if formatting is None:
		formatting = ThemeAttr("main", "default")

	hlinearray: List[Union[ThemeRef, ThemeString]] = [
		ThemeString(ltee, formatting),
		ThemeString("".rjust(end - start - 1, hline), formatting),
		ThemeString(rtee, formatting),
	]

	addthemearray(win, hlinearray, y = y, x = start)

def window_tee_vline(win: curses.window, x: int, start: int, end: int, formatting: Optional[ThemeAttr] = None) -> None:
	"""
	Draw a vertical line with "tees" ("┬", "┴") at the ends

		Parameters:
			win (curses.window): The curses window to operate on
			x (int): The y-coordinate
			start (int): the starting point of the vline
			end (int): the ending point of the vline
			formatting (ThemeAttr): Optional ThemeAttr to apply to the line
	"""

	ttee = deep_get(theme, DictPath("boxdrawing#ttee"))
	btee = deep_get(theme, DictPath("boxdrawing#btee"))
	vline = deep_get(theme, DictPath("boxdrawing#vline"))

	if formatting is None:
		formatting = ThemeAttr("main", "default")

	y = start

	addthemearray(win, [ThemeString(ttee, formatting)], y = y, x = x)

	while y < end:
		y += 1
		addthemearray(win, [ThemeString(vline, formatting)], y = y, x = x)

	addthemearray(win, [ThemeString(btee, formatting)], y = end, x = x)

# pylint: disable-next=too-many-arguments
def scrollbar_vertical(win: curses.window, x: int, miny: int, maxy: int, height: int, yoffset: int, clear_color: ThemeAttr) ->\
				Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int, int]]:
	"""
	Draw a vertical scroll bar

		Parameters:
			win (curses.window): The curses window to operate on
			x (int): The x-coordinate
			miny (int): the starting point of the scroll bar
			maxy (int): the ending point of the scroll bar
			height (int): the height of the scrollable area
			yoffset (int): the offset into the scrollable area
			clear_color (ThemeAttr): The theme attr to use if the scrollbar is disabled
		Returns:
			((int, int), (int, int), (int, int)): A tuple with (y, x) for the upper and lower arrow,
			as well as the midpoint of the dragger
	"""

	arrowup = deep_get(theme, DictPath("boxdrawing#arrowup"), "▲")
	arrowdown = deep_get(theme, DictPath("boxdrawing#arrowdown"), "▼")
	scrollbar = deep_get(theme, DictPath("boxdrawing#scrollbar"), "▒")
	verticaldragger_upper = deep_get(theme, DictPath("boxdrawing#verticaldragger_upper"), "█")
	verticaldragger_midpoint = deep_get(theme, DictPath("boxdrawing#verticaldragger_midpoint"), "◉")
	verticaldragger_lower = deep_get(theme, DictPath("boxdrawing#verticaldragger_lower"), "█")
	vline = deep_get(theme, DictPath("boxdrawing#vline"))
	upperarrow = (-1, -1)
	lowerarrow = (-1, -1)
	vdragger = (-1, -1, -1)

	maxoffset = height - (maxy - miny) - 1

	# We only need a scrollbar if we can actually scroll
	if maxoffset > 0:
		addthemearray(win, [ThemeString(arrowup, ThemeAttr("main", "scrollbar_arrows"))], y = miny, x = x)
		upperarrow = (miny, x)
		y = miny + 1
		while y < maxy:
			addthemearray(win, [ThemeString(scrollbar, ThemeAttr("main", "scrollbar"))], y = y, x = x)
			y += 1
		addthemearray(win, [ThemeString(arrowdown, ThemeAttr("main", "scrollbar_arrows"))], y = maxy, x = x)
		lowerarrow = (maxy, x)
		curpos = miny + 1 + int((maxy - miny) * (yoffset / (maxoffset)))
		curpos = min(curpos, maxy - 3)
		vdragger = (curpos, x, 3)
		addthemearray(win, [ThemeString(verticaldragger_upper, ThemeAttr("main", "dragger"))], y = curpos + 0, x = x)
		addthemearray(win, [ThemeString(verticaldragger_midpoint, ThemeAttr("main", "dragger_midpoint"))], y = curpos + 1, x = x)
		addthemearray(win, [ThemeString(verticaldragger_lower, ThemeAttr("main", "dragger"))], y = curpos + 2, x = x)
	# But we might need to cover up the lack of one if the window has been resized
	else:
		for y in range(miny, maxy + 1):
			addthemearray(win, [ThemeString(vline, clear_color)], y = y, x = x)

	# (y, x Upper arrow), (y, x Lower arrow), (y, x, len vertical dragger)
	return upperarrow, lowerarrow, vdragger

# pylint: disable-next=too-many-arguments
def scrollbar_horizontal(win: curses.window, y: int, minx: int, maxx: int, width: int, xoffset: int, clear_color: ThemeAttr) ->\
				Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int, int]]:
	"""
	Draw a horizontal scroll bar

		Parameters:
			win (curses.window): The curses window to operate on
			y (int): The y-coordinate
			minx (int): the starting point of the scroll bar
			maxx (int): the ending point of the scroll bar
			width (int): the width of the scrollable area
			xoffset (int): the offset into the scrollable area
			clear_color (ThemeAttr): The theme attr to use if the scrollbar is disabled
		Returns:
			((int, int), (int, int), (int, int)): A tuple with (y, x) for the upper and lower arrow,
			as well as the midpoint of the dragger
	"""

	arrowleft = deep_get(theme, DictPath("boxdrawing#arrowleft"), "▲")
	arrowright = deep_get(theme, DictPath("boxdrawing#arrowright"), "▼")
	scrollbar = deep_get(theme, DictPath("boxdrawing#scrollbar"), "▒")
	horizontaldragger_left = deep_get(theme, DictPath("boxdrawing#horizontaldragger_left"), "█")
	horizontaldragger_midpoint = deep_get(theme, DictPath("boxdrawing#horizontaldragger_midpoint"), "◉")
	horizontaldragger_right = deep_get(theme, DictPath("boxdrawing#horizontaldragger_right"), "█")
	hline = deep_get(theme, DictPath("boxdrawing#hline"))

	leftarrow = (-1, -1)
	rightarrow = (-1, -1)
	hdragger = (-1, -1, -1)

	maxoffset = width - (maxx - minx) - 1

	scrollbararray: List[Union[ThemeRef, ThemeString]] = []

	# We only need a scrollbar if we can actually scroll
	if maxoffset > 0:
		scrollbararray += [
			ThemeString(arrowleft, ThemeAttr("main", "scrollbar_arrows")),
		]
		leftarrow = (y, minx)

		scrollbararray += [
			ThemeString("".rjust(maxx - minx - 1, scrollbar), ThemeAttr("main", "scrollbar")),
		]
		scrollbararray += [
			ThemeString(arrowright, ThemeAttr("main", "scrollbar_arrows")),
		]
		rightarrow = (y, maxx)

		curpos = minx + 1 + int((maxx - minx) * (xoffset / (maxoffset)))
		curpos = min(curpos, maxx - 5)

		addthemearray(win, scrollbararray, y = y, x = minx)

		draggerarray: List[Union[ThemeRef, ThemeString]] = [
			ThemeString(f"{horizontaldragger_left}{horizontaldragger_left}", ThemeAttr("main", "dragger")),
			ThemeString(f"{horizontaldragger_midpoint}", ThemeAttr("main", "dragger_midpoint")),
			ThemeString(f"{horizontaldragger_right}{horizontaldragger_right}", ThemeAttr("main", "dragger")),
		]

		addthemearray(win, draggerarray, y = y, x = curpos)
		hdragger = (y, curpos, 5)
	# But we might need to cover up the lack of one if the window has been resized
	else:
		scrollbararray += [
			ThemeString("".rjust(maxx - minx + 1, hline), clear_color),
		]
		addthemearray(win, scrollbararray, y = y, x = minx)

	# (y, x Upper arrow), (y, x Lower arrow), (y, x, len horizontal dragger)
	return leftarrow, rightarrow, hdragger

def generate_heatmap(maxwidth: int, stgroups: List[StatusGroup], selected: int) -> List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Given list[StatusGroup] and an index to the selected item and the max width,
	generate an array of themearrays

		Parameters:
			maxwidth (int): The maximum width of a line
			stgroups (list[StatusGroup]): The status group for each item
			selected (int): The selected item (used to draw the cursor); use -1 to disable cursor
		Returns:
			array (list[ThemeArray]): A list of themearrays
	"""

	array = []
	row: List[Union[ThemeRef, ThemeString]] = []
	block = deep_get(theme, DictPath("boxdrawing#smallblock"), "■")
	selectedblock = deep_get(theme, DictPath("boxdrawing#block"), "█")
	x = 0

	color = color_status_group(stgroups[0])
	tmp = ""

	# Try to make minimise the colour changes
	for i, stgroup in enumerate(stgroups):
		heat = stgroup
		nextcolor = color_status_group(heat)
		if selected == i:
			sblock = selectedblock
		else:
			sblock = block

		if x > maxwidth:
			row.append(ThemeString(tmp, color, False))
			x = 0
			array.append(row)
			row = []

		# If we have a new colour we need a new element in the array,
		# otherwise we just extend the current element
		if x == 0:
			color = nextcolor
			tmp = f"{sblock}"
		elif nextcolor == color:
			tmp += f"{sblock}"
		elif nextcolor != color:
			row.append(ThemeString(tmp, color, False))
			tmp = f"{sblock}"
			color = nextcolor

		x += 1
		if i == len(stgroups) - 1:
			row.append(ThemeString(tmp, color, False))
			array.append(row)
			break

	return array

# pylint: disable-next=too-many-arguments
def percentagebar(win: curses.window, y: int, minx: int, maxx: int, total: int, subsets: List[Tuple[int, ThemeAttr]]) -> curses.window:
	"""
	Draw a bar of multiple subsets that sum up to a total
	FIXME: This should be modified to just return a ThemeArray instead of drawing it

		Parameters:
			win (curses.window): The curses window to operate on
			y (int):  The y-position of the percentage bar
			minx (int): The starting position of the percentage bar
			maxx (int): The ending position of the percentage bar
			total (int): The total sum
			subsets (list(subset, themeattr)):
				subset (int): The fraction of the total that this subset represents
				themeattr (ThemeAttr): The colour to use for this subset
		Returns:
			win (curses.window): The curses window to operate on
	"""

	block = deep_get(theme, DictPath("boxdrawing#smallblock"), "■")
	barwidth = maxx - minx + 1
	barpos = minx + 1

	win.addstr(y, minx, "[")
	ax = barpos
	for subset in subsets:
		rx = 0
		pct, themeattr = subset
		col = themeattr_to_curses_merged(themeattr)
		subsetwidth = int((pct / total) * barwidth)

		while rx < subsetwidth and ax < maxx:
			win.addstr(y, ax, block, col)
			rx += 1
			ax += 1
	while ax < maxx:
		win.addstr(y, ax, " ", col)
		ax += 1
	win.addstr(y, maxx, "]")
	return win

# pylint: disable=unused-argument
def __notification(stdscr: Optional[curses.window], y: int, x: int, message: str, formatting: ThemeAttr) -> curses.window:
	height = 3
	width = 2 + len(message)
	ypos = y - height // 2
	xpos = x - width // 2

	win = curses.newwin(height, width, ypos, xpos)
	col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
	win.attrset(col)
	win.clear()
	win.border()
	win.addstr(1, 1, message, themeattr_to_curses_merged(formatting))
	win.noutrefresh()
	curses.doupdate()
	return win

def notice(stdscr: Optional[curses.window], y: int, x: int, message: str) -> curses.window:
	"""
	Show a notification

		Parameters:
			win (curses.window): The curses window to operate on
			y (int): the y-coordinate of the window centre point
			x (int): the x-coordinate of the window centre point
			message (str): The message to show
		Returns:
			win (curses.window): A reference to the notification window
	"""

	return __notification(stdscr, y, x, message, ThemeAttr("windowwidget", "notice"))

def alert(stdscr: Optional[curses.window], y: int, x: int, message: str) -> curses.window:
	"""
	Show an alert

		Parameters:
			win (curses.window): The curses window to operate on
			y (int): the y-coordinate of the window centre point
			x (int): the x-coordinate of the window centre point
			message (str): The message to show
		Returns:
			win (curses.window): A reference to the notification window
	"""

	return __notification(stdscr, y, x, message, ThemeAttr("windowwidget", "alert"))


# pylint: disable-next=too-many-arguments
def progressbar(win: curses.window, y: int, minx: int, maxx: int, progress: int, title: Optional[str] = None) -> curses.window:
	"""
	A progress bar;
	Usage: Initialise by calling with a reference to a variable set to None
	Pass in progress in 0-100; once done clean up with:
	stdscr.touchwin()
	stdscr.refresh()

		Parameters:
			win (curses.window): The curses window to operate on
			y (int): the y-coordinate
			miny (int): the starting point of the progress bar
			maxy (int): the ending point of the progress bar
			progress (int): 0-100%
			title (str): The title for the progress bar (None for an anonymous window)
		Returns:
			win (curses.window): A reference to the progress bar window
	"""

	width = maxx - minx + 1

	if progress < 0:
		sys.exit("You cannot use a progress bar with negative progress; this is not a regression bar.")
	elif progress > 100:
		sys.exit("That's impossible. No one can give more than 100%. By definition, that is the most anyone can give.")

	if win is None:
		win = curses.newwin(3, width, y, minx)
		col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
		win.attrset(col)
		win.clear()
		win.border()
		col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
		win.bkgd(" ", col)
		if title is not None:
			win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))

	# progress is in % of the total length
	solidblock = deep_get(theme, DictPath("boxdrawing#solidblock"))
	dimmedblock = deep_get(theme, DictPath("boxdrawing#dimmedblock"))
	for x in range(0, width - 2):
		try:
			if x < (width * progress) // 100:
				addthemearray(win, [ThemeString(solidblock, ThemeAttr("main", "progressbar"))], y = 1, x = x + 1)
			else:
				addthemearray(win, [ThemeString(dimmedblock, ThemeAttr("main", "progressbar"))], y = 1, x = x + 1)
		except curses.error:
			curses.endwin()
			ansithemeprint([ANSIThemeString("Critical", "critical"),
					ANSIThemeString(": Live resizing progressbar() is currently broken; this is a known issue.", "default")], stderr = True)
			sys.exit(errno.ENOTSUP)

	win.noutrefresh()
	curses.doupdate()

	return win

def inputwrapper(keypress: int) -> int:
	"""
	A wrapper used by textpads to change the input behaviour of the Escape key

		Parameters:
			keypress (int): The keypress
		Returns:
			keypress (int): The filtered keypress
	"""

	global ignoreinput # pylint: disable=global-statement

	if keypress == 27:	# ESCAPE
		ignoreinput = True
		return 7
	return keypress

# Show a one line high pad the width of the current pad with a border
# and specified title in the middle of the screen
# pylint: disable-next=too-many-arguments,unused-argument
def inputbox(stdscr: curses.window, y: int, x: int, height: int, width: int, title: str) -> str:
	global ignoreinput # pylint: disable=global-statement

	# Show the cursor
	curses.curs_set(True)

	ignoreinput = False

	win = curses.newwin(3, width, y, x)
	col, _discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
	win.attrset(col)
	win.clear()
	win.border()
	win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
	win.noutrefresh()

	inputarea = win.subwin(1, width - 2, y + 1, x + 1)
	inputarea.bkgd(" ", themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
	inputarea.attrset(themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
	inputarea.noutrefresh()

	tpad = curses.textpad.Textbox(inputarea)
	curses.doupdate()

	tpad.edit(inputwrapper)

	if ignoreinput == True:
		string = ""
	else:
		string = tpad.gather()

	del tpad
	del win

	# Hide the cursor
	curses.curs_set(False)
	stdscr.touchwin()
	stdscr.noutrefresh()
	curses.doupdate()

	return string.rstrip()

# Show a confirmation box centered around y and x
# with the specified default value and title
def confirmationbox(stdscr: curses.window, y: int, x: int, title: str = "", default: bool = False) -> bool:
	global ignoreinput # pylint: disable=global-statement

	ignoreinput = False
	retval = default

	default_option = "Y/n" if default else "y/N"
	question = f"Are you sure [{default_option}]: "
	height = 3
	width = 2 + max(len(question), len(title))
	ypos = y - height // 2
	xpos = x - width // 2

	win = curses.newwin(height, width, ypos, xpos)
	col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
	win.attrset(col)
	win.clear()
	win.border()
	win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
	win.addstr(1, 1, question.ljust(width - 2), themeattr_to_curses_merged(ThemeAttr("windowwidget", "default")))
	win.noutrefresh()
	curses.doupdate()

	while True:
		stdscr.timeout(100)
		c = stdscr.getch()
		if c == 27:	# ESCAPE
			break

		if c == ord(""):
			curses.endwin()
			sys.exit()

		if c in (curses.KEY_ENTER, 10, 13):
			break

		if c in (ord("y"), ord("Y")):
			retval = True
			break

		if c in (ord("n"), ord("N")):
			retval = False
			break

	del win
	stdscr.touchwin()
	stdscr.noutrefresh()
	curses.doupdate()

	return retval

# pylint: disable-next=too-many-arguments,unused-argument
def move_cur_with_offset(curypos: int, listlen: int, yoffset: int,
			 maxcurypos: int, maxyoffset: int, movement: int, wraparound: bool = False) -> Tuple[int, int]:
	newcurypos = curypos + movement
	newyoffset = yoffset

	# If we are being asked to move forward but we are already
	# at the end of the list, it is prudent not to move,
	# even if the caller so requests.
	# It is just good manners, really; likewise if we are being asked to move
	# backward past the start of the list.
	#
	# One may gracefully accept the request if so instructed using the wraparound flag, though.
	if movement > 0:
		if newcurypos > maxcurypos:
			if newyoffset == maxyoffset and wraparound == True:
				newcurypos = 0
				newyoffset = 0
			else:
				newcurypos = maxcurypos
				newyoffset = min(yoffset + movement - (maxcurypos - curypos), maxyoffset)
	elif movement < 0:
		if newcurypos < 0:
			if (yoffset + curypos) + newcurypos < 0 and wraparound == True:
				newcurypos = maxcurypos
				newyoffset = maxyoffset
			else:
				newcurypos = 0
				newyoffset = max(yoffset + movement + curypos, 0)
	return newcurypos, newyoffset

def addthemearray(win: curses.window, array: List[Union[ThemeRef, ThemeString]], y: int = -1, x: int = -1, selected: Optional[bool] = None) -> Tuple[int, int]:
	"""
	Add a ThemeArray to a curses window

		Parameters:
			win (curses.window): The curses window to operate on
			array (list[union[ThemeRef, ThemeString]]): The themearray to add to the curses window
			y (int): The y-coordinate (-1 to start from current cursor position)
			x (int): The x-coordinate (-1 to start from current cursor position)
			selected (bool): Should the selected version of the ThemeArray be used
		Returns:
			(y, x):
				y (int): The new y-coordinate
				x (int): The new x-coordinate
	"""

	for item in themearray_flatten(array):
		string, attr = themestring_to_cursestuple(item)
		# If there still are remaining <NUL> occurences, replace them
		string = string.replace("\x00", "<NUL>")
		try:
			win.addstr(y, x, string, attr)
		except curses.error:
			pass
		y, x = win.getyx()
	return y, x

class WidgetLineAttrs(IntFlag):
	"""
	Special properties used by lines in windowwidgets
	"""

	NORMAL = 0		# No specific attributes
	SEPARATOR = 1		# Separators start a new category; they are not selectable
	DISABLED = 2		# Disabled items are not selectable, but are not treated as a new category
	UNSELECTABLE = 4	# Unselectable items are not selectable, but are not skipped when navigating
	INVALID = 8		# Invalid items are not selectable; to be used for parse error etc.

# This extracts the string without formatting;
# once everything uses proper ThemeArray this wo not be necessary anymore
def themearray_to_string(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeString]]]) -> str:
	"""
	Given a themearray (either a true ThemeArray or List[Union[ThemeRef, ThemeString]],
	return an unformatted string

		Parameters:
			themearray (ThemeArray): A themearray
		Returns:
			string (str): The unformatted string
	"""

	string = ""

	if isinstance(themearray, ThemeArray):
		return str(themearray)

	for fragment in themearray:
		string += str(fragment)

	return string

def themearray_truncate(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeString]]], max_len: int) -> Union[ThemeArray, List[Union[ThemeRef, ThemeString]]]:
	output_format = type(themearray)
	truncated_themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeString]]] = []

	# For the time being (until we implement proper iteration over ThemeArray elements) this is needed
	if isinstance(themearray, ThemeArray):
		themearray = themearray.to_list()

	# To be able to truncate a themearray that can contain themerefs we need to flatten the array
	# (replace the themerefs with the corresponding themearray) first
	themearray_flattened = themearray_flatten(themearray)

	for element in themearray_flattened:
		max_element_len = max_len - themearray_len(truncated_themearray)
		if len(element) > max_element_len:
			string = str(element)
			attr = element.get_themeattr()
			selected = element.get_selected()
			truncated_themearray.append(ThemeString(string[0:max_element_len], attr, selected = selected))
			break
		else:
			truncated_themearray.append(element)

	if output_format == ThemeArray:
		truncated_themearray = ThemeArray(cast(List[Union[ThemeRef, ThemeString]], truncated_themearray))

	return truncated_themearray

def themearray_len(themearray: Union[ThemeArray, List[Union[ThemeRef, ThemeString]]]) -> int:
	"""
	Given a themearray (either a true ThemeArray or List[Union[ThemeRef, ThemeString]],
	return its length

		Parameters:
			themearray (ThemeArray): A themearray
		Returns:
			len (int): The length of the unformatted string
	"""
	return len(themearray_to_string(themearray))

def themeattr_to_curses(themeattr: ThemeAttr, selected: bool = False) -> Tuple[int, int]:
	"""
	Given a themeattr returns a tuple with curses color + curses attributes

		Parameters:
			themeattr (ThemeAttr): The ThemeAttr to convert
			selected (bool): [optional] True is selected, False otherwise
		Returns:
			(curses_col, curses_attrs):
				curses_col (int): A curses color
				curses_attrs (int): Curses attributes
	"""

	context, key = themeattr
	tmp_attr = deep_get(theme, DictPath(f"{context}#{key}"))

	if tmp_attr is None:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("Could not find the tuple (", "default"),
				 ANSIThemeString(f"{context}", "emphasis"),
				 ANSIThemeString(", ", "default"),
				 ANSIThemeString(f"{key}", "emphasis"),
				 ANSIThemeString(") in theme.", "default")],
				[ANSIThemeString("Using (", "default"),
				 ANSIThemeString("main", "emphasis"),
				 ANSIThemeString(", ", "default"),
				 ANSIThemeString("default", "emphasis"),
				 ANSIThemeString(") as fallback.", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		tmp_attr = deep_get(theme, DictPath("main#default"))

	if isinstance(tmp_attr, dict):
		if selected == True:
			attr = tmp_attr["selected"]
		else:
			attr = tmp_attr["unselected"]
	else:
		attr = tmp_attr

	if isinstance(attr, list):
		col, attr = attr
	else:
		col = attr
		attr = "normal"

	if isinstance(attr, str):
		attr = [attr]
	else:
		attr = list(attr)

	tmp = 0

	for item in attr:
		if not isinstance(item, str):
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("Invalid text attribute used in theme; attribute has to be a string and one of:", "default")],
					[ANSIThemeString("“", "default"),
					 ANSIThemeString("dim", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("normal", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("bold", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("underline", "emphasis"),
					 ANSIThemeString("“.", "default")],
					[ANSIThemeString("Using “", "default"),
					 ANSIThemeString("normal", "emphasis"),
					 ANSIThemeString("“ as fallback.", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
		if item == "dim":
			tmp |= curses.A_DIM
		elif item == "normal":
			tmp |= curses.A_NORMAL
		elif item == "bold":
			tmp |= curses.A_BOLD
		elif item == "underline":
			tmp |= curses.A_UNDERLINE
		else:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("Invalid text attribute “", "default"),
					 ANSIThemeString(f"{item}", "emphasis"),
					 ANSIThemeString("“ used in theme; attribute has to be one of:", "default")],
					[ANSIThemeString("“", "default"),
					 ANSIThemeString("dim", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("normal", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("bold", "emphasis"),
					 ANSIThemeString("“, “", "default"),
					 ANSIThemeString("underline", "emphasis"),
					 ANSIThemeString("“.", "default")],
					[ANSIThemeString("Using “", "default"),
					 ANSIThemeString("normal", "emphasis"),
					 ANSIThemeString("“ as fallback.", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			tmp |= curses.A_NORMAL
	curses_attrs = tmp

	curses_col = __color[col][selected]
	if curses_col is None:
		CMTLog(CMTLogType.DEBUG, [
				[ANSIThemeString("themeattr_to_curses()", "emphasis")],
				[ANSIThemeString("called with non-existing (color, selected) tuple ", "error")],
				[ANSIThemeString(f"{col}", "argument")],
				[ANSIThemeString(", ", "error")],
				[ANSIThemeString(f"{selected}", "argument")],
				[ANSIThemeString(").", "error")],
				[ANSIThemeString("Backtrace:", "error")],
				[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
		       ], severity = LogLevel.ERR, facility = str(themefile))
		raise KeyError(f"themeattr_to_curses: (color: {col}, selected: {selected}) not found")
	return curses_col, curses_attrs

def themeattr_to_curses_merged(themeattr: ThemeAttr, selected: bool = False) -> int:
	"""
	Given a themeattr returns merged curses color + curses attributes

		Parameters:
			themeattr (ThemeAttr): The ThemeAttr to convert
			selected (bool): [optional] True is selected, False otherwise
		Returns:
			curses_attrs (int): Curses color | attrs
	"""

	curses_col, curses_attrs = themeattr_to_curses(themeattr, selected)
	return curses_col | curses_attrs

def themestring_to_cursestuple(themestring: ThemeString, selected: Optional[bool] = None) -> Tuple[str, int]:
	"""
	Given a themestring returns a cursestuple

		Parameters:
			themestring (ThemeString): The ThemeString to convert
			selected (bool): [optional] True is selected, False otherwise
		Returns:
			cursestuple (str, int): A curses tuple for use with addformattedarray()
	"""

	string = str(themestring)
	themeattr = themestring.get_themeattr()

	if selected is None:
		selected = themestring.get_selected()
		if selected is None:
			selected = False

	return (string, themeattr_to_curses_merged(themeattr, selected))

def themearray_flatten(themearray: List[Union[ThemeRef, ThemeString]], selected: Optional[bool] = None) -> List[ThemeString]:
	"""
	Replace all ThemeRefs in a ThemeArray with ThemeString

		Parameters:
			themearray (ThemeArray): The themearray to flatten
			selected (bool): [optional] True is selected, False otherwise
		Returns:
			themearray_flattened (ThemeArray): The flattened themearray
	"""

	themearray_flattened = []

	for substring in themearray:
		if isinstance(substring, ThemeString):
			themearray_flattened.append(substring)
		elif isinstance(substring, ThemeRef):
			themearray_flattened += substring.to_themearray()
		else:
			CMTLog(CMTLogType.DEBUG, [
					[ANSIThemeString("themearray_flatten()", "emphasis"),
					 ANSIThemeString(" called with invalid type ", "error"),
					 ANSIThemeString(f"{type(substring)}", "argument"),
					 ANSIThemeString("; substring:", "error")],
					[ANSIThemeString(f"{substring}", "default")],
					[ANSIThemeString("Backtrace:", "error")],
					[ANSIThemeString(f"{''.join(traceback.format_stack())}", "default")],
			       ], severity = LogLevel.ERR, facility = str(themefile))
			raise TypeError(f"themearray_flatten() called with invalid type {type(substring)}")
	return themearray_flattened

def themearray_wrap_line(themearray: List[Union[ThemeRef, ThemeString]], maxwidth: int = -1, wrap_marker: bool = True, selected: Optional[bool] = None) ->\
				List[List[Union[ThemeRef, ThemeString]]]:
	"""
	Given a themearray, split it into multiple lines, each maxwidth long

		Parameters:
			themearray (ThemeArray): The themearray to wrap
			maxwidth (int): The maximum number of characters before wrapping
			wrap_marker (bool): Should the line end in a wrap marker?
			selected (bool): Should the line(s) be selected?
		Returns:
			themearrays (list[ThemeArray]): A list of themearrays
	"""

	if maxwidth == -1:
		return [themearray]

	themearray_flattened = themearray_flatten(themearray, selected = selected)

	linebreak = ThemeRef("separators", "line_break").to_themearray()

	if wrap_marker == True:
		linebreaklen = len(linebreak)
	else:
		linebreaklen = 0

	themearrays: List[List[Union[ThemeRef, ThemeString]]] = []
	tmp_themearray: List[Union[ThemeRef, ThemeString]] = []
	tmplen = 0
	i = 0

	while True:
		# Does the fragment fit?
		tfilen = len(themearray_flattened[i])
		if tmplen + tfilen < maxwidth:
			tmp_themearray.append(themearray_flattened[i])
			tmplen += tfilen
			i += 1
		# Nope
		else:
			string = str(themearray_flattened[i])
			themeattr = themearray_flattened[i].get_themeattr()

			tmp_themearray.append(ThemeString(string[:maxwidth - linebreaklen - tmplen], themeattr))
			if wrap_marker == True:
				tmp_themearray += linebreak
			themearray_flattened[i] = ThemeString(string[maxwidth - linebreaklen - tmplen:], themeattr)
			themearrays.append(tmp_themearray)
			tmp_themearray = []
			tmplen = 0
			continue
		if i == len(themearray_flattened):
			themearrays.append(tmp_themearray)
			break

	return themearrays

ignoreinput = False

# A generic window widget
# items is a list of tuples, like so:
# (widgetlineattr, strarray, strarray, ...)
# A strarray is a list of tuples, where every tuple is of the format (string, attribute)
# Alternatively items can be a list of dicts
# on the format:
# {
#	"lineattrs": ...,
#	"columns": strarray, ...,
#	"retval": the value to return if this item is selected (any type is allowed)
# }
# pylint: disable-next=too-many-arguments,line-too-long
def windowwidget(stdscr: curses.window, maxy: int, maxx: int, y: int, x: int,
		 items, headers = None, title: str = "", preselection: Union[str, Set[int]] = "",
		 cursor: bool = True, taggable: bool = False, confirm: bool = False, confirm_buttons = None, **kwargs):
	stdscr.refresh()
	global ignoreinput # pylint: disable=global-statement
	ignoreinput = False

	padwidth = 2
	listpadheight = len(items)

	if confirm_buttons is None:
		confirm_buttons = []

	if isinstance(items[0], tuple):
		# This is used by the About text
		if isinstance(items[0][0], int):
			tmpitems = []
			for item in items:
				tmpitems.append({
					"lineattrs": item[0],
					"columns": list(item[1:]),
					"retval": None,
				})
			items = tmpitems
		else:
			raise ValueError(f"The text passed to windowwidget() is of invalid format:\n\n{items}")

	columns = len(items[0]["columns"])
	lengths = [0] * columns

	if headers is not None:
		if len(headers) != columns:
			raise ValueError(f"Mismatch: Number of headers passed to windowwidget ({len(headers)}) does not match number of columns ({columns})")

		for i in range(0, columns):
			lengths[i] = len(headers[i])

	tagprefix = str(ThemeRef("separators", "tag"))

	# Leave room for a tag prefix column if needed
	if taggable == True:
		tagprefixlen = len(tagprefix)
	else:
		tagprefixlen = 0

	# Every item is a line
	for item in items:
		for i in range(0, columns):
			length = themearray_len(item["columns"][i])
			lengths[i] = max(lengths[i], length)

	listpadwidth = 0
	for i in range(0, columns):
		if i > 0:
			listpadwidth += padwidth
		listpadwidth += lengths[i]

	if len(title) > listpadwidth:
		lengths[columns - 1] += len(title) - listpadwidth

	listpadwidth = max(listpadwidth, len(title)) + tagprefixlen

	extra_height = 0

	if headers is not None:
		extra_height += 2
	if confirm == True:
		extra_height += 2

	height = min(maxy - 5, listpadheight) + 2 + extra_height
	maxcurypos = min(height - 3 - extra_height, listpadheight - 1)
	maxyoffset = listpadheight - (height - 2 - extra_height)
	width = min(maxx - 5, listpadwidth) + 2
	button_lengths = 0
	if confirm == True:
		for button in confirm_buttons[1:]:
			for string, _ in button:
				button_lengths += len(string)
		button_lengths += len(confirm_buttons) - 2
		width = max(button_lengths, width)

	xoffset = 0
	maxxoffset = listpadwidth - (width - 2)

	yoffset = 0

	ypos = y - height // 2
	xpos = x - width // 2

	if headers is not None:
		headerpadypos = ypos + 1
		listpadypos = ypos + 3
		scrollbarypos = 3
	else:
		listpadypos = ypos + 1
		scrollbarypos = 1

	if confirm == True:
		buttonpadypos = ypos + height - 2

	win = curses.newwin(height, width, ypos, xpos)
	col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "boxdrawing"))
	win.attrset(col)
	win.clear()
	win.border()
	col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
	win.bkgd(" ", col)
	win.addstr(0, 1, title, themeattr_to_curses_merged(ThemeAttr("windowwidget", "title")))
	listpad = curses.newpad(listpadheight + 1, listpadwidth + 1)
	col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "default"))
	listpad.bkgd(" ", col)

	if headers is not None:
		headerpad = curses.newpad(1, listpadwidth + 1)
		col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
		headerpad.bkgd(" ", col)

	if confirm == True:
		buttonpad = curses.newpad(1, listpadwidth + 1)
		col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
		headerpad.bkgd(" ", col)

	selection: Union[int, str, None] = None
	curypos = 0

	headerarray: List[Union[ThemeRef, ThemeString]] = []

	# Generate headers
	if headers is not None:
		if taggable == True:
			headerarray.append(ThemeString(f"{tagprefix}", ThemeAttr("windowwidget", "highlight")))
		for i in range(0, columns):
			extrapad = padwidth
			if i == columns - 1:
				extrapad = 0
			headerarray.append(ThemeString((headers[i].ljust(lengths[i] + extrapad)), ThemeAttr("windowwidget", "header")))

	# Move to preselection
	if isinstance(preselection, str):
		if preselection != "":
			for _y, item in enumerate(items):
				if isinstance(item["columns"][0][0], ThemeString):
					tmp_selection = str(item["columns"][0][0])
				else:
					tmp_selection = item["columns"][0][0][0]

				if "retval" in item and item["retval"] == preselection or "retval" not in item and tmp_selection == preselection:
					curypos, yoffset = move_cur_with_offset(0, height, yoffset, maxcurypos, maxyoffset, _y)
					break
		tagged_items = set()
	elif isinstance(preselection, set):
		tagged_items = preselection
	else:
		raise ValueError(f"is_taggable() == True, but type(preselection) == {type(preselection)} (must be str or set())")

	while selection is None:
		for _y, item in enumerate(items):
			if cursor == True:
				# These parentheses helps readability
				# pylint: disable-next=superfluous-parens
				_selected = (yoffset + curypos == _y)
			else:
				_selected = False

			lineattributes = item["lineattrs"]
			linearray: List[Union[ThemeRef, ThemeString]] = []

			if taggable == True:
				if _y in tagged_items:
					linearray.append(ThemeString(f"{tagprefix}", ThemeAttr("windowwidget", "tag")))
				else:
					linearray.append(ThemeString("".ljust(tagprefixlen), ThemeAttr("windowwidget", "tag")))

			for _x, column in enumerate(item["columns"]):
				themearray: List[Union[ThemeRef, ThemeString]] = []
				length = 0

				for string in column:
					if isinstance(string, ThemeString):
						tmpstring = str(string)
						attribute = string.themeattr
					else:
						raise ProgrammingError(f"In windowwidget(); we want to get rid of this: items={items}")
						#tmpstring = string[0]
						#attribute = string[1]
					strlen = len(tmpstring)
					length += strlen

					if lineattributes & (WidgetLineAttrs.INVALID) != 0:
						attribute = ThemeAttr("windowwidget", "alert")
						themearray.append(ThemeString(tmpstring, attribute, _selected))
					elif lineattributes & (WidgetLineAttrs.DISABLED | WidgetLineAttrs.UNSELECTABLE) != 0:
						attribute = ThemeAttr("windowwidget", "dim")
						themearray.append(ThemeString(tmpstring, attribute, _selected))
					elif lineattributes & WidgetLineAttrs.SEPARATOR != 0:
						if attribute == ThemeAttr("windowwidget", "default"):
							attribute = ThemeAttr("windowwidget", "highlight")
						tpad = listpadwidth - strlen
						lpad = int(tpad / 2)
						rpad = tpad - lpad
						lpadstr = "".ljust(lpad, "─")
						rpadstr = "".rjust(rpad, "─")

						themearray.append(ThemeString(lpadstr, ThemeAttr("windowwidget", "highlight"), _selected))
						themearray.append(ThemeString(tmpstring, attribute, _selected))
						themearray.append(ThemeString(rpadstr, ThemeAttr("windowwidget", "highlight"), _selected))
					else:
						themearray.append(ThemeString(tmpstring, attribute, _selected))



				if lineattributes & WidgetLineAttrs.SEPARATOR == 0:
					padstring = "".ljust(lengths[_x] - length + padwidth)
					themearray.append(ThemeString(padstring, attribute, _selected))

				linearray += themearray

			addthemearray(listpad, linearray, y = _y, x = 0)

		# pylint: disable-next=line-too-long
		_upperarrow, _lowerarrow, _vdragger = scrollbar_vertical(win, width - 1, scrollbarypos, height - 2, listpadheight, yoffset, ThemeAttr("windowwidget", "boxdrawing"))
		# pylint: disable-next=line-too-long
		_leftarrow, _rightarrow, _hdragger = scrollbar_horizontal(win, height - 1, 1, width - 2, listpadwidth, xoffset, ThemeAttr("windowwidget", "boxdrawing"))

		if headers is not None:
			addthemearray(headerpad, headerarray, y = 0, x = 0)
			headerxoffset = 0
			if len(headers) > 0:
				headerxoffset = xoffset
			headerpad.noutrefresh(0, headerxoffset, headerpadypos, xpos + 1, headerpadypos, xpos + width - 2)
			window_tee_hline(win, 2, 0, width - 1, ThemeAttr("windowwidget", "boxdrawing"))

		listpad.noutrefresh(yoffset, xoffset, listpadypos, xpos + 1, ypos + height - 2, xpos + width - 2)

		if confirm == True:
			x = width - button_lengths - 2
			col, __discard = themeattr_to_curses(ThemeAttr("windowwidget", "header"))
			buttonpad.bkgd(" ", col)
			for button in confirm_buttons[1:]:
				_, x = addthemearray(buttonpad, button, y = 0, x = x)
				x += 1
			buttonpad.noutrefresh(0, 0, buttonpadypos, xpos + 1, buttonpadypos, xpos + width - 2)
			window_tee_hline(win, height - 3, 0, width - 1, ThemeAttr("windowwidget", "boxdrawing"))

		win.noutrefresh()
		curses.doupdate()

		stdscr.timeout(100)
		oldcurypos = curypos
		oldyoffset = yoffset

		c = stdscr.getch()
		if c == curses.KEY_RESIZE:
			curses.endwin()
			ansithemeprint([ANSIThemeString("Critical", "critical"),
					ANSIThemeString(": Live resizing windowwidget() is currently broken; this is a known issue.", "default")], stderr = True)
			sys.exit(errno.ENOTSUP)
		if c == 27:	# ESCAPE
			selection = ""
			confirm_press = c
			break
		elif c == ord(""):
			curses.endwin()
			sys.exit()
		elif deep_get(kwargs, DictPath("KEY_F6"), False) == True and c == curses.KEY_F6:
			# This is used to toggle categorised list on/off
			selection = -c
			break
		elif taggable == True and c == ord(" "):
			if curypos + yoffset in tagged_items:
				tagged_items.discard(curypos + yoffset)
			else:
				tagged_items.add(curypos + yoffset)
		elif ord("a") <= c <= ord("z") and cursor == True and confirm == False:
			# Find the next entry starting with the pressed letter; wrap around if the bottom is hit
			# stop if oldycurypos + oldyoffset is hit
			while True:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1, wraparound = True)
				lineattributes = items[yoffset + curypos]["lineattrs"]
				tmp_char = str(items[yoffset + curypos]["columns"][0][0])[0]
				if tmp_char.lower() == chr(c).lower() and lineattributes & WidgetLineAttrs.DISABLED == 0:
					break
				if (curypos + yoffset) == (oldcurypos + oldyoffset):
					# While we are at the same position in the list we might not be at the same offsets
					curypos = oldcurypos
					yoffset = oldyoffset
					break
		elif ord("A") <= c <= ord("Z") and cursor == True and confirm == False:
			# Find the previous entry starting with the pressed letter; wrap around if the top is hit
			# stop if oldycurypos + oldyoffset is hit
			while True:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1, wraparound = True)
				lineattributes = items[yoffset + curypos]["lineattrs"]
				tmp_char = str(items[yoffset + curypos]["columns"][0][0])[0]
				if tmp_char.lower() == chr(c).lower() and lineattributes & WidgetLineAttrs.DISABLED == 0:
					break
				if (curypos + yoffset) == (oldcurypos + oldyoffset):
					# While we are at the same position in the list we might not be at the same offsets
					curypos = oldcurypos
					yoffset = oldyoffset
					break
		elif c == ord("\t") and cursor == True:
			# Find next group
			while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR == 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (curypos + yoffset) == (maxcurypos + maxyoffset):
					break
				# OK, we found a group, now find the first not-group
			while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (curypos + yoffset) == (maxcurypos + maxyoffset):
					break
		elif c == curses.KEY_BTAB and cursor == True:
			# Find previous group
			while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR == 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (curypos + yoffset) == 0:
					break
			# OK, we found a group, now find the previous not-group
			while items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (curypos + yoffset) == 0:
					break
			# Finally find the first entry in that group
			while (curypos + yoffset) > 0 and items[yoffset + curypos]["lineattrs"] & WidgetLineAttrs.SEPARATOR != 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (curypos + yoffset) == 0:
					break
		elif c == curses.KEY_UP:
			curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
		elif c == curses.KEY_DOWN:
			curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
		elif c == curses.KEY_LEFT:
			xoffset = max(xoffset - 1, 0)
		elif c == curses.KEY_RIGHT:
			xoffset = min(xoffset + 1, maxxoffset)
		elif c == curses.KEY_HOME:
			xoffset = 0
		elif c == curses.KEY_END:
			xoffset = maxxoffset
		elif c == curses.KEY_SHOME:
			curypos = 0
			yoffset = 0
		elif c == curses.KEY_SEND:
			curypos = maxcurypos
			yoffset = maxyoffset
		elif c == curses.KEY_PPAGE:
			curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -10)
		elif c == curses.KEY_NPAGE:
			curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +10)
		elif c in (curses.KEY_ENTER, 10, 13) and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.UNSELECTABLE) == 0 and confirm == False:
			if deep_get(items[yoffset + curypos], DictPath("retval")) is None:
				selection = items[yoffset + curypos]["columns"]
			else:
				selection = items[yoffset + curypos]["retval"]
			break
		elif confirm == True and c in confirm_buttons[0]:
			confirm_press = c
			break

		# These only apply if we use a cursor
		if cursor == True:
			# Find the last acceptable line
			if (yoffset + curypos) == (maxcurypos + maxyoffset):
				while items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
			# We tried moving backwards; do we need to go farther?
			if (yoffset + curypos) > (oldyoffset + oldcurypos):
				while (yoffset + curypos) < len(items) and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (yoffset + curypos) == len(items) and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					yoffset = oldyoffset
					curypos = oldcurypos
			# Find the first acceptable line
			elif (yoffset + curypos) == 0:
				while items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
			# We tried moving backwards; do we need to go farther?
			elif (yoffset + curypos) < (oldyoffset + oldcurypos):
				while (yoffset + curypos) > 0 and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (yoffset + curypos) == 0 and items[yoffset + curypos]["lineattrs"] & (WidgetLineAttrs.SEPARATOR | WidgetLineAttrs.DISABLED) != 0:
					curypos = oldcurypos + oldyoffset
					yoffset = 0

		if cursor == False:
			yoffset += curypos
			yoffset = min(maxyoffset, yoffset)
			curypos = 0

	del listpad
	del win

	if taggable == True:
		return tagged_items

	if confirm == True:
		return (confirm_press, selection)

	return selection

label_headers = ["Label:", "Value:"]

def get_labels(labels: Optional[Dict]) -> Optional[List[Dict]]:
	"""
	Get labels

		Parameters:
			labels (dict): A dict
		Returns:
			None if no labels are found, list[(WidgetLineAttrs, themestr, themestr)] if labels are found
	"""

	if labels is None:
		return None

	rlabels = []
	for key, value in labels.items():
		rlabels.append({
			"lineattrs": WidgetLineAttrs.NORMAL,
			"columns": [[ThemeString(key, ThemeAttr("windowwidget", "highlight"))], [ThemeString(value.replace("\n", "\\n"), ThemeAttr("windowwidget", "default"))]],
			"retval": None,
		})
	return rlabels

annotation_headers = ["Annotation:", "Value:"]

def get_annotations(annotations: Optional[Dict]) -> Optional[List[Dict]]:
	"""
	Get annotations

		Parameters:
			annotations (dict): A dict
		Returns:
			None if no labels are found, list[(WidgetLineAttrs, themestr, themestr)] if annotations are found
	"""

	return get_labels(annotations)

# pylint: disable-next=too-many-instance-attributes,too-many-public-methods
class UIProps:
	"""
	The class used for the UI
	"""

	def __init__(self, stdscr: curses.window) -> None:
		self.stdscr: curses.window = stdscr

		# Helptext
		self.helptext = None

		# Info to use for populating lists, etc.
		self.sorted_list: List[Type] = []
		self.sortorder_reverse = False

		# Used for searching
		self.searchkey = ""

		# Used for label list
		self.labels: Optional[List[Dict]] = None

		# Used for annotation list
		self.annotations: Optional[List[Dict]] = None

		# Reference to the external color class
		self.miny = 0
		self.maxy = 0
		self.minx = 0
		self.maxx = 0
		self.mincurypos = 0
		self.maxcurypos = 0
		self.curypos = 0
		self.yoffset = 0
		self.xoffset = 0
		self.maxyoffset = 0
		self.maxxoffset = 0
		# -1 -- Do not update
		# 0 -- Update
		# > 0 -- Count this down to 0 before updating
		self.update_count = 0
		# Count to use for update countdowns; only used if update_count > 0
		self.update_delay = 0
		# Update will update the content to display,
		# Refresh just updates the display
		self.refresh = True
		self.sortcolumn = ""
		self.sortkey1 = ""
		self.sortkey2 = ""
		self.field_list: Dict = {}

		self.helpstring = "[F1] / [Shift] + H: Help"
		# Should there be a timestamp in the upper right corner?
		self.timestamp = True

		self.selected: Union[None, Type] = None

		# For generic information
		self.infopadminwidth = 0
		self.infopadypos = 0
		self.infopadxpos = 0
		self.infopadheight = 0
		self.infopadwidth = 0
		self.infopad: Optional[curses.window] = None
		# For lists
		self.headerpadminwidth = 0
		self.headerpadypos = 0
		self.headerpadxpos = 0
		self.headerpadheight = 0
		self.headerpadwidth = 0
		self.headerpad: Optional[curses.window] = None
		self.listlen: int = 0
		# This one really is a misnomer and could possible be confused with the infopad
		self.sort_triggered = False
		self.regenerate_list = False
		self.info: List[Type] = []
		# This is a list of the xoffset for all headers in listviews
		self.tabstops: List[int] = []
		self.listpadypos = 0
		self.listpadxpos = 0
		self.listpadheight = 0
		self.listpadwidth = 0
		self.listpad: Optional[curses.window] = None
		self.listpadminwidth = 0
		self.reversible = True
		# For logs with a timestamp column
		self.tspadypos = 0
		self.tspadxpos = 0
		self.tspadheight = 0
		self.tspadwidth = len("YYYY-MM-DD HH:MM:SS")
		self.tspad: Optional[curses.window] = None
		self.borders = True
		self.logpadypos = 0
		self.logpadxpos = 0
		self.logpadheight = 0
		self.logpadwidth = 0
		self.logpad: Optional[curses.window] = None
		self.loglen = 0
		self.logpadminwidth = 0
		self.statusbar: Optional[curses.window] = None
		self.statusbarypos: int = 0
		self.continuous_log = False
		self.match_index: Optional[int] = None
		self.search_matches: Set[int] = set()
		self.timestamps: Optional[List[datetime]] = None
		self.facilities: Optional[List[str]] = None
		self.severities: Optional[List[LogLevel]] = None
		self.messages: Optional[List[str]] = None
		# For checking clicks/drags of the scrollbars
		self.leftarrow = -1, -1
		self.rightarrow = -1, -1
		self.hdragger = -1, -1, -1
		self.upperarrow = -1, -1
		self.lowerarrow = -1, -1
		self.vdragger = -1, -1, -1

		# Function handler for <enter> / <double-click>
		self.activatedfun = None
		self.on_activation: Dict = {}
		self.extraref = None
		self.data = None

		self.windowheader: str = ""
		self.view = ""

	def __del__(self) -> None:
		if self.infopad is not None:
			del self.infopad
		if self.listpad is not None:
			del self.listpad
		if self.headerpad is not None:
			del self.headerpad
		if self.logpad is not None:
			del self.logpad

	def update_sorted_list(self) -> None:
		if self.sort_triggered == False:
			return
		self.sort_triggered = False
		self.list_needs_regeneration(True)
		self.yoffset = 0
		self.curypos = 0

		sortkey1, sortkey2 = self.get_sortkeys()
		try:
			self.sorted_list = natsorted(self.info, key = attrgetter(sortkey1, sortkey2), reverse = self.sortorder_reverse)
		except TypeError:
			# We could not sort the list; we should log and just keep the current sort order
			pass

	def update_info(self, info: List[Type]) -> int:
		self.info = info
		self.listlen = len(self.info)
		self.sort_triggered = True

		return self.listlen

	def update_log_info(self, timestamps: Optional[List[datetime]],
			    facilities: Optional[List[str]], severities: Optional[List[LogLevel]], messages: Optional[List[str]]) -> None:
		self.timestamps = timestamps
		self.facilities = facilities
		self.severities = severities
		self.messages = messages

	def set_update_delay(self, delay: int) -> None:
		self.update_delay = delay

	def force_update(self) -> None:
		self.update_count = 0
		self.refresh = True
		self.sort_triggered = True
		self.list_needs_regeneration(True)

	def force_refresh(self) -> None:
		self.list_needs_regeneration(True)
		self.refresh_all()
		self.refresh_window()
		self.update_window()

	def disable_update(self) -> None:
		self.update_count = -1

	def reset_update_delay(self) -> None:
		self.update_count = self.update_delay

	def countdown_to_update(self) -> None:
		if self.update_count > 0:
			self.update_count -= 1

	def is_update_triggered(self) -> bool:
		return self.update_count == 0

	def list_needs_regeneration(self, regenerate_list: bool) -> None:
		self.regenerate_list = regenerate_list

	def is_list_regenerated(self) -> bool:
		return self.regenerate_list != True

	def select(self, selection: Union[None, Type]) -> None:
		self.selected = selection

	def select_if_y(self, y: int, selection: Type) -> None:
		if self.yoffset + self.curypos == y:
			self.select(selection)

	def is_selected(self, selected: Union[None, Type]) -> bool:
		if selected is None:
			return False

		return self.selected == selected

	def get_selected(self) -> Union[None, Type]:
		return self.selected

	# Default behaviour:
	# timestamps enabled, no automatic updates, default sortcolumn = "status"
	# pylint: disable-next=too-many-arguments
	def init_window(self, field_list: Dict, view = None, windowheader: str = "",
			update_delay: int = -1, sortcolumn: str = "status", sortorder_reverse: bool = False, reversible: bool = True,
			helptext = None, activatedfun = None, on_activation = None, extraref = None, data = None) -> None:
		self.field_list = field_list
		self.searchkey = ""
		self.sortcolumn = sortcolumn
		self.sortorder_reverse = sortorder_reverse
		self.reversible = reversible
		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.set_update_delay(update_delay)
		self.view = view

		self.resize_window()

		self.windowheader = windowheader
		self.headerpad = None
		self.listpad = None
		self.infopad = None
		self.tspad = None
		self.borders = True
		self.logpad = None
		self.helptext = helptext

		if on_activation is None:
			on_activation = {}

		self.activatedfun = activatedfun
		self.on_activation = on_activation
		self.extraref = extraref
		self.data = data

	def reinit_window(self, field_list: Dict, sortcolumn: str) -> None:
		self.field_list = field_list
		self.searchkey = ""
		self.sortcolumn = sortcolumn
		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.resize_window()

	def update_window(self) -> None:
		hline = deep_get(theme, DictPath("boxdrawing#hline"))

		maxyx = self.stdscr.getmaxyx()
		if self.maxy != (maxyx[0] - 1) or self.maxx != (maxyx[1] - 1):
			self.resize_window()
		self.stdscr.erase()
		self.stdscr.border()
		# If we do not have sideborders we need to clear the right border we just painted,
		# just in case the content of the logpad is not wide enough to cover it
		if self.borders == False:
			for y in range(self.logpadypos, self.maxy - 1):
				self.addthemearray(self.stdscr, [ThemeString(" ", ThemeAttr("main", "default"))], y = y, x = self.maxx)

		self.draw_winheader()
		self.update_timestamp(0, self.maxx)

		if self.headerpad is not None:
			self.headerpad.clear()
			# Whether to have one or two hlines depends on if we
			# overlap with the upper border or not
			if self.headerpadypos > 1:
				window_tee_hline(self.stdscr, self.headerpadypos - 1, 0, self.maxx)
			window_tee_hline(self.stdscr, self.headerpadypos + 1, 0, self.maxx)
			if self.borders == False:
				if self.headerpadypos > 1:
					self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.headerpadypos - 1, x = 0)
					self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.headerpadypos - 1, x = self.maxx)
				self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.headerpadypos + 1, x = 0)
				self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.headerpadypos + 1, x = self.maxx)
		elif self.listpad is not None and self.borders == False:
			self.addthemearray(self.stdscr, [ThemeString(" ", ThemeAttr("main", "default"))], y = self.listpadypos - 1, x = 0)
			self.addthemearray(self.stdscr, [ThemeString(" ", ThemeAttr("main", "default"))], y = self.listpadypos - 1, x = self.maxx)

		if self.logpad is not None:
			if self.logpadypos > 2:
				window_tee_hline(self.stdscr, self.logpadypos - 1, 0, self.maxx)
			if self.borders == True:
				window_tee_hline(self.stdscr, self.maxy - 2, 0, self.maxx)
				if self.tspad is not None and self.tspadxpos != self.logpadxpos and self.loglen > 0:
					window_tee_vline(self.stdscr, self.logpadxpos - 1, self.logpadypos - 1, self.maxy - 2)
			else:
				# If the window lacks sideborders we want lines
				self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.logpadypos - 1, x = 0)
				self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.logpadypos - 1, x = self.maxx)

		self.reset_update_delay()

	# pylint: disable-next=unused-argument
	def update_timestamp(self, ypos: int, xpos: int) -> None:
		# Elsewhere we use now(timezone.utc), but here we want the local timezone
		lastupdate = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
		rtee = deep_get(theme, DictPath("boxdrawing#rtee"))
		ltee = deep_get(theme, DictPath("boxdrawing#ltee"))

		timestamparray: List[Union[ThemeRef, ThemeString]] = [
			ThemeString(rtee, ThemeAttr("main", "default")),
		]

		if len(self.helpstring) > 0:
			timestamparray += [
				ThemeString(self.helpstring, ThemeAttr("main", "statusbar")),
				ThemeRef("separators", "statusbar"),
			]
		timestamparray += [
			ThemeString(lastupdate, ThemeAttr("main", "last_update")),
		]

		if self.borders == True:
			timestamparray += [
				ThemeString(ltee, ThemeAttr("main", "default")),
			]

		xpos -= themearray_len(timestamparray)
		if self.borders == False:
			xpos += 1
		self.addthemearray(self.stdscr, timestamparray, y = 0, x = xpos)

	def draw_winheader(self) -> None:
		if self.windowheader != "":
			ltee = deep_get(theme, DictPath("boxdrawing#ltee"))
			rtee = deep_get(theme, DictPath("boxdrawing#rtee"))

			winheaderarray: List[Union[ThemeRef, ThemeString]] = []

			if self.borders == True:
				winheaderarray += [
					ThemeString(rtee, ThemeAttr("main", "default")),
				]

			winheaderarray += [
				ThemeRef("separators", "mainheader_prefix"),
				ThemeString(f"{self.windowheader}", ThemeAttr("main", "header")),
				ThemeRef("separators", "mainheader_suffix"),
			]
			if self.borders == True:
				winheaderarray += [
					ThemeString(ltee, ThemeAttr("main", "default")),
				]
				self.addthemearray(self.stdscr, winheaderarray, y = 0, x = 1)
			else:
				self.addthemearray(self.stdscr, winheaderarray, y = 0, x = 0)

	def refresh_window(self) -> None:
		if self.borders == True:
			bl = deep_get(theme, DictPath("boxdrawing#llcorner"))
			br = deep_get(theme, DictPath("boxdrawing#lrcorner"))
			self.addthemearray(self.stdscr, [ThemeString(bl, ThemeAttr("main", "default"))], y = self.maxy - 2, x = 0)
			self.addthemearray(self.stdscr, [ThemeString(br, ThemeAttr("main", "default"))], y = self.maxy - 2, x = self.maxx)

		# The extra status can change, so we need to update the windowheader (which should not change)
		self.draw_winheader()

		mousestatus = "On" if get_mousemask() == -1 else "Off"
		mousearray: List[Union[ThemeRef, ThemeString]] = [
			ThemeString("Mouse: ", ThemeAttr("statusbar", "infoheader")),
			ThemeString(f"{mousestatus}", ThemeAttr("statusbar", "highlight"))
		]
		xpos = self.maxx - themearray_len(mousearray) + 1
		if self.statusbar is not None:
			self.addthemearray(self.statusbar, mousearray, y = 0, x = xpos)
		ycurpos = self.curypos + self.yoffset
		maxypos = self.maxcurypos + self.maxyoffset
		if ycurpos != 0 or maxypos != 0:
			curposarray: List[Union[ThemeRef, ThemeString]] = [
				# pylint: disable-next=line-too-long
				ThemeString("Line: ", ThemeAttr("statusbar", "infoheader")),
				ThemeString(f"{ycurpos + 1}".rjust(len(str(maxypos + 1))), ThemeAttr("statusbar", "highlight")),
				ThemeRef("separators", "statusbar_fraction"),
				ThemeString(f"{maxypos + 1}", ThemeAttr("statusbar", "highlight"))
			]
			xpos = self.maxx - themearray_len(curposarray) + 1
			if self.statusbar is not None:
				self.addthemearray(self.statusbar, curposarray, y = 1, x = xpos)
		self.stdscr.noutrefresh()

	# This should be called when a resize event is detected
	def resize_window(self) -> None:
		self.stdscr.clear()
		maxyx = self.stdscr.getmaxyx()
		self.miny = 0
		self.maxy = maxyx[0] - 1
		self.maxx = maxyx[1] - 1
		self.mincurypos = self.miny
		# screen position
		self.curypos = self.mincurypos
		# offset relative pad
		self.yoffset = 0
		self.maxyoffset = 0
		self.xoffset = 0
		self.maxxoffset = 0

		self.resize_statusbar()
		self.force_update()

	def refresh_all(self) -> None:
		self.stdscr.touchwin()
		self.stdscr.noutrefresh()
		if self.infopad:
			self.refresh_infopad()
		if self.listpad:
			self.refresh_listpad()
		if self.logpad:
			self.refresh_logpad()
		if self.statusbar:
			self.refresh_statusbar()
		self.refresh = True

	# For generic information
	# Pass -1 as width to the infopadminwidth
	# pylint: disable-next=too-many-arguments
	def init_infopad(self, height: int, width: int, ypos: int, xpos: int, labels: Optional[Dict] = None, annotations: Optional[Dict] = None) -> curses.window:
		self.infopadminwidth = self.maxx + 1
		self.infopadypos = ypos
		self.infopadxpos = xpos
		self.infopadheight = height
		self.infopadwidth = max(width, self.infopadminwidth)
		self.infopad = curses.newpad(max(self.infopadheight, self.maxy), self.infopadwidth)
		self.labels = get_labels(labels)
		self.annotations = get_annotations(annotations)
		return self.infopad

	# Pass -1 to keep the current height/width
	def resize_infopad(self, height: int, width: int) -> None:
		if self.infopad is None:
			return
		self.infopadminwidth = self.maxx - self.infopadxpos
		if height != -1:
			self.infopadheight = height
		self.infopad.erase()
		if width != -1:
			self.infopadwidth = max(width, self.infopadminwidth)
		self.infopad.resize(max(self.infopadheight, self.maxy), self.infopadwidth)

	def refresh_infopad(self) -> None:
		if self.infopad is not None:
			height = self.infopadheight
			if self.borders == True:
				if self.logpad is None and self.listpad is None:
					height = self.maxy - 3
				try:
					self.infopad.noutrefresh(0, 0, self.infopadypos, self.infopadxpos, height, self.maxx - 1)
				except curses.error:
					pass
			else:
				if self.logpad is None and self.listpad is None:
					height = self.maxy - 2
				try:
					self.infopad.noutrefresh(0, 0, self.infopadypos, self.infopadxpos - 1, height, self.maxx)
				except curses.error:
					pass

			# If there's no logpad and no listpad, then the infopad is responsible for scrollbars
			if self.listpad is None and self.logpad is None and self.borders == True:
				# pylint: disable-next=line-too-long
				self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, self.maxx, self.infopadypos, self.maxy - 3, self.infopadheight, self.yoffset, ThemeAttr("main", "boxdrawing"))
				# pylint: disable-next=line-too-long
				self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, self.maxy - 2, self.infopadxpos, self.maxx - 1, self.infopadwidth - 1, self.xoffset, ThemeAttr("main", "boxdrawing"))

	# For (optionally) scrollable lists of information,
	# optionally with a header
	# Pass -1 as width to use listpadminwidth
	# pylint: disable-next=too-many-arguments
	def init_listpad(self, listheight: int, width: int, ypos: int, xpos: int, header: bool = True) -> Tuple[Optional[curses.window], curses.window]:
		self.listpadminwidth = self.maxx
		if header == True:
			self.headerpadypos = ypos
			self.headerpadxpos = xpos
			self.headerpadheight = 1
			self.headerpadwidth = self.listpadminwidth
			self.listpadypos = ypos + 2
			self.headerpad = curses.newpad(self.headerpadheight, self.headerpadwidth)
		else:
			self.listpadypos = ypos
		self.listpadxpos = xpos
		self.listpadheight = self.maxy - 2 - self.listpadypos
		self.listpadwidth = max(width, self.listpadminwidth)
		self.listpad = curses.newpad(self.listpadheight, self.listpadwidth)
		self.selected = None

		return self.headerpad, self.listpad

	# Pass -1 to keep the current height/width
	def resize_listpad(self, width: int) -> None:
		if self.listpad is None:
			return
		self.listpadheight = self.maxy - 2 - self.listpadypos
		self.listpadminwidth = self.maxx
		self.listpad.erase()
		if width != -1:
			self.listpadwidth = max(width + 1, self.listpadminwidth)
		else:
			width = self.listpadwidth

		if self.borders == True:
			self.maxcurypos = min(self.listpadheight - 1, self.listlen - 1)
		else:
			self.maxcurypos = min(self.listpadheight - 1, self.listlen - 1)
		self.maxyoffset = self.listlen - (self.maxcurypos - self.mincurypos) - 1
		self.headerpadwidth = self.listpadwidth
		self.maxxoffset = max(0, self.listpadwidth - self.listpadminwidth)

		if self.headerpad is not None and self.headerpadheight > 0:
			self.headerpad.resize(self.headerpadheight, self.headerpadwidth)
		if self.listpadheight > 0:
			self.listpad.resize(max(self.listpadheight, self.maxy), self.listpadwidth)
		self.curypos = min(self.curypos, self.maxcurypos)
		self.yoffset = min(self.yoffset, self.maxyoffset)

	def refresh_listpad(self) -> None:
		xpos = self.listpadxpos
		maxx = self.maxx - 1
		if self.borders == False:
			xpos -= 1
			maxx = self.maxx
		if self.headerpad is not None:
			try:
				self.headerpad.noutrefresh(0, self.xoffset, self.headerpadypos, xpos, self.headerpadypos, maxx)
			except curses.error:
				pass
		if self.listpad is not None:
			if self.borders == True:
				try:
					self.listpad.noutrefresh(0, self.xoffset, self.listpadypos, xpos, self.maxy - 3, maxx)
				except curses.error:
					pass
				# pylint: disable-next=line-too-long
				self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, x = maxx + 1, miny = self.listpadypos, maxy = self.maxy - 3, height = self.listlen, yoffset = self.yoffset, clear_color = ThemeAttr("main", "boxdrawing"))
				# pylint: disable-next=line-too-long
				self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, y = self.maxy - 2, minx = self.listpadxpos, maxx = maxx, width = self.listpadwidth - 1, xoffset = self.xoffset, clear_color = ThemeAttr("main", "boxdrawing"))
			else:
				try:
					self.listpad.noutrefresh(self.yoffset, self.xoffset, self.listpadypos, xpos, self.maxy - 2, maxx)
				except curses.error:
					pass

	# Recalculate the xpos of the log; this is needed when timestamps are toggled
	def recalculate_logpad_xpos(self, tspadxpos: int = -1, timestamps: Optional[bool] = None) -> None:
		if tspadxpos == -1:
			if self.tspadxpos is None:
				raise ProgrammingError("logpad is not initialised and no tspad xpos provided")

		if timestamps is None:
			timestamps = self.tspadxpos != self.logpadxpos

		self.tspadxpos = tspadxpos

		if timestamps == False:
			self.tspadwidth = 0
			self.logpadxpos = self.tspadxpos
		else:
			self.tspadwidth = len("YYYY-MM-DD HH:MM:SS")
			#self.tspadwidth = len("YYYY-MM-DD")
			self.logpadxpos = self.tspadxpos + self.tspadwidth + 1

	# For (optionally) scrollable log of information with optional timestamps
	# The log widget behaves a bit differently than the list widget;
	# to avoid a lot of wasted memory when most log messages are short and there's one
	# string that can go for miles (if you know what I mean), we keep the pad
	# the same height as the visible area, and only update the content of the pad
	# as the yoffset changes.  The pad is still variable width though.
	#
	# Pass -1 as width to use logpadminwidth
	def init_logpad(self, width: int, ypos: int, xpos: int, timestamps: bool = True) -> Tuple[Optional[curses.window], curses.window]:
		self.match_index = None
		self.search_matches = set()

		self.logpadheight = self.maxy - ypos - 2
		self.recalculate_logpad_xpos(tspadxpos = xpos, timestamps = timestamps)
		if timestamps == True:
			self.tspadypos = ypos
			self.tspadheight = self.logpadheight
			self.tspad = curses.newpad(self.tspadheight + 1, self.tspadwidth)
		else:
			self.tspad = None
		self.logpadypos = ypos
		self.logpadminwidth = self.maxx - self.logpadxpos
		if width == -1:
			self.logpadwidth = self.logpadminwidth
		else:
			self.logpadwidth = max(width, self.logpadminwidth)
		self.logpad = curses.newpad(self.logpadheight + 1, self.logpadwidth)
		self.loglen = 0

		return self.tspad, self.logpad

	# Pass -1 to keep the current height/width
	# Calling this function directly is not necessary; the pad never grows down, and self.__addstr() calls this when x grows
	def resize_logpad(self, height: int, width: int) -> None:
		self.recalculate_logpad_xpos(tspadxpos = self.tspadxpos)
		if height != -1:
			if self.borders == True:
				self.tspadheight = height
				self.logpadheight = height
			else:
				self.tspadheight = height + 1
				self.logpadheight = height + 1
		if width != -1:
			self.logpadminwidth = self.maxx - self.logpadxpos
			self.logpadwidth = max(width, self.logpadminwidth)

		if self.logpadheight > 0:
			if self.tspad is not None and self.tspadxpos != self.logpadxpos:
				self.tspad.resize(self.tspadheight + 1, self.tspadwidth + 1)
			if self.logpad is not None:
				self.logpad.resize(self.logpadheight + 1, self.logpadwidth + 1)
		self.maxyoffset = max(0, self.loglen - self.logpadheight)
		self.maxxoffset = max(0, self.logpadwidth - self.logpadminwidth)
		self.yoffset = min(self.yoffset, self.maxyoffset)

	def refresh_logpad(self) -> None:
		if self.logpad is None:
			return

		self.yoffset = min(self.yoffset, self.maxyoffset)
		self.xoffset = min(self.xoffset, self.maxxoffset)

		tspadxpos = self.tspadxpos
		logpadxpos = self.logpadxpos
		if self.borders == False:
			tspadxpos -= 1
			logpadxpos -= 1
		if self.tspad is not None and self.tspadxpos != self.logpadxpos:
			hline = deep_get(theme, DictPath("boxdrawing#hline"))
			if self.borders == True:
				for i in range(0, self.tspadwidth):
					self.addthemearray(self.stdscr, [ThemeString(hline, ThemeAttr("main", "default"))], y = self.maxy - 2, x = 1 + i)
				try:
					self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos, self.maxy - 3, self.tspadwidth)
				except curses.error:
					pass
			else:
				try:
					self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos, self.maxy - 2, self.tspadwidth - 1)
				except curses.error:
					pass
		if self.borders == True:
			try:
				self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos, self.maxy - 3, self.maxx - 1)
			except curses.error:
				pass
			# pylint: disable-next=line-too-long
			self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, self.maxx, self.logpadypos, self.maxy - 3, self.loglen, self.yoffset, ThemeAttr("main", "boxdrawing"))
			# pylint: disable-next=line-too-long
			self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, self.maxy - 2, logpadxpos, self.maxx - 1, self.logpadwidth, self.xoffset, ThemeAttr("main", "boxdrawing"))
		else:
			try:
				self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos, self.maxy - 2, self.maxx)
			except curses.error:
				pass

	def toggle_timestamps(self, timestamps: Optional[bool] = None) -> None:
		if timestamps is None:
			timestamps = self.tspadxpos == self.logpadxpos

		self.recalculate_logpad_xpos(tspadxpos = self.tspadxpos, timestamps = timestamps)

	def toggle_borders(self, borders: Optional[bool] = None) -> None:
		if borders is None:
			self.borders = not self.borders
		else:
			self.borders = borders

		self.recalculate_logpad_xpos(tspadxpos = self.tspadxpos)

	def init_statusbar(self) -> curses.window:
		"""
		Initialise the statusbar

			Returns:
				statusbar (curses.window): A reference to the statusbar object
		"""

		self.resize_statusbar()

		return cast(curses.window, self.statusbar)

	def refresh_statusbar(self) -> None:
		"""
		Refresh the statusbar
		"""

		if self.statusbar is not None:
			col, __discard = themeattr_to_curses(ThemeAttr("statusbar", "default"))
			self.statusbar.bkgd(" ", col)
			try:
				self.statusbar.noutrefresh(0, 0, self.statusbarypos, 0, self.maxy, self.maxx)
			except curses.error:
				pass

	def resize_statusbar(self) -> None:
		"""
		Trigger the statusbar to be resized
		"""

		self.statusbarypos = self.maxy - 1
		if self.statusbar is not None:
			self.statusbar.erase()
			self.statusbar.resize(2, self.maxx + 1)
		else:
			self.statusbar = curses.newpad(2, self.maxx + 1)

	# pylint: disable-next=too-many-arguments
	def addthemearray(self, win: curses.window,
			  array: List[Union[ThemeRef, ThemeString]], y: int = -1, x: int = -1, selected: Optional[bool] = None) -> Tuple[int, int]:
		"""
		Add a ThemeArray to a curses window

			Parameters:
				win (curses.window): The curses window to operate on
				array (list[union[ThemeRef, ThemeString]]): The themearray to add to the curses window
				y (int): The y-coordinate (-1 to start from current cursor position)
				x (int): The x-coordinate (-1 to start from current cursor position)
				selected (bool): Should the selected version of the ThemeArray be used
			Returns:
				(y, x):
					y (int): The new y-coordinate
					x (int): The new x-coordinate
		"""

		for item in themearray_flatten(array):
			string, attr = themestring_to_cursestuple(item)
			# If there still are remaining <NUL> occurences, replace them
			string = string.replace("\x00", "<NUL>")

			maxy, maxx = win.getmaxyx()
			cury, curx = win.getyx()

			newmaxy = max(y, maxy)
			newmaxx = max(maxx, len(string) + curx + 1)

			if win != self.stdscr:
				win.resize(newmaxy, newmaxx)
			elif win == self.stdscr and (maxy, maxx) != (newmaxy, newmaxx):
				# If the string to print is *exactly* maxx == len(string) + curx,
				# then we check if we can print the last character using addch(),
				# otherwise we give up.
				if (maxy, maxx) == (newmaxy, len(string) + curx):
					try:
						win.addch(y, maxx - 1, string[-1:], attr)
						win.addstr(string[0:-1], attr)
					except curses.error:
						cury, curx = win.getyx()
						return cury, curx
				else:
					# If the message would resize the window,
					# just pretend success instead of raising an exception
					cury, curx = win.getyx()
					return cury, curx

			try:
				win.addstr(y, x, string, attr)
			except curses.error:
				pass
			y, x = win.getyx()
		return y, x

	def move_xoffset_abs(self, position: int) -> None:
		if self.borders == True:
			sideadjust = 0
		else:
			sideadjust = 2
		if position == -1:
			self.xoffset = self.maxxoffset - sideadjust
		elif position == 0:
			self.xoffset = 0
		else:
			self.xoffset = max(0, position)
			self.xoffset = min(self.xoffset, self.maxxoffset - sideadjust)
		self.refresh = True

	def move_yoffset_abs(self, position: int) -> None:
		if position == -1:
			self.yoffset = self.maxyoffset
		elif position == 0:
			self.yoffset = 0
		else:
			self.yoffset = max(0, position)
			self.yoffset = min(self.yoffset, self.maxyoffset)
		self.refresh = True

	def move_xoffset_rel(self, movement: int) -> None:
		if self.borders == True:
			sideadjust = 0
		else:
			sideadjust = 2
		self.xoffset = max(0, self.xoffset + movement)
		self.xoffset = min(self.xoffset, self.maxxoffset - sideadjust)
		self.refresh = True

	def move_yoffset_rel(self, movement: int) -> None:
		self.yoffset = max(0, self.yoffset + movement)
		self.yoffset = min(self.maxyoffset, self.yoffset)
		self.refresh = True

	def move_cur_abs(self, position: int) -> None:
		if position == -1:
			self.curypos = self.maxcurypos
			self.yoffset = self.maxyoffset
		elif position == 0:
			self.curypos = self.mincurypos
			self.yoffset = 0
		else:
			raise ProgrammingError("FIXME")
		self.list_needs_regeneration(True)

	def move_cur_with_offset(self, movement: int) -> None:
		newcurypos = self.curypos + movement
		newyoffset = self.yoffset

		# If we are being asked to move forward but we are already
		# at the end of the list, it is prudent not to move,
		# even if the caller so requests.
		# It is just good manners, really.
		if self.yoffset + newcurypos > self.listlen:
			newcurypos = min(newcurypos, self.maxcurypos)
			newyoffset = self.maxyoffset
		elif newcurypos > self.maxcurypos:
			newyoffset = min(self.yoffset - (self.maxcurypos - newcurypos), self.maxyoffset)
			newcurypos = self.maxcurypos
		elif newcurypos < self.mincurypos:
			newyoffset = max(self.yoffset + (newcurypos - self.mincurypos), 0)
			newcurypos = self.mincurypos

		if self.curypos != newcurypos or self.yoffset != newyoffset:
			self.curypos = newcurypos
			self.yoffset = newyoffset
			self.list_needs_regeneration(True)

	def find_all_matches_by_searchkey(self, messages, searchkey: str) -> None:
		self.match_index = None
		self.search_matches.clear()

		if len(searchkey) == 0:
			return

		for y, msg in enumerate(messages):
			# The messages can either be raw strings,
			# or themearrays, so we need to flatten them to just text first
			message = themearray_to_string(msg)
			if searchkey in message:
				self.search_matches.add(y)

	def find_next_match(self) -> None:
		start = self.match_index
		if start is None:
			start = self.yoffset
		for y in range(start, self.loglen):
			if y in self.search_matches:
				if self.match_index is None or self.match_index != y:
					self.match_index = y
					self.yoffset = min(y, self.maxyoffset)
					break

	def find_prev_match(self) -> None:
		end = self.match_index
		if end is None:
			end = self.yoffset
		for y in reversed(range(0, end)):
			if y in self.search_matches:
				# We do not want to return the same match over and over...
				if self.match_index is None or self.match_index != y:
					self.match_index = y
					self.yoffset = min(y, self.maxyoffset)
					break

	# Find the next line that has severity > NOTICE
	def next_line_by_severity(self, severities: Optional[List[LogLevel]]) -> None:
		y = 0
		newoffset = self.yoffset

		if severities is None:
			return

		for severity in severities:
			# We are only searching forward
			if y > self.yoffset and severity < LogLevel.NOTICE:
				newoffset = y
				break
			y += 1

		self.yoffset = min(newoffset, self.maxyoffset)
		self.refresh = True

	# Find the prev line that has severity > NOTICE
	def prev_line_by_severity(self, severities: Optional[List[LogLevel]]) -> None:
		y = 0
		newoffset = self.yoffset

		if severities is None:
			return

		for severity in severities:
			# We are only searching backward
			if y == self.yoffset:
				break
			if severity < LogLevel.NOTICE:
				newoffset = y
			y += 1

		self.yoffset = newoffset
		self.refresh = True

	def next_by_sortkey(self, info: List[Type]) -> None:
		if self.sortkey1 is None:
			return

		pos = self.curypos + self.yoffset
		y = 0
		newpos = 0
		current = ""
		sortkey1, sortkey2 = self.get_sortkeys()
		sortkey = sortkey2 if sortkey1 == "status_group" else sortkey1

		# Search forward within sort category
		# next namespace when sorted by namespace
		# next (existing) letter when sorted by name
		# next status when sorted by status
		# next node when sorted by node
		for entry in natsorted(info, key = attrgetter(sortkey1, sortkey2), reverse = self.sortorder_reverse):
			entryval = getattr(entry, sortkey)

			# OK, from here we want to go to next entry
			if y == pos:
				if sortkey == "age" or self.sortkey1 == "seen":
					current = cmtlib.seconds_to_age(entryval)
				else:
					current = entryval
			elif y > pos:
				if sortkey == "name":
					if current[0] != entryval[0]:
						newpos = y - pos
						break
				elif sortkey == "age" or self.sortkey1 == "seen":
					if current != cmtlib.seconds_to_age(entryval):
						newpos = y - pos
						break
				else:
					if current != entryval:
						newpos = y - pos
						break
			y += 1

		# If we do not match we will just end up with the old pos
		self.move_cur_with_offset(newpos)

	def prev_by_sortkey(self, info: List[Type]) -> None:
		if self.sortkey1 is None:
			return

		pos = self.curypos + self.yoffset
		y = 0
		newpos = 0
		current = None
		sortkey1, sortkey2 = self.get_sortkeys()
		sortkey = sortkey2 if sortkey1 == "status_group" else sortkey1

		# Search backward within sort category
		# prev namespace when sorted by namespace
		# prev (existing) letter when sorted by name
		# prev status when sorted by status
		# prev node when sorted by node
		for entry in natsorted(info, key = attrgetter(sortkey1, sortkey2), reverse = self.sortorder_reverse):
			entryval = getattr(entry, sortkey)
			if current is None:
				if sortkey == "age" or self.sortkey1 == "seen":
					current = cmtlib.seconds_to_age(entryval)
				else:
					current = entryval

			if y == pos:
				break

			if sortkey == "name" and current is not None and len(current) > 0:
				if current[0] != entryval[0]:
					current = entryval
					newpos = y - pos
			elif sortkey == "age":
				if current != cmtlib.seconds_to_age(getattr(entry, sortkey)):
					current = cmtlib.seconds_to_age(entryval)
					newpos = y - pos
			else:
				if current != entryval:
					current = entryval
					newpos = y - pos
			y += 1

		# If we do not match we will just end up with the old pos
		if newpos == 0:
			self.move_cur_abs(0)
		else:
			self.move_cur_with_offset(newpos)

	def find_next_by_sortkey(self, info: List[Type], searchkey: str) -> None:
		pos = self.curypos + self.yoffset
		offset = 0

		# Search within sort category
		sorted_list = natsorted(info, key = attrgetter(self.sortkey1, self.sortkey2), reverse = self.sortorder_reverse)
		match = False
		for y in range(pos, len(sorted_list)):
			tmp2 = getattr(sorted_list[y], self.sortcolumn)
			if self.sortkey1 in ("age", "first_seen", "last_restart", "seen"):
				tmp2 = [cmtlib.seconds_to_age(tmp2)]
			else:
				if isinstance(tmp2, (list, tuple)):
					if isinstance(tmp2[0], tuple):
						tmp3: List = []
						for t in tmp2:
							tmp3 += map(str, t)
						tmp2 = tmp3
					else:
						tmp2 = map(str, tmp2)
				else:
					tmp2 = [str(tmp2)]
			for part in tmp2:
				part = part[0:len(searchkey)].rstrip().lower()
				if searchkey == part:
					offset = y - pos
					if offset > 0:
						match = True
						break
			if match == True:
				break

		# If we do not match we will just end up with the old pos
		self.move_cur_with_offset(offset)

	def find_prev_by_sortkey(self, info: List[Type], searchkey: str) -> None:
		pos = self.curypos + self.yoffset
		offset = 0

		# Search within sort category
		sorted_list = natsorted(info, key = attrgetter(self.sortkey1, self.sortkey2), reverse = self.sortorder_reverse)
		match = False
		for y in reversed(range(0, pos)):
			tmp2 = getattr(sorted_list[y], self.sortcolumn)
			if self.sortkey1 in ("age", "seen"):
				tmp2 = [cmtlib.seconds_to_age(tmp2)]
			else:
				if isinstance(tmp2, (list, tuple)):
					tmp2 = map(str, tmp2)
				else:
					tmp2 = [str(tmp2)]
			for part in tmp2:
				part = part[0:len(searchkey)].rstrip().lower()
				if searchkey == part:
					offset = y - pos
					if offset < 0:
						match = True
						break
			if match == True:
				break

		# If we do not match we will just end up with the old pos
		self.move_cur_with_offset(offset)

	def goto_first_match_by_name_namespace(self, name: str, namespace: str) -> Optional[Type]:
		"""
		This function is used to find the first match based on command line input
		The sort order used will still be the default, to ensure that the partial
		match ends up being the first.

			Parameters:
				name (str): The name to search for
				namespace (str): The namespace to search for
			Returns:
				match (InfoType): The unique match, the first partial match if no unique match is found, or None if no match is found
		"""

		if self.info is None or len(self.info) == 0 or name is None or len(name) == 0 or hasattr(self.info[0], "name") == False:
			return None

		# Search within sort category
		sorted_list = natsorted(self.info, key = attrgetter(self.sortkey1, self.sortkey2), reverse = self.sortorder_reverse)
		first_match = None
		unique_match = None
		match_count = 0

		for y, listitem in enumerate(sorted_list):
			if hasattr(sorted_list[0], "namespace"):
				if namespace is not None and listitem.namespace != namespace:
					continue

			if listitem.name == name:
				first_match = y
				match_count = 1
				break

			if listitem.name.startswith(name):
				if first_match is None:
					first_match = y
				match_count += 1

		if first_match is not None:
			self.move_cur_with_offset(first_match)
		if match_count == 1:
			unique_match = sorted_list[self.curypos + self.yoffset].ref

		return unique_match

	def next_sortcolumn(self) -> None:
		if self.sortcolumn is None or self.sortcolumn == "":
			return

		match = 0
		for field in self.field_list:
			if self.field_list[field].get("skip", False) == True:
				continue
			if match == 1:
				self.sortcolumn = field
				break
			if field == self.sortcolumn:
				match = 1

		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.sort_triggered = True

	def prev_sortcolumn(self) -> None:
		if self.sortcolumn is None or self.sortcolumn == "":
			return

		match = 0
		for field in reversed(self.field_list):
			if match == 1:
				self.sortcolumn = field
				break
			if field == self.sortcolumn:
				match = 1

		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.sort_triggered = True

	def get_sortcolumn(self) -> str:
		return self.sortcolumn

	def get_sortkeys(self) -> Tuple[str, str]:
		if self.field_list is None:
			# We do not really care about what the sortkeys are; we do not have a list to sort
			# but if we return valid strings we can at least pacify the type checker
			return "", ""

		field = self.field_list.get(self.sortcolumn)

		if field is None:
			valid_fields = []
			for f in self.field_list:
				valid_fields.append(f)
			raise ValueError(f"Invalid sortcolumn: {self.sortcolumn} does not exist in field_list:\nvalid fields are: {valid_fields}")

		sortkey1 = self.field_list[self.sortcolumn]["sortkey1"]
		sortkey2 = self.field_list[self.sortcolumn]["sortkey2"]
		return sortkey1, sortkey2

	# pylint: disable-next=too-many-arguments,too-many-return-statements
	def handle_mouse_events(self, win: curses.window, sorted_list, activatedfun, extraref, data) -> Retval:
		try:
			_eventid, x, y, _z, bstate = curses.getmouse()
		except curses.error:
			# Most likely mouse is not supported
			return Retval.NOMATCH

		if win == self.listpad:
			if self.listpad is None:
				return Retval.NOMATCH
			cypos = self.listpadypos
			cxpos = self.listpadxpos
			cheight = self.listpadheight
			selections = True
		elif win == self.logpad:
			if self.logpad is None:
				return False
			cypos = self.logpadypos
			cxpos = self.logpadxpos
			cheight = self.logpadheight
			# We do not care about selection
			selections = False
		else:
			return Retval.NOMATCH

		cmaxy = self.maxy
		cmaxx = self.maxx
		cyoffset = self.yoffset
		ypos = y - cypos
		xpos = x - cxpos

		#if bstate == curses.BUTTON1_PRESSED:
			# Here goes handling of dragging scrollbars
		if bstate == curses.BUTTON1_DOUBLE_CLICKED and selections == True:
			# double-clicks on list items
			if activatedfun is not None and cypos <= y < min(cheight + cypos, cmaxy) and cxpos <= x < cmaxx:
				selected = sorted_list[ypos + cyoffset]
				self.select(selected)
				self.curypos = ypos

				if selected.ref is not None:
					if extraref is not None:
						view = getattr(selected, extraref, self.view)

						on_activation = copy.deepcopy(self.on_activation)
						kind = deep_get(on_activation, DictPath("kind"), view)
						on_activation.pop("kind", None)
						if data is not None:
							_retval = activatedfun(self.stdscr, selected.ref, kind, info = data, **on_activation)
						else:
							_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
					else:
						on_activation = copy.deepcopy(self.on_activation)
						kind = deep_get(on_activation, DictPath("kind"), self.view)
						on_activation.pop("kind", None)
						_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
					if _retval is not None:
						self.force_refresh()
					return _retval
		elif bstate == curses.BUTTON1_CLICKED:
			# clicks on list items
			if cypos <= y < min(cheight + cypos, cmaxy) and cxpos <= x < cmaxx and selections == True:
				selected = self.get_selected()

				# If we are clicking on something that is not selected (or if nothing is selected), move here
				if selected is None or selected != sorted_list[ypos + cyoffset]:
					# We want to move the cursor here
					self.selected = sorted_list[ypos + self.yoffset]
					self.curypos = ypos
				else:
					# If we click an already selected item we open it
					if selected.ref is not None and activatedfun is not None:
						self.force_update()
						if extraref is not None:
							view = getattr(selected, extraref, self.view)

							on_activation = copy.deepcopy(self.on_activation)
							kind = deep_get(on_activation, DictPath("kind"), view)
							on_activation.pop("kind", None)
							if data is not None:
								_retval = activatedfun(self.stdscr, selected.ref, kind, info = data, **on_activation)
							else:
								_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
						else:
							on_activation = copy.deepcopy(self.on_activation)
							kind = deep_get(on_activation, DictPath("kind"), self.view)
							on_activation.pop("kind", None)
							_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
						if _retval is not None:
							self.force_refresh()
						return _retval
			# clicks on the vertical scrollbar
			elif (y, x) == (self.upperarrow):
				if win == self.listpad:
					self.move_cur_with_offset(-1)
				else:
					self.move_yoffset_rel(-1)
			elif (y, x) == (self.lowerarrow):
				if win == self.listpad:
					self.move_cur_with_offset(1)
				else:
					self.move_yoffset_rel(1)
			elif x == self.upperarrow[1]:
				if self.upperarrow[0] < y < self.lowerarrow[0]:
					# Do not count the arrows
					total = self.lowerarrow[0] - self.upperarrow[0] - 2
					# Y-position on the bar
					ypos = y - self.upperarrow[0] - 1
					# moveoffset
					moveoffset = int((ypos / total) * self.listpadheight)
					# start by moving the cursor & offset to 0
					# that way we can do an relative move
					self.move_cur_abs(0)
					self.move_cur_with_offset(moveoffset)
			# clicks on the horizontal scrollbar
			elif (y, x) == (self.leftarrow):
				self.move_xoffset_rel(-1)
			elif (y, x) == (self.rightarrow):
				self.move_xoffset_rel(1)
			elif y == self.leftarrow[0]:
				if self.leftarrow[1] < x < self.rightarrow[1]:
					# Do not count the arrows
					total = self.rightarrow[1] - self.leftarrow[1] - 2
					# X-position on the bar
					xpos = x - self.leftarrow[1] - 1
					move = int(self.maxxoffset * (xpos / total))
					self.move_xoffset_abs(move)
		elif bstate == curses.BUTTON2_CLICKED:
			# Middle button
			pass
		elif bstate == curses.BUTTON3_CLICKED:
			# Right button
			pass
		elif curses_configuration.mousescroll_enable and bstate == curses_configuration.mousescroll_up:
			# Scroll wheel up
			if self.listpad is not None:
				self.move_cur_with_offset(-5)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(-5)
			return Retval.MATCH
		elif curses_configuration.mousescroll_enable and bstate == curses_configuration.mousescroll_down:
			if self.listpad is not None:
				self.move_cur_with_offset(5)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(5)
			return Retval.MATCH

		return Retval.NOMATCH

	def enter_handler(self, activatedfun, extraref, data) -> Retval:
		selected = self.get_selected()

		if activatedfun is not None and selected is not None and selected.ref is not None:
			if extraref is not None:
				view = getattr(selected, extraref, self.view)

				on_activation = copy.deepcopy(self.on_activation)
				kind = deep_get(on_activation, DictPath("kind"), view)
				on_activation.pop("kind", None)
				if data is not None:
					_retval = activatedfun(self.stdscr, selected.ref, kind, info = data, **on_activation)
				else:
					_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
			else:
				on_activation = copy.deepcopy(self.on_activation)
				kind = deep_get(on_activation, DictPath("kind"), self.view)
				on_activation.pop("kind", None)
				_retval = activatedfun(self.stdscr, selected.ref, kind, **on_activation)
			if _retval is not None:
				self.force_refresh()
			return _retval

		return Retval.NOMATCH

	# pylint: disable-next=too-many-return-statements
	def generic_keycheck(self, c: int) -> Retval:
		if c == curses.KEY_RESIZE:
			self.resize_window()
			return Retval.MATCH
		elif c == 27:	# ESCAPE
			del self
			return Retval.RETURNONE
		elif c == curses.KEY_MOUSE:
			return self.handle_mouse_events(cast(curses.window, self.listpad), self.sorted_list, self.activatedfun, self.extraref, self.data)
		elif c in (curses.KEY_ENTER, 10, 13) and self.activatedfun is not None:
			return self.enter_handler(self.activatedfun, self.extraref, self.data)
		elif c == ord("M"):
			# Toggle mouse support on/off to allow for copy'n'paste
			if get_mousemask() == 0:
				set_mousemask(-1)
			else:
				set_mousemask(0)
			if self.statusbar is not None:
				self.statusbar.erase()
			self.refresh_all()
			return Retval.MATCH
		elif c == ord("") or c == ord(""):
			curses.endwin()
			sys.exit()
		elif c == curses.KEY_F1 or c == ord("H"):
			if self.helptext is not None:
				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
					     items = self.helptext, title = "Help", cursor = False)
			self.refresh_all()
			return Retval.MATCH
		elif c == curses.KEY_F12:
			if curses_configuration.abouttext is not None:
				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
					     items = curses_configuration.abouttext, title = "About", cursor = False)
			self.refresh_all()
			return Retval.MATCH
		elif c == curses.KEY_F5:
			# We need to rate limit this somehow
			self.force_update()
			return Retval.MATCH
		elif c == ord("r"):
			# Reverse the sort order
			if self.listpad is not None and self.reversible == True:
				self.sortorder_reverse = not self.sortorder_reverse
				self.sort_triggered = True
			return Retval.MATCH
		elif c == curses.KEY_SLEFT:
			# For listpads we switch sort column with this; for logpads we move half a page left/right
			if self.listpad is not None:
				self.prev_sortcolumn()
			elif self.logpad is not None and self.continuous_log == False:
				self.move_xoffset_rel(-(self.logpadminwidth // 2))
			return Retval.MATCH
		elif c == curses.KEY_SRIGHT:
			if self.listpad is not None:
				self.next_sortcolumn()
			elif self.logpad is not None and self.continuous_log == False:
				self.move_xoffset_rel(self.logpadminwidth // 2)
			return Retval.MATCH
		elif c == curses.KEY_UP:
			if self.listpad is not None:
				self.move_cur_with_offset(-1)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(-1)
			return Retval.MATCH
		elif c == curses.KEY_DOWN:
			if self.listpad is not None:
				self.move_cur_with_offset(1)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(1)
			return Retval.MATCH
		elif c == curses.KEY_LEFT:
			if self.logpad is not None and self.continuous_log:
				return Retval.MATCH

			self.move_xoffset_rel(-1)
			return Retval.MATCH
		elif c == curses.KEY_RIGHT:
			if self.logpad is not None and self.continuous_log:
				return Retval.MATCH

			self.move_xoffset_rel(1)
			return Retval.MATCH
		elif c == curses.KEY_HOME:
			if self.logpad is not None and self.continuous_log:
				return Retval.MATCH

			self.move_xoffset_abs(0)
			return Retval.MATCH
		elif c == curses.KEY_END:
			if self.logpad is not None and self.continuous_log:
				return Retval.MATCH

			self.move_xoffset_abs(-1)
			return Retval.MATCH
		elif c == curses.KEY_SHOME:
			if self.logpad is not None:
				if self.continuous_log:
					return Retval.MATCH
				self.move_yoffset_abs(0)
			elif self.listpad is not None:
				self.move_cur_abs(0)
			return Retval.MATCH
		elif c == curses.KEY_SEND:
			if self.logpad is not None:
				if self.continuous_log:
					return Retval.MATCH
				self.move_yoffset_abs(-1)
			elif self.listpad is not None:
				self.move_cur_abs(-1)
			return Retval.MATCH
		elif c == curses.KEY_PPAGE:
			if self.listpad is not None:
				self.move_cur_with_offset(-10)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(-(self.logpadheight - 2))
			return Retval.MATCH
		elif c == curses.KEY_NPAGE:
			if self.listpad is not None:
				self.move_cur_with_offset(10)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(self.logpadheight - 2)
			return Retval.MATCH
		elif c == ord("\t"):
			if self.listpad is not None:
				self.next_by_sortkey(self.info)
			elif self.logpad is not None and self.continuous_log == False:
				self.next_line_by_severity(self.severities)
			return Retval.MATCH
		elif c == curses.KEY_BTAB:
			if self.listpad is not None:
				self.prev_by_sortkey(self.info)
			elif self.logpad is not None and self.continuous_log == False:
				self.prev_line_by_severity(self.severities)
			return Retval.MATCH
		elif c == ord("§"):
			# For listpads this jumps to the next column
			if self.listpad is not None:
				# In case the list empty for some reason
				tabstop = 0
				curxoffset = self.xoffset
				# Find next tabstop
				for tabstop in self.tabstops:
					if curxoffset < tabstop:
						if tabstop <= self.maxxoffset:
							self.move_xoffset_abs(tabstop)
						break
			return Retval.MATCH
		elif c == ord("½"):
			# For listpads this jumps to the previous column
			if self.listpad is not None:
				# In case the list empty for some reason
				tabstop = 0
				curxoffset = self.xoffset
				# Find previous tabstop
				for tabstop in reversed(self.tabstops):
					if curxoffset > tabstop:
						self.move_xoffset_abs(tabstop)
						break
			return Retval.MATCH
		elif c == ord("") or c == ord("/"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return Retval.MATCH

				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, f"Search in “{self.sortcolumn}“: ").rstrip().lower()
				if searchkey is None or searchkey == "":
					return Retval.MATCH

				self.find_next_by_sortkey(self.info, searchkey)
				self.searchkey = searchkey
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return Retval.MATCH

				self.refresh = True
				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Find: ")
				if searchkey is None or searchkey == "":
					self.match_index = None
					self.search_matches.clear()
					return Retval.MATCH

				self.find_all_matches_by_searchkey(self.messages, searchkey)
				self.find_next_match()
			return Retval.MATCH
		elif c == ord("?"):
			self.search_matches.clear()

			if self.listpad is not None:
				if self.listpadheight < 2:
					return Retval.MATCH

				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, f"Search in “{self.sortcolumn}“: ").rstrip().lower()
				if searchkey is None or searchkey == "":
					return Retval.MATCH

				self.find_prev_by_sortkey(self.info, searchkey)
				self.searchkey = searchkey
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return Retval.MATCH

				self.refresh = True
				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Find: ")
				if searchkey is None or searchkey == "":
					self.match_index = None
					self.search_matches.clear()
					return Retval.MATCH

				self.find_all_matches_by_searchkey(self.messages, searchkey)
				self.find_next_match()
			return Retval.MATCH
		elif c == ord("n"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return Retval.MATCH

				if self.searchkey is None or self.searchkey == "":
					return Retval.MATCH

				self.find_next_by_sortkey(self.info, self.searchkey)
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log == True or len(self.search_matches) == 0:
					return Retval.MATCH

				self.refresh = True
				self.find_next_match()
			return Retval.MATCH
		elif c == ord("p"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return Retval.MATCH

				if self.searchkey is None or self.searchkey == "":
					return Retval.MATCH

				self.find_prev_by_sortkey(self.info, self.searchkey)
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log == True or len(self.search_matches) == 0:
					return Retval.MATCH

				self.refresh = True
				self.find_prev_match()
			return Retval.MATCH
		elif c == ord("a"):
			if self.annotations is not None:
				title = ""

				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
					     items = self.annotations, headers = annotation_headers, title = title, cursor = False)

				self.refresh_all()
				return Retval.MATCH
		elif c == ord("l"):
			if self.labels is not None:
				title = ""

				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
					     items = self.labels, headers = label_headers, title = title, cursor = False)

				self.refresh_all()
				return Retval.MATCH

		# Nothing good enough for you, eh?
		return Retval.NOMATCH

	# Shortcuts used in most view
	def __exit_program(self, **kwargs: Dict) -> NoReturn:
		retval = deep_get(kwargs, DictPath("retval"))

		curses.endwin()
		sys.exit(retval)

	# pylint: disable-next=unused-argument
	def __refresh_information(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		# XXX: We need to rate limit this somehow
		self.force_update()
		return Retval.MATCH, {}

	def __select_menu(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		refresh_apis = deep_get(kwargs, DictPath("refresh_apis"), False)
		selectwindow = deep_get(kwargs, DictPath("selectwindow"))

		retval = selectwindow(self, refresh_apis = refresh_apis)
		if retval == Retval.RETURNFULL:
			return retval, {}
		self.refresh_all()
		return retval, {}

	# pylint: disable-next=unused-argument
	def __show_about(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		if curses_configuration.abouttext is not None:
			windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
				     items = curses_configuration.abouttext, title = "About", cursor = False)
		self.refresh_all()
		return Retval.MATCH, {}

	def __show_help(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		helptext = deep_get(kwargs, DictPath("helptext"))

		windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2,
			     items = helptext, title = "Help", cursor = False)
		self.refresh_all()
		return Retval.MATCH, {}

	# pylint: disable-next=unused-argument
	def __toggle_mouse(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		# Toggle mouse support on/off to allow for copy'n'paste
		if get_mousemask() == 0:
			set_mousemask(-1)
		else:
			set_mousemask(0)
		if self.statusbar is not None:
			self.statusbar.erase()
		self.refresh_all()
		return Retval.MATCH, {}

	# pylint: disable-next=unused-argument
	def __toggle_borders(self, **kwargs: Dict) -> Tuple[Retval, Dict]:
		self.toggle_borders()
		self.refresh_all()
		self.force_update()
		return Retval.MATCH, {}

	def generate_helptext(self, shortcuts: Dict, **kwargs: Dict) -> List[Dict]:
		"""
		Generate helptexts to use with generic_inputhandler()

			Parameters:
				shortcuts (dict): A dict of shortcuts
				kwargs (dict): Additional parameters
			Returns:
				list[Dict]: A list of dicts formatted for passing to windowwidget()
		"""

		read_only_mode = deep_get(kwargs, DictPath("read_only"), False)
		subview = deep_get(kwargs, DictPath("subview"), False)

		# There are (up to) four helptext groups:
		# Global
		# Global F-keys
		# Command
		# Navigation keys
		helptext_groups: List[List] = [[], [], [], []]

		for shortcut_name, shortcut_data in shortcuts.items():
			read_only = deep_get(shortcut_data, DictPath("read_only"), False)
			if read_only_mode == True and read_only == False:
				continue

			helptext_group = deep_get(shortcut_data, DictPath("helpgroup"))
			if helptext_group is None:
				raise ValueError(f"The shortcut {shortcut_name} has no helpgroup; this is a programming error.")
			tmp = deep_get(shortcut_data, DictPath("helptext"))
			if tmp is None:
				raise ValueError(f"The shortcut {shortcut_name} has no helptext; this is a programming error.")

			helptext_groups[helptext_group].append(tmp)

		helptext = []
		if subview == True:
			helptext.append(("", ""))

		first = True
		for helptexts in helptext_groups:
			if len(helptexts) == 0:
				continue
			if first == False:
				helptext.append(("", ""))
			for key, description in helptexts:
				helptext.append((key, description))
			first = False

		return format_helptext(helptext)

	def generic_inputhandler(self, shortcuts: Dict, **kwargs: Dict) -> Tuple[Retval, Dict]:
		"""
		Generic inputhandler for views

			Parameters:
				shortcuts (dict): View-specific shortcuts
				kwargs (dict): Additional parameters
			Returns:
				(Retval, dict): retval, return_args
		"""

		__common_shortcuts = {
			"Exit program": {
				"shortcut": [ord(""), ord("")],
				"helptext": ("[Ctrl] + X", "Exit program"),
				"helpgroup": 0,
				"action": "key_callback",
				"action_call": self.__exit_program,
				"action_args": {
					"retval": 0,
				}
			},
			"Refresh information": {
				"shortcut": curses.KEY_F5,
				"helptext": ("[F5]", "Refresh information"),
				"helpgroup": 1,
				"action": "key_callback",
				"action_call": self.__refresh_information,
			},
			"Show information about the program": {
				"shortcut": curses.KEY_F12,
				"helptext": ("[F12]", "Show information about the program"),
				"helpgroup": 1,
				"action": "key_callback",
				"action_call": self.__show_about,
			},
			"Show this helptext": {
				"shortcut": [curses.KEY_F1, ord("H")],
				"helptext": ("[F1] / [Shift] + H", "Show this helptext"),
				"helpgroup": 1,
				"action": "key_callback",
				"action_call": self.__show_help,
			},
			"Switch main view": {
				"shortcut": curses.KEY_F2,
				"helptext": ("[F2]", "Switch main view"),
				"helpgroup": 1,
				"action": "key_callback",
				"action_call": self.__select_menu,
			},
			"Switch main view (recheck available API resources)": {
				"shortcut": curses.KEY_F3,
				"helptext": ("[F3]", "Switch main view (recheck available API resources)"),
				"helpgroup": 1,
				"action": "key_callback",
				"action_call": self.__select_menu,
				"action_args": {
					"refresh_apis": True,
				}
			},
			"Toggle mouse on/off": {
				"shortcut": ord("M"),
				"helptext": ("[Shift] + M", "Toggle mouse on/off"),
				"helpgroup": 0,
				"action": "key_callback",
				"action_call": self.__toggle_mouse,
			},
			"Toggle borders": {
				"shortcut": ord("B"),
				"helptext": ("[Shift] + B", "Toggle borders on/off"),
				"helpgroup": 0,
				"action": "key_callback",
				"action_call": self.__toggle_borders,
			},
		}

		self.stdscr.timeout(100)
		c = self.stdscr.getch()

		# Default return value if we do not manage to match anything
		retval = Retval.NOMATCH

		if c == curses.KEY_RESIZE:
			self.resize_window()
			return Retval.MATCH, {}

		if c == 27:	# ESCAPE
			del self
			return Retval.RETURNONE, {}

		if c == curses.KEY_MOUSE:
			return self.handle_mouse_events(cast(curses.window, self.listpad), self.sorted_list, self.activatedfun, self.extraref, self.data), {}

		if c in (curses.KEY_ENTER, 10, 13) and self.activatedfun is not None:
			return self.enter_handler(self.activatedfun, self.extraref, self.data), {}

		# First generate a list of all the shortcuts we should check
		__shortcuts = {}

		# We *always* add the shortcut to exit the program
		__shortcuts["Exit program"] = __common_shortcuts["Exit program"]

		# Now iterate the list of common shortcuts in the shortcuts dict
		for shortcut_name in deep_get(shortcuts, DictPath("__common_shortcuts"), []):
			if shortcut_name not in __common_shortcuts:
				raise ValueError(f"Common shortcut {shortcut_name} is not defined in __common_shortcuts; this is a programming error.")
			__shortcuts[shortcut_name] = deep_get(__common_shortcuts, DictPath(shortcut_name))

		# Finally add all the remaining shortcuts
		for shortcut_name, shortcut_data in shortcuts.items():
			# We've already dealt with this
			if shortcut_name == "__common_shortcuts":
				continue
			__shortcuts[shortcut_name] = shortcut_data

		# Now generate helptext
		helptext = self.generate_helptext(__shortcuts, **kwargs)

		for shortcut_name, shortcut_data in __shortcuts.items():
			keys = deep_get(shortcut_data, DictPath("shortcut"), [])
			if isinstance(keys, int):
				keys = [keys]

			if c in keys:
				action = deep_get(shortcut_data, DictPath("action"))
				action_call = deep_get(shortcut_data, DictPath("action_call"))
				_action_args = deep_get(shortcut_data, DictPath("action_args"), {})
				action_args: Dict = {**kwargs, **_action_args}
				action_args["__keypress"] = c
				action_args["helptext"] = helptext
				if action == "key_callback":
					return action_call(**action_args)

		return retval, {}
