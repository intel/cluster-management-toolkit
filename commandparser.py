#! /usr/bin/env python3
import sys

import about
from iktprint import iktprint, init_iktprint

programname = None
programversion = None
programdescription = None
programauthors = None

commandline = None

def themearray_len(themearray):
	tlen = 0
	for _str, _format in themearray:
		tlen += len(_str)
	return tlen

def version(options = None, args = None):
	iktprint([(f"{programname} ", "programname"), (f"{programversion}", "version")])
	iktprint([(f"{about.program_suite_full_name} ({about.program_suite_name}) ", "programname"), (f"{about.program_suite_version}", "version")])
	print()
	print(about.copyright)
	print(about.license)
	print()
	print(programauthors)
	return 0

def usage(options = None, args = None):
	has_commands = False
	has_options = False
	has_args = False

	maxlen = 0
	commands = []
	commandcount = 0
	globaloptioncount = 0

	for key, value in commandline.items():
		if key in ["__default", "extended_description"] or key.startswith("spacer"):
			continue
		elif key.startswith("__"):
			globaloptioncount += 1
		else:
			commandcount += 1

		if commandline[key].get("options") is not None:
			has_options = True

		if commandline[key].get("max_args", 0) > 0:
			has_args = True

	if commandcount > 2 or globaloptioncount == 0:
		has_commands = True
	else:
		has_options = True

	headerstring = [(f"{programname}", "programname")]
	if has_commands == True:
		headerstring += [(" COMMAND", "command")]
	if has_options == True:
		headerstring += [(" [", "separator"), ("OPTIONS", "option"), ("]", "separator"), ("...", "option")]
	if has_args == True:
		headerstring += [(" [", "separator"), ("ARGUMENTS", "argument"), ("]", "separator"), ("...", "argument")]

	iktprint(headerstring)
	print()
	iktprint([(programdescription, "description")])
	print()

	if has_commands == True:
		print("Commands:")
	else:
		print("Options:")

	for key, value in commandline.items():
		if key in ["__default", "extended_description"]:
			continue

		if key.startswith("spacer"):
			commands.append((0, [("", "default")], [("", "default")]))
			continue

		tmp = []
		separator = "|"
		for cmd in value["command"]:
			if key.startswith("__"):
				continue

			if len(tmp) > 0:
				tmp.append((f"{separator}", "separator"))
			tmp.append((f"{cmd}", "command"))

		values = value.get("values")
		if values is not None:
			tmp.append((" ", "default"))
			for part in values:
				tmp.append(part)

		tlen = themearray_len(tmp)
		maxlen = max(maxlen, tlen)
		if tlen > 0:
			commands.append((tlen, tmp, value["description"]))

		if value.get("extended_description") is not None:
			for line in value["extended_description"]:
				commands.append((0, [("", "default")], line))

		if value.get("options") is not None:
			for option in value["options"]:
				indent = ""
				if len(tmp) > 0:
					indent = "  "
				tmp2 = [(f"{indent}", "option")]
				if type(option) == tuple:
					i = 0
					for i in range(0, len(option)):
						# The first string is the initial indentation
						if len(tmp2) > 1:
							tmp2.append((f"{separator}", "separator"))
						tmp2.append((f"{option[i]}", "option"))
				else:
					tmp2.append((f"{option}", "option"))
				values = value["options"][option].get("values")
				if values is not None:
					tmp2.append((" ", "default"))

					for part in values:
						tmp2.append(part)
				tlen = themearray_len(tmp2)
				maxlen = max(maxlen, tlen)
				description = value["options"][option]["description"]
				if len(indent) > 0:
					description = [(indent, "default")] + description
				commands.append((tlen, tmp2, description))

	# cmp[0]: unformatted length of command/option
	# cmd[1]: formatted cmd/option
	# cmp[2]: formatted description
	# We cannot do ljust() directly on the string, since it would include the formatting
	for cmd in commands:
		string = cmd[1] + [("".ljust(maxlen - cmd[0] + 2), "default")] + cmd[2]
		iktprint(string)

	if "extended_description" in commandline:
		print()
		for line in commandline["extended_description"]:
			iktprint(line)

	return 0

def __find_command(commandline, arg):
	command = None
	commandname = None
	min_args = 0
	max_args = 0
	key = None

	for key, value in commandline.items():
		if key == "extended_description":
			continue

		for cmd in value["command"]:
			if cmd == arg:
				commandname = cmd
				command = value["callback"]
				min_args = value.get("min_args", 0)
				max_args = value.get("max_args", 0)
				break
		if command is not None:
			break

	return commandname, command, key, min_args, max_args

commandlinedefaults = {
	"Help": {
		"command": ["help", "--help"],
		"description": [("Display this help and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": usage,
	},
	"Version": {
		"command": ["version", "--version"],
		"description": [("Output version information and exit", "description")],
		"min_args": 0,
		"max_args": 0,
		"callback": version,
	},
}

def parse_commandline(__programname, __programversion, __programdescription, __programauthors, argv, __commandline, default_command = None, theme = None):
	global commandline
	global programname
	global programversion
	global programdescription
	global programauthors

	i = 1

	programname = __programname
	programversion = __programversion
	programdescription = __programdescription
	programauthors = __programauthors

	commandline = {**__commandline, **commandlinedefaults}

	if theme is not None:
		init_iktprint(theme)

	commandname = None
	command = None
	key = None
	options = []
	args = []
	min_args = 0
	max_args = 0

	while i < len(argv):
		# Have we got a command to execute?
		if command is None:
			commandname, command, key, min_args, max_args = __find_command(commandline, argv[i])

			if command is None:
				if default_command is not None:
					commandname, command, key, min_args, max_args = __find_command(commandline, default_command)

				if command is None:
					iktprint([(f"{programname}", "programname"), (": unknown command “", "default"), (f"{argv[i]}", "command"), ("“.", "default")], stderr = True)
					iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
					sys.exit(2)
		# OK, we have a command, time to check for options
		elif argv[i].startswith("-"):
			if len(args) > 0:
				# I came here to have an argument, but this is an option!
				iktprint([(f"{programname}", "programname"), (": option “", "default"), (f"{argv[i]}", "option"), ("“ found after arguments.", "default")], stderr = True)
				iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
				sys.exit(2)
			else:
				# Is this option valid for this command?
				match = None
				for opt in commandline[key].get("options"):
					if type(opt) is str and argv[i] == opt or type(opt) is tuple and argv[i] in opt:
						match = opt
						break

				if match is None:
					iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{commandname}", "command"), ("“ does not support option “", "default"), (f"{argv[i]}", "option"), ("“.", "default")], stderr = True)
					iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
					sys.exit(2)
				else:
					arg = None
					option = match

					# Does this option require arguments?
					requires_arg = commandline[key]["options"][option].get("requires_arg")
					if requires_arg is not None and requires_arg == True:
						i += 1
						if i >= len(argv):
							iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{option}", "option"), ("“ requires an argument.", "default")], stderr = True)
							iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
							sys.exit(2)
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
		sys.exit(2)
	elif len(args) < min_args and min_args != max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{commandname}", "command"), (f"“ requires at least {min_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(2)
	elif len(args) != min_args and min_args == max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{commandname}", "command"), (f"“ requires exactly {min_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(2)
	elif len(args) > max_args:
		iktprint([(f"{programname}", "programname"), (": “", "default"), (f"{commandname}", "command"), (f"“ requires at most {max_args} arguments.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(2)

	# The command was called without any command and no default was defined; this is an error
	if command is None:
		iktprint([(f"{programname}", "programname"), (": missing operand.", "default")], stderr = True)
		iktprint([("Try “", "default"), (f"{programname} ", "programname"), ("help", "command"), ("“ for more information.", "default")], stderr = True)
		sys.exit(2)
	else:
		# Are there implicit options?
		implicit_options = commandline[key].get("implicit_options")
		if implicit_options is not None:
			options += implicit_options

	return command, options, args
