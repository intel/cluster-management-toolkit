#! /usr/bin/env python3

"""
This module parses command line options and generate helptexts
"""

import errno
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import about

from ikttypes import DictPath, FilePath

from iktlib import deep_get
from iktprint import themearray_len, iktprint, init_iktprint

programname = None
programversion = None
programdescription = None
programauthors = None

commandline = None

# pylint: disable-next=unused-arguments
def __version(options: List[Tuple[str, str]], args: List[str]) -> int:
	"""
	Display version information

		Parameters:
			options (list[(str, str)]): Unused
			args (dict): Unused

		Returns:
			0
	"""

	iktprint([(f"{programname} ", "programname"), (f"{programversion}", "version")])
	iktprint([(f"{about.PROGRAM_SUITE_FULL_NAME} ({about.PROGRAM_SUITE_NAME}) ", "programname"), (f"{about.PROGRAM_SUITE_VERSION}", "version")])
	print()
	print(about.COPYRIGHT)
	print(about.LICENSE)
	print()
	print(programauthors)
	return 0

# pylint: disable-next=unused-arguments
def __usage(options: List[Tuple[str, str]], args: List[str]) -> int:
	"""
	Display usage information

		Parameters:
			options (list[(str, str)]): Unused
			args (dict): Unused

		Returns:
			0
	"""

	assert commandline is not None

	has_commands: bool = False
	has_options: bool = False
	has_args: bool = False

	maxlen = 0
	commands = []
	commandcount = 0
	globaloptioncount = 0

	for key, value in commandline.items():
		if key in ("__default", "extended_description") or key.startswith("spacer"):
			continue

		if key.startswith("__"):
			globaloptioncount += 1
		else:
			commandcount += 1

		if deep_get(commandline, DictPath(f"{key}#options")) is not None:
			has_options = True

		if deep_get(commandline, DictPath(f"{key}#max_args"), 0) > 0:
			has_args = True

	if commandcount > 2 or globaloptioncount == 0:
		has_commands = True
	else:
		has_options = True

	headerstring = [(f"{programname}", "programname")]
	if has_commands == True:
		headerstring += [(" COMMAND", "command")]
	if has_options == True:
		headerstring += [(" [", "separator"), ("OPTION", "option"), ("]", "separator"), ("...", "option")]
	if has_args == True:
		headerstring += [(" [", "separator"), ("ARGUMENT", "argument"), ("]", "separator"), ("...", "argument")]

	iktprint(headerstring)
	print()
	iktprint([(programdescription, "description")])
	print()

	if has_commands == True:
		print("Commands:")
	else:
		print("Global Options:")

	for key, value in commandline.items():
		if key in ("__default", "extended_description"):
			continue

		if key.startswith("spacer"):
			commands.append((0, [("", "default")], [("", "default")]))
			continue

		tmp = []
		separator = "|"
		for cmd in deep_get(value, DictPath("command"), []):
			if key.startswith("__"):
				continue

			if len(tmp) > 0:
				tmp.append((f"{separator}", "separator"))
			tmp.append((f"{cmd}", "command"))

		values = deep_get(value, DictPath("values"))
		if values is not None:
			tmp.append((" ", "default"))
			for part in values:
				tmp.append(part)

		tlen = themearray_len(tmp)
		maxlen = max(maxlen, tlen)
		if tlen > 0:
			commands.append((tlen, tmp, deep_get(value, DictPath("description"))))

		for line in deep_get(value, DictPath("extended_description"), []):
			commands.append((0, [("", "default")], line))

		for option in deep_get(value, DictPath("options"), []):
			indent = ""
			if len(tmp) > 0:
				indent = "  "
			tmp2 = [(f"{indent}", "option")]
			if isinstance(option, tuple):
				for _opt in option:
					# The first string is the initial indentation
					if len(tmp2) > 1:
						tmp2.append((f"{separator}", "separator"))
					tmp2.append((f"{_opt}", "option"))
			elif key.startswith("__"):
				tmp2.append((f"  {option}", "option"))
			else:
				tmp2.append((f"{option}", "option"))
			values = deep_get(value, DictPath(f"options#{option}#values"))
			if values is not None:
				tmp2.append((" ", "default"))

				for part in values:
					tmp2.append(part)
			tlen = themearray_len(tmp2)
			maxlen = max(maxlen, tlen)
			description = deep_get(value, DictPath(f"options#{option}#description"))
			if len(indent) > 0:
				description = [(indent, "default")] + description
			commands.append((tlen, tmp2, description))
			for line in deep_get(value, DictPath(f"options#{option}#extended_description"), []):
				if len(indent) > 0:
					commands.append((tlen, [("".ljust(tlen), "default")], [(indent, "default")] + line))
				else:
					commands.append((tlen, [("".ljust(tlen), "default")], line))

	# cmd[0]: unformatted length of command/option
	# cmd[1]: formatted cmd/option
	# cmd[2]: formatted description
	# We cannot do ljust() directly on the string, since it would include the formatting
	for cmd in commands:
		string = cmd[1] + [("".ljust(maxlen - cmd[0] + 2), "default")] + cmd[2]
		iktprint(string)

	if "extended_description" in commandline:
		print()
		for line in deep_get(commandline, DictPath("extended_description"), []):
			iktprint(line)

	return 0

def __find_command(__commandline: Dict, arg: str) -> Tuple[str, Optional[Callable[[Tuple[str, str], List[str]], None]], str, int, int]:
	command = None
	commandname = ""
	min_args = 0
	max_args = 0
	key = ""

	for key, value in __commandline.items():
		if key == "extended_description":
			continue

		for cmd in deep_get(value, DictPath("command"), []):
			if cmd == arg:
				commandname = cmd
				command = deep_get(value, DictPath("callback"))
				min_args = deep_get(value, DictPath("min_args"), 0)
				max_args = deep_get(value, DictPath("max_args"), 0)
				break
		if command is not None:
			break

	return commandname, command, key, min_args, max_args

COMMANDLINEDEFAULTS = {
	"Help": {
		"command": ["help", "--help"],
		"description": [("Display this help and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": __usage,
	},
	"Version": {
		"command": ["version", "--version"],
		"description": [("Output version information and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": __version,
	},
}

# pylint: disable-next=line-too-long
def parse_commandline(__programname: str, __programversion: str, __programdescription: str, __programauthors: str, argv: List[str],
		      __commandline: Dict, default_command: str = None, theme: FilePath = None):
	"""
	Parse the command line

		Parameters:
			__programname (str): The name of the program (used in usage and version information, and in error messages)
			__programversion (str): The version of the program (used in version information)
			__programdescription (str): The description of the program (used in usage information)
			__programauthors (str): The authors of the program (used in version information)
	"""

	global commandline  # pylint: disable=global-statement
	global programname  # pylint: disable=global-statement
	global programversion  # pylint: disable=global-statement
	global programdescription  # pylint: disable=global-statement
	global programauthors  # pylint: disable=global-statement

	i = 1

	programname = __programname
	programversion = __programversion
	programdescription = __programdescription
	programauthors = __programauthors

	commandline = {**__commandline, **COMMANDLINEDEFAULTS}

	if theme is not None:
		init_iktprint(theme)

	commandname = None
	command = None
	key = None
	options = []
	args: List[str] = []
	min_args = 0
	max_args = 0

	while i < len(argv):
		if "\x00" in argv[i]:
			iktprint([(f"{programname}", "programname"), (": argument “", "default"),
				  (argv[i].replace("\x00", "<NUL>"), "command"),
				  ("“ contains NUL-bytes (replaced here);\n", "default"),
				  ("this is either a programming error, a system error, file or memory corruption, ", "default"),
				  ("or a deliberate attempt to bypass security; aborting.", "default")], stderr = True)
			sys.exit(errno.EINVAL)

		# Have we got a command to execute?
		if command is None:
			commandname, command, key, min_args, max_args = __find_command(commandline, argv[i])

			if command is None:
				if default_command is not None:
					commandname, command, key, min_args, max_args = __find_command(commandline, default_command)

				if command is None:
					iktprint([(f"{programname}", "programname"), (": unrecognised command “", "default"), (f"{argv[i]}", "command"), ("“.", "default")], stderr = True)
					iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
					sys.exit(errno.EINVAL)

				# If we defaulted we don't want to consume any options
				continue
		# OK, we have a command, time to check for options
		elif argv[i].startswith("-"):
			if len(args) > 0:
				# I came here to have an argument, but this is an option!
				iktprint([(f"{programname}", "programname"), (": option “", "default"), (f"{argv[i]}", "option"), ("“ found after arguments.", "default")], stderr = True)
				iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
			else:
				# Is this option valid for this command?
				match = None
				__key = key
				for opt in deep_get(commandline, DictPath(f"{__key}#options"), {}):
					if isinstance(opt, str) and argv[i] == opt or isinstance(opt, tuple) and argv[i] in opt:
						match = opt
						break
				# Check global options
				if match is None:
					for opt in deep_get(commandline, DictPath("__global_options#options"), {}):
						if isinstance(opt, str) and argv[i] == opt or isinstance(opt, tuple) and argv[i] in opt:
							__key = "__global_options"
							match = opt
							break

				if match is None:
					iktprint([(f"{programname}", "programname"), (": “", "default"),
						  (f"{commandname}", "command"),
						  ("“ does not support option “", "default"), (f"{argv[i]}", "option"), ("“.", "default")], stderr = True)
					iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
					sys.exit(errno.EINVAL)
				else:
					arg = None
					option = match

					# Does this option require arguments?
					requires_arg = deep_get(commandline, DictPath(f"{__key}#options#{option}#requires_arg"), False)
					if requires_arg == True:
						i += 1
						if i >= len(argv):
							iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{option}", "option"), ("“ requires an argument.", "default")], stderr = True)
							iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
							sys.exit(errno.EINVAL)
						arg = argv[i]

					options.append((option, arg))
		else:
			args.append(argv[i])
		i += 1

	if command is None and default_command is not None:
		commandname, command, key, min_args, max_args = __find_command(commandline, default_command)

	if max_args == 0 and len(args) > 0:
		iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{commandname}", "command"), ("“ does not accept arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) < min_args and min_args != max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"),
			  (f"{commandname}", "command"),
			  (f"“ requires at least {min_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) != min_args and min_args == max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"),
			  (f"{commandname}", "command"),
			  (f"“ requires exactly {min_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) > max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"),
			  (f"{commandname}", "command"),
			  (f"“ requires at most {max_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	# The command was called without any command and no default was defined; this is an error
	if command is None:
		iktprint([(f"{programname}", "programname"), (": missing operand.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	else:
		# Are there implicit options?
		options += deep_get(commandline, DictPath(f"{key}#implicit_options"), [])

	return command, options, args
