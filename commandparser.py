#! /usr/bin/env python3

"""
This module parses command line options and generate helptexts
"""

import errno
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
try:
	import validators # type: ignore
except ModuleNotFoundError:
	validators = None

import about

import cmtlib
from ansithemeprint import ANSIThemeString, ansithemeprint, init_ansithemeprint, themearray_len, themearray_ljust, ansithemestring_join_tuple_list
from cmttypes import deep_get, DictPath, FilePath

programname = None
programversion = None
programdescription = None
programauthors = None

commandline = None

def validator_bool(value: Any, error_on_failure: bool = True, exit_on_failure: bool = True) -> Tuple[bool, bool]:
	"""
	Checks whether the value represents a bool.

		Parameters:
			value (any): The representation of value
			error_on_failure (bool): Print an error message on failure
			exit_on_failure (bool): Exit on failure
		Returns:
			result (bool): True if the value can be represented as bool, False if not
			retval (bool): True if value is True, False if value is False
	"""

	result = False

	if isinstance(value, bool):
		result = True
		retval = value
	elif isinstance(value, int):
		if value == 0:
			result = True
			retval = False
		elif value == 1:
			result = True
			retval = True
	elif isinstance(value, str):
		if value.lower() in ("1", "y", "yes", "true"):
			result = True
			retval = True
		elif value.lower() in ("0", "n", "no", "false"):
			result = True
			retval = False

	if result == False:
		if error_on_failure == True:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not a boolean.", "default")], stderr = True)
		if exit_on_failure == True:
			sys.exit(errno.EINVAL)

	return result, retval

def validator_int(minval: int, maxval: int, value: Any, error_on_failure: bool = True, exit_on_failure: bool = True) -> bool:
	"""
	Checks whether value can be represented as an integer,
	and whether it's within the range [min, max].

		Parameters:
			min (int): The minimum value
			max (int): The maximum value
			value (any): The representation of value
			error_on_failure (bool): Print an error message on failure
			exit_on_failure (bool): Exit on failure
		Returns:
			result (bool): True if the value can be represented as int, False if not
	"""

	try:
		value = int(value)
	except ValueError:
		if error_on_failure == True:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not an integer.", "default")], stderr = True)
		if exit_on_failure == True:
			sys.exit(errno.EINVAL)
		return False

	if minval is None:
		minval = -sys.maxsize
		maxval_str = "<any>"
	else:
		minval_str = str(minval)

	if maxval is None:
		maxval = sys.maxsize
		maxval_str = "<any>"
	else:
		maxval_str = str(maxval)

	if minval > maxval:
		raise ValueError("minval > maxval: This is a programming error!")

	if not minval <= int(value) <= maxval:
		if error_on_failure == True:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": “", "default"),
					ANSIThemeString(f"{value}", "option"),
					ANSIThemeString("“ is not in the range [", "default"),
					ANSIThemeString(minval_str, "emphasis"),
					ANSIThemeString(", ", "default"),
					ANSIThemeString(maxval_str, "emphasis"),
					ANSIThemeString("].", "default")], stderr = True)
		if exit_on_failure == True:
			sys.exit(errno.EINVAL)
		return False
	return True

def validate_argument(arg: str, arg_string: List[ANSIThemeString], options: Dict) -> bool:
	"""
	Validate an argument or argument list

		Parameters:
			arg (str): The argument to validate
			arg_string (ansithemearray): A ansithemearray with the formatted representation of the expected data format
			options (dict): Options to pass to the validators
		Returns:
			True on success, False on failure
	"""

	result = False

	validator = deep_get(options, DictPath("validator"), "")
	list_separator = deep_get(options, DictPath("list_separator"))
	minval, maxval = deep_get(options, DictPath("valid_range"), (None, None))
	allowlist = deep_get(options, DictPath("allowlist"), [])
	validator_regex = deep_get(options, DictPath("regex"), r"")

	if list_separator is None:
		arglist = [arg]
	else:
		arglist = arg.split(list_separator)

	for subarg in arglist:
		if validator == "cidr":
			valid = False
			if "/" in subarg:
				ip, netmask = subarg.split("/")
				valid_ipv4_address = validators.ipv4(ip)
				valid_ipv6_address = validators.ipv6(ip)
				try:
					if valid_ipv4_address and 0 < int(netmask) <= 32:
						valid = True
					if valid_ipv6_address and 0 < int(netmask) <= 128:
						valid = True
				except ValueError:
					pass

			if not valid:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is not a valid POD Network CIDR.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
		elif validator == "path":
			if not Path(arg).is_file():
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is not a valid path.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
		elif validator in ("hostname", "hostname_or_path", "hostname_or_ip", "ip"):
			valid_dns_label = cmtlib.validate_name("dns-label", subarg)
			valid_ipv4_address = validators.ipv4(subarg)
			valid_ipv6_address = validators.ipv6(subarg)

			if validator in ("hostname", "hostname_or_path") and not valid_dns_label:
				# If validation failed as subname we check if it's a valid path;
				# this will need deeper checks in the main function
				if validator == "hostname_or_path":
					if Path(arg).is_file():
						break
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is not a valid hostname or path.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
			if validator == "ip" and not valid_ipv4_address and not valid_ipv6_address:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is not a valid IP-address.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
			if validator == "hostname_or_ip" and not valid_dns_label and not valid_ipv4_address and not valid_ipv6_address:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is neither a valid hostname nor a valid IP-address.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
		elif validator in ("taint", "untaint"):
			# Format: dns-subdomain[:dns-label]={NoSchedule,PreferNoSchedule,NoExecute}
			valid = False
			if "=" in subarg:
				key_value, effect = subarg.split("=")
			else:
				key_value = subarg
				effect = ""

			if ":" in key_value:
				key, value = key_value.split(":")
			else:
				key = key_value
				value = ""

			valid_key = cmtlib.validate_name("dns-subdomain", key)
			if len(value) > 0:
				valid_value = cmtlib.validate_name("dns-label", value)
			else:
				valid_value = True

			valid_effect = effect in ("NoSchedule", "PreferNoSchedule", "NoExecute")
			if len(effect) == 0 and validator == "untaint":
				valid_effect = True

			if not valid_key:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{key}", "option"),
						ANSIThemeString("“ is not a valid taint-key.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
			if not valid_value:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{value}", "option"),
						ANSIThemeString("“ is not a valid taint-value.", "default")], stderr = True)
				sys.exit(errno.EINVAL)
			if not valid_effect:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{effect}", "option"),
						ANSIThemeString("“ is not a valid taint-effect.", "default")], stderr = True)
				ansithemeprint([ANSIThemeString("Valid options are: ", "description")], stderr = True)
				ansithemeprint(ansithemestring_join_tuple_list(["NoSchedule", "PreferNoSchedule", "NoExecute"],
									       formatting = "argument", separator = ANSIThemeString(", ", "separator")), stderr = True)
				sys.exit(errno.EINVAL)
		elif validator == "bool":
			_result, _value = validator_bool(subarg)
		elif validator == "int":
			_result = validator_int(minval, maxval, subarg)
		elif validator == "allowlist":
			_result = subarg in allowlist
			if _result is False:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "argument"),
						ANSIThemeString("“ is not a valid argument for ", "default"),
					       ] + arg_string + [ANSIThemeString(".", "default")], stderr = True)
				ansithemeprint([ANSIThemeString("Valid options are: ", "description")], stderr = True)
				ansithemeprint(ansithemestring_join_tuple_list(allowlist, formatting = "argument",
									       separator = ANSIThemeString(", ", "separator")), stderr = True)
				sys.exit(errno.EINVAL)
		elif validator == "regex":
			tmp = re.match(validator_regex, subarg)
			if tmp is None:
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "argument"),
						ANSIThemeString("“ is not a valid argument for ", "default"),
					       ] + arg_string + [ANSIThemeString(".", "default")], stderr = True)
				sys.exit(errno.EINVAL)
		elif validator == "url":
			tmp_arg = subarg
			if not tmp_arg.startswith("http"):
				tmp_arg = f"https://{arg}"

			# Workaround; it seems validators.url accepts usernames that start with "-"
			if arg.startswith("-") or not validators.url(tmp_arg):
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": “", "default"),
						ANSIThemeString(f"{subarg}", "option"),
						ANSIThemeString("“ is not a valid URL.", "default")], stderr = True)
				sys.exit(errno.EINVAL)

	return result

# pylint: disable-next=unused-argument
def __version(options: List[Tuple[str, str]], args: List[str]) -> int:
	"""
	Display version information

		Parameters:
			options (list[(str, str)]): Unused
			args (dict): Unused

		Returns:
			0
	"""

	ansithemeprint([ANSIThemeString(f"{programname} ", "programname"),
			ANSIThemeString(f"{programversion}", "version")])
	ansithemeprint([ANSIThemeString(f"{about.PROGRAM_SUITE_FULL_NAME} ({about.PROGRAM_SUITE_NAME}) ", "programname"),
			ANSIThemeString(f"{about.PROGRAM_SUITE_VERSION}", "version")])
	print()
	print(about.COPYRIGHT)
	print(about.LICENSE)
	print()
	print(programauthors)
	return 0

def __sub_usage(command: str) -> int:
	"""
	Display usage information for a single command

		Parameters:
			command (str): The command to show help for
		Returns:
			0
	"""

	assert commandline is not None

	commandinfo = {}
	headerstring = None

	for _key, value in commandline.items():
		if command in deep_get(value, DictPath("command")):
			commandstring = deep_get(value, DictPath("command_alias"), command)
			headerstring = [ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(f" {commandstring}", "command")]
			commandinfo = value
			break

	if headerstring is None:
		ansithemeprint([ANSIThemeString("Error", "warning"),
				ANSIThemeString(f": Could not find help entry for command {command}; aborting.", "default")], stderr = True)
		sys.exit(errno.ENOENT)

	values = deep_get(commandinfo, DictPath("values"), [])
	options = deep_get(commandinfo, DictPath("options"), [])
	description = deep_get(commandinfo, DictPath("description"), [])
	extended_description = deep_get(commandinfo, DictPath("extended_description"), [])

	if len(options) > 0:
		headerstring += [ANSIThemeString(" [", "separator"),
				 ANSIThemeString("OPTION", "option"),
				 ANSIThemeString("]", "separator"),
				 ANSIThemeString("...", "option")]
	if len(values) > 0:
		headerstring += [ANSIThemeString(" ", "separator")] + values

	ansithemeprint(headerstring)
	print()
	ansithemeprint(description)
	print()
	if len(extended_description) > 0:
		for line in extended_description:
			ansithemeprint([ANSIThemeString("  ", "description")] + line)
		print()

	if len(options) > 0:
		max_optionlen = 0
		for option, optiondata in options.items():
			optionlen = len(option) + 4 + themearray_len(deep_get(optiondata, DictPath("values"), ""))
			max_optionlen = max(max_optionlen, optionlen)

		ansithemeprint([ANSIThemeString("Options:", "description")])
		for option, optiondata in options.items():
			optionline = [ANSIThemeString(f"  {option}", "option")]
			values = deep_get(optiondata, DictPath("values"), [])
			description = deep_get(optiondata, DictPath("description"), [])
			extended_description = deep_get(optiondata, DictPath("extended_description"), [])

			if len(values) > 0:
				optionline += [ANSIThemeString(" ", "option")] + values
			pad = " ".rjust(max_optionlen - themearray_len(optionline))
			optionline += [ANSIThemeString(pad, "description")] + description
			ansithemeprint(optionline)

			pad = " ".rjust(max_optionlen)
			for extended_line in extended_description:
				ansithemeprint([ANSIThemeString(pad, "description")] + extended_line)

	return 0

# pylint: disable-next=unused-argument
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
		if key in ("__default", "__*", "extended_description") or key.startswith("spacer"):
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

	headerstring = [ANSIThemeString(f"{programname}", "programname")]
	if has_commands == True:
		headerstring += [ANSIThemeString(" COMMAND", "command")]
	if has_options == True:
		headerstring += [ANSIThemeString(" [", "separator"),
				 ANSIThemeString("OPTION", "option"),
				 ANSIThemeString("]", "separator"),
				 ANSIThemeString("...", "option")]
	if has_args == True:
		headerstring += [ANSIThemeString(" [", "separator"),
				 ANSIThemeString("ARGUMENT", "argument"),
				 ANSIThemeString("]", "separator"),
				 ANSIThemeString("...", "argument")]

	ansithemeprint(headerstring)
	print()
	ansithemeprint([ANSIThemeString(programdescription, "description")])
	print()

	if has_commands == True:
		print("Commands:")
	else:
		print("Global Options:")

	for key, value in commandline.items():
		if key in ("__default", "extended_description", "__*"):
			continue

		if key.startswith("spacer"):
			commands.append(([ANSIThemeString("", "default")], [ANSIThemeString("", "default")]))
			continue

		tmp = []
		separator = "|"
		for cmd in deep_get(value, DictPath("command"), []):
			if key.startswith("__"):
				continue

			if len(tmp) > 0:
				tmp.append(ANSIThemeString(f"{separator}", "separator"))
			tmp.append(ANSIThemeString(f"{cmd}", "command"))

		values = deep_get(value, DictPath("values"))
		if values is not None:
			tmp.append(ANSIThemeString(" ", "default"))
			for part in values:
				tmp.append(part)

		tlen = themearray_len(tmp)
		maxlen = max(maxlen, tlen)
		if tlen > 0:
			commands.append((tmp, deep_get(value, DictPath("description"))))

		for line in deep_get(value, DictPath("extended_description"), []):
			commands.append(([ANSIThemeString("", "default")], line))

		for option in deep_get(value, DictPath("options"), []):
			indent = ""
			if len(tmp) > 0:
				indent = "  "
			tmp2 = [ANSIThemeString(f"{indent}", "option")]
			if isinstance(option, tuple):
				for _opt in option:
					# The first string is the initial indentation
					if len(tmp2) > 1:
						tmp2.append(ANSIThemeString("  ", "separator"))
					tmp2.append(ANSIThemeString(f"{_opt}", "option"))
			elif key.startswith("__"):
				tmp2.append(ANSIThemeString(f"  {option}", "option"))
			else:
				tmp2.append(ANSIThemeString(f"{option}", "option"))
			values = deep_get(value, DictPath(f"options#{option}#values"))
			if values is not None:
				tmp2.append(ANSIThemeString(" ", "default"))

				for part in values:
					tmp2.append(part)
			tlen = themearray_len(tmp2)
			maxlen = max(maxlen, tlen)
			description = deep_get(value, DictPath(f"options#{option}#description"))
			if len(indent) > 0:
				description = [ANSIThemeString(indent, "default")] + description
			commands.append((tmp2, description))
			for line in deep_get(value, DictPath(f"options#{option}#extended_description"), []):
				if len(indent) > 0:
					commands.append(([ANSIThemeString("", "default")], [ANSIThemeString(indent, "default")] + line))
				else:
					commands.append(([ANSIThemeString("", "default")], line))

	# cmd[0]: formatted cmd/option
	# cmd[1]: formatted description
	for cmd in commands:
		if themearray_len(cmd[0]) > 27 or themearray_len(cmd[0]) + 2 + themearray_len(cmd[1]) > 79 or themearray_len(cmd[1]) > 51:
			ansithemeprint(cmd[0])
			string = themearray_ljust([ANSIThemeString("", "default")], 29) + cmd[1]
			ansithemeprint(string)
			#if themearray_len(string) > 79:
			#	sys.exit(f"FIXME: {themearray_len(string)} > 79 characters; please file a bug report.")
		else:
			string = themearray_ljust(cmd[0], 29) + cmd[1]
			ansithemeprint(string)

	if "extended_description" in commandline:
		print()
		for line in deep_get(commandline, DictPath("extended_description"), []):
			ansithemeprint(line)

	return 0

def __find_command(__commandline: Dict, arg: str) -> Tuple[str, Optional[Callable[[Tuple[str, str], List[str]], None]], str, int, int, List[Dict], List[Dict]]:
	command = None
	commandname = ""
	required_args = []
	optional_args = []
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
				required_args = deep_get(value, DictPath("required_args"), [])
				optional_args = deep_get(value, DictPath("optional_args"), [])
				min_args = deep_get(value, DictPath("min_args"))
				max_args = deep_get(value, DictPath("max_args"))
				if min_args is None:
					min_args = len(required_args)
				if max_args is None:
					max_args = min_args + len(optional_args)
				break
		if command is not None:
			break

	return commandname, command, key, min_args, max_args, required_args, optional_args

COMMANDLINEDEFAULTS = {
	"Help": {
		"command": ["help", "--help"],
		"description": [ANSIThemeString("Display this help and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": __usage,
	},
	"Version": {
		"command": ["version", "--version"],
		"description": [ANSIThemeString("Output version information and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": __version,
	},
}

# pylint: disable-next=line-too-long
def parse_commandline(__programname: str, __programversion: str, __programdescription: str, __programauthors: str, argv: List[str],
		      __commandline: Dict, default_command: Optional[str] = None, theme: Optional[FilePath] = None) -> Tuple[Callable, List[Tuple[str, str]], List[str]]:
	"""
	Parse the command line

		Parameters:
			__programname (str): The name of the program (used in usage and version information, and in error messages)
			__programversion (str): The version of the program (used in version information)
			__programdescription (str): The description of the program (used in usage information)
			__programauthors (str): The authors of the program (used in version information)
		Returns:
			(command, options, args):
				command (callable): The command to call
				options (list[(str, str)]): The options to pass to the command
				args (list[str]): The arguments to pass to the command
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
		init_ansithemeprint(theme)

	commandname = None
	command = None
	key = None
	options: List[Tuple[str, str]] = []
	args: List[str] = []
	min_args = 0
	max_args = 0

	while i < len(argv):
		if "\x00" in argv[i]:
			ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
					ANSIThemeString(": argument “", "default"),
					ANSIThemeString(argv[i].replace("\x00", "<NUL>"), "command"),
					ANSIThemeString("“ contains NUL-bytes (replaced here);\n", "default"),
					ANSIThemeString("this is either a programming error, a system error, file or memory corruption, ", "default"),
					ANSIThemeString("or a deliberate attempt to bypass security; aborting.", "default")], stderr = True)
			sys.exit(errno.EINVAL)

		# Have we got a command to execute?
		if command is None:
			commandname, command, key, min_args, max_args, required_args, optional_args = __find_command(commandline, argv[i])

			if command is None:
				if default_command is not None:
					commandname, command, key, min_args, max_args, required_args, optional_args = __find_command(commandline, default_command)
				elif "__*" in commandline:
					commandname, command, key, min_args, max_args, required_args, optional_args = __find_command(commandline, "*")

				if command is None:
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": unrecognised command “", "default"),
							ANSIThemeString(f"{argv[i]}", "command"),
							ANSIThemeString("“.", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("Try “", "default"),
							ANSIThemeString(f"{programname} ", "programname"),
							ANSIThemeString("help", "command"),
							ANSIThemeString("“ for more information.", "default")], stderr = True)
					sys.exit(errno.EINVAL)

				# If we defaulted we do not want to consume any options
				continue
		# OK, we have a command, time to check for options
		elif argv[i].startswith("-"):
			# All commands except [--]help and [--]version have their own help pages
			if argv[i] == "--help" and commandname not in ("--help", "help", "--version", "version") and not commandname.startswith("__"):
				__sub_usage(commandname)
				sys.exit()

			if len(args) > 0:
				# I came here to have an argument, but this is an option!
				ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
						ANSIThemeString(": option “", "default"),
						ANSIThemeString(f"{argv[i]}", "option"),
						ANSIThemeString("“ found after arguments.", "default")], stderr = True)
				ansithemeprint([ANSIThemeString("Try “", "default"),
						ANSIThemeString(f"{programname} ", "programname"),
						ANSIThemeString("help", "command"),
						ANSIThemeString("“ for more information.", "default")], stderr = True)
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
					ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
							ANSIThemeString(": “", "default"),
							ANSIThemeString(f"{commandname}", "command"),
							ANSIThemeString("“ does not support option “", "default"),
							ANSIThemeString(f"{argv[i]}", "option"),
							ANSIThemeString("“.", "default")], stderr = True)
					ansithemeprint([ANSIThemeString("Try “", "default"),
							ANSIThemeString(f"{programname} ", "programname"),
							ANSIThemeString("help", "command"),
							ANSIThemeString("“ for more information.", "default")], stderr = True)
					sys.exit(errno.EINVAL)
				else:
					arg = None
					option = match

					# Does this option require arguments?
					requires_arg = deep_get(commandline, DictPath(f"{__key}#options#{option}#requires_arg"), False)

					if requires_arg == True:
						i += 1
						if i >= len(argv):
							ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
									ANSIThemeString(": “", "default"),
									ANSIThemeString(f"{option}", "option"),
									ANSIThemeString("“ requires an argument.", "default")], stderr = True)
							ansithemeprint([ANSIThemeString("Try “", "default"),
									ANSIThemeString(f"{programname} ", "programname"),
									ANSIThemeString("help", "command"),
									ANSIThemeString("“ for more information.", "default")], stderr = True)
							sys.exit(errno.EINVAL)
						arg = argv[i]

					# Validate the option argument
					validator_options = deep_get(commandline, DictPath(f"{__key}#options#{option}#validation"), {})

					# validate_argument() will terminate by default if validation fails
					_result = validate_argument(arg, [ANSIThemeString(f"{option}", "option")], validator_options)
					options.append((option, arg))
		else:
			args.append(argv[i])
		i += 1

	if command is None and default_command is not None:
		commandname, command, key, min_args, max_args, required_args, optional_args = __find_command(commandline, default_command)

	if max_args == 0 and len(args) > 0:
		ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
				ANSIThemeString(": “", "default"),
				ANSIThemeString(f"{commandname}", "command"),
				ANSIThemeString("“ does not accept arguments.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("Try “", "default"),
				ANSIThemeString(f"{programname} ", "programname"),
				ANSIThemeString("help", "command"),
				ANSIThemeString("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) < min_args and min_args != max_args:
		ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
				ANSIThemeString(": “", "default"),
				ANSIThemeString(f"{commandname}", "command"),
				ANSIThemeString(f"“ requires at least {min_args} arguments.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("Try “", "default"),
				ANSIThemeString(f"{programname} ", "programname"),
				ANSIThemeString("help", "command"),
				ANSIThemeString("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) != min_args and min_args == max_args:
		ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
				ANSIThemeString(": “", "default"),
				ANSIThemeString(f"{commandname}", "command"),
				ANSIThemeString(f"“ requires exactly {min_args} arguments.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("Try “", "default"),
				ANSIThemeString(f"{programname} ", "programname"),
				ANSIThemeString("help", "command"),
				ANSIThemeString("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	elif len(args) > max_args:
		ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
				ANSIThemeString(": “", "default"),
				ANSIThemeString(f"{commandname}", "command"),
				ANSIThemeString(f"“ requires at most {max_args} arguments.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("Try “", "default"),
				ANSIThemeString(f"{programname} ", "programname"),
				ANSIThemeString("help", "command"),
				ANSIThemeString("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)

	# The command was called without any command and no default was defined; this is an error
	if command is None:
		ansithemeprint([ANSIThemeString(f"{programname}", "programname"),
				ANSIThemeString(": missing operand.", "default")], stderr = True)
		ansithemeprint([ANSIThemeString("Try “", "default"),
				ANSIThemeString(f"{programname} ", "programname"),
				ANSIThemeString("help", "command"),
				ANSIThemeString("“ for more information.", "default")], stderr = True)
		sys.exit(errno.EINVAL)
	else:
		# Are there implicit options?
		options += deep_get(commandline, DictPath(f"{key}#implicit_options"), [])

	# Validate the args against required_args and optional_args
	for i, arg in enumerate(required_args + optional_args):
		if i >= len(args):
			break

		# Validate the argument
		validator_options = deep_get(arg, DictPath("validation"), {})

		# validate_argument() will terminate by default if validation fails
		_result = validate_argument(args[i], arg["string"], validator_options)

	return command, options, args
