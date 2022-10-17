#! /usr/bin/env python3

"""
Format text as themearrays
"""

import re
import sys
import yaml

import iktlib # pylint: disable=unused-import
from iktlib import deep_get, iktconfig, split_msg

def __str_representer(dumper, data):
	"""
	Reformat yaml with |-style str

		Parameters:
			dumper: Opaque type internal to python-yaml
			data: Opaque type internal to python-yaml
		Returns:
			Opaque type internal to python-yaml
	"""

	if "\n" in data:
		return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
	return dumper.represent_scalar("tag:yaml.org,2002:str", data)

def format_binary(lines, **kwargs):
	return [([("Binary file; cannot view", ("types", "generic"))])]

def format_none(lines, **kwargs):
	"""
	Noop formatter; returns the text without syntax highlighting

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	del kwargs

	dumps = []

	if isinstance(lines, str):
		lines = split_msg(lines)

	for line in lines:
		dumps.append([(line, ("types", "generic"))])
	return dumps

def format_yaml_line(line, override_formatting = None):
	"""
	Formats a single line of YAML

		Parameters:
			line (str): A string
			override_formatting (dict): Overrides instead of default YAML-formatting
		Returns:
			themearray: A themearray
	"""

	if override_formatting is None:
		override_formatting = {}

	if isinstance(override_formatting, dict):
		# Since we don't necessarily override all
		# formatting we need to set defaults;
		# doing it here instead of in the code makes
		# it easier to change the defaults of necessary
		generic_format = ("types", "generic")
		comment_format = ("types", "yaml_comment")
		key_format = ("types", "yaml_key")
		value_format = ("types", "yaml_value")
		list_format = ("separators", "yaml_list")
		separator_format = ("types", "generic")
		reference_format = ("types", "yaml_reference")
	elif isinstance(override_formatting, tuple):
		generic_format = override_formatting
		comment_format = override_formatting
		key_format = override_formatting
		value_format = override_formatting
		list_format = ("- ", override_formatting)
		separator_format = override_formatting
		reference_format = override_formatting

	tmpline = []
	if line.lstrip(" ").startswith("#"):
		tmpline += [
			(line, comment_format),
		]
		return tmpline
	if line.lstrip(" ").startswith("- "):
		# Safe
		tmp = re.match(r"^(\s*?)- (.*)", line)
		tmpline += [
			(f"{tmp[1]}", generic_format),
			list_format,
		]
		line = tmp[2]
		if len(line) == 0:
			return tmpline

	if line.endswith(":"):
		if isinstance(override_formatting, dict):
			_key_format = deep_get(override_formatting, f"{line[:-1]}#key", key_format)
		else:
			_key_format = key_format
		tmpline += [
			(f"{line[:-1]}", _key_format),
			(":", separator_format),
		]
	else:
		# Safe
		tmp = re.match(r"^(.*?)(:\s*?)(&|\.|)(.*)", line)
		# pylint: disable-next=line-too-long
		if tmp is not None and (tmp[1].strip().startswith("\"") and tmp[1].strip().endswith("\"") or (not tmp[1].strip().startswith("\"") and not tmp[1].strip().endswith("\""))):
			key = tmp[1]
			reference = tmp[2]
			separator = tmp[3]
			value = tmp[4]
			if isinstance(override_formatting, dict):
				_key_format = deep_get(override_formatting, f"{key.strip()}#key", key_format)
				if value.strip() in ("{", "["):
					_value_format = value_format
				else:
					_value_format = deep_get(override_formatting, f"{key.strip()}#value", value_format)
			else:
				_key_format = key_format
				_value_format = value_format
			tmpline += [
				(f"{key}", _key_format),
				(f"{separator}", separator_format),
				(f"{reference}", reference_format),
				(f"{value}", _value_format),
			]
		else:
			if isinstance(override_formatting, dict):
				_value_format = deep_get(override_formatting, f"{line}#value", value_format)
			else:
				_value_format = value_format
			tmpline += [
				(f"{line}", _value_format),
			]

	return tmpline

def format_yaml(objects, override_formatting = None, **kwargs):
	"""
	YAML formatter; returns the text with syntax highlighting for YAML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	if override_formatting is None:
		override_formatting = {}

	dumps = []
	indent = deep_get(iktconfig, "Global#indent", 2)

	if isinstance(objects, str):
		objects = [objects]

	generic_format = ("types", "generic")

	if deep_get(kwargs, "raw", False) == True:
		override_formatting = generic_format

	yaml.add_representer(str, __str_representer)

	for i, obj in enumerate(objects):
		if isinstance(obj, dict):
			split_dump = yaml.dump(obj, default_flow_style = False, indent = indent, width = sys.maxsize).splitlines()
		else:
			split_dump = obj.splitlines()
		first = True
		if len(split_dump) > 0 and "\n" not in obj and split_dump[0].startswith("'") and split_dump[0].endswith("'"):
			split_dump[0] = split_dump[0][1:-1]

		for line in split_dump:
			truncated = False

			if len(line) >= 16384 - len(" [...] (Truncated)") - 1:
				line = line[0:16384 - len(" [...] (Truncated)") - 1]
				truncated = True
			# This allows us to use the yaml formatter for json too
			if first == True:
				first = False
				if line in ("|", "|-"):
					continue
			if len(line) == 0:
				continue

			tmpline = format_yaml_line(line, override_formatting = override_formatting)
			if truncated == True:
				tmpline += [(" [...] (Truncated)", ("types", "yaml_key_error"))]
			dumps.append(tmpline)

		if i < len(objects) - 1:
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])
			dumps.append([("", generic_format)])

	return dumps

KEY_HEADERS = [
	"-----BEGIN CERTIFICATE-----",
	"-----END CERTIFICATE-----",
	"-----BEGIN PUBLIC KEY-----",
	"-----END PUBLIC KEY-----",
	"-----BEGIN PRIVATE KEY-----",
	"-----END PRIVATE KEY-----",
	"-----BEGIN DSA PRIVATE KEY-----",
	"-----END DSA PRIVATE KEY-----",
	"-----BEGIN RSA PRIVATE KEY-----",
	"-----END RSA PRIVATE KEY-----",
	"-----BEGIN EC PRIVATE KEY-----",
	"-----END EC PRIVATE KEY-----",
]

def format_crt(lines, **kwargs):
	"""
	CRT formatter; returns the text with syntax highlighting for certificates

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	for line in lines:
		if line in KEY_HEADERS:
			dumps.append([(line, ("types", "separator"))])
		else:
			dumps.append([(line, ("types", "generic"))])
	return dumps

def format_caddyfile(lines, **kwargs):
	"""
	CaddyFile formatter; returns the text with syntax highlighting for CaddyFiles

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	single_site = True
	site = False

	# Safe
	block_open_regex = re.compile(r"^(\s*)({)(.*)")
	# Safe
	snippet_regex = re.compile(r"^(\s*)(\(.+?\))(.*)")
	# Safe
	site_regex = re.compile(r"^(\s*)(\S+?)(\s+{\s*$|$)")
	# Safe
	block_close_regex = re.compile(r"^(\s*)(}\s*$)")
	# Safe
	matcher_regex = re.compile(r"^(\s*)(@.*?|\*/.*?)(\s.*)")
	# Safe
	directive_regex = re.compile(r"^(\s*)(.+?)(\s.*|$)")
	# Safe
	argument_regex = re.compile(r"^(.*?)(\s{\s*$|$)")

	for line in lines:
		tmpline = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				("", ("types", "xml_content")),
			]

		directive = False
		block_depth = 0

		while len(line) > 0:
			# Is this a comment?
			if "#" in line:
				tmpline += [
					(line, ("types", "caddyfile_comment")),
				]
				line = ""
				continue

			# Are we opening a block?
			tmp = block_open_regex.match(line)
			if tmp is not None:
				block_depth += 1
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_block")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_block")),
				]
				line = tmp[3]
				if site == True:
					single_site = False
				continue

			# Is this a snippet?
			tmp = snippet_regex.match(line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_snippet")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_snippet")),
				]
				line = tmp[3]
				continue

			# Is this a site?
			tmp = site_regex.match(line)
			if tmp is not None:
				if block_depth == 0 and site == False and (single_site == True or "{" in tmp[3]):
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "caddyfile_site")),
						]
					tmpline += [
						(tmp[2], ("types", "caddyfile_site")),
					]
					line = tmp[3]
					site = True
					single_site = False
					continue

			# Are we closing a block?
			tmp = block_close_regex.match(line)
			if tmp is not None:
				block_depth -= 1
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_block")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_block")),
				]
				line = ""
				continue

			# Is this a matcher?
			tmp = matcher_regex.match(line)
			if tmp is not None:
				if len(tmp[1]) > 0:
					tmpline += [
						(tmp[1], ("types", "caddyfile_matcher")),
					]
				tmpline += [
					(tmp[2], ("types", "caddyfile_matcher")),
				]
				line = tmp[3]
				continue

			# Is this a directive?
			if directive == False:
				tmp = directive_regex.match(line)
				if tmp is not None:
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "caddyfile_directive")),
						]
					tmpline += [
						(tmp[2], ("types", "caddyfile_directive")),
					]
					line = tmp[3]
					directive = True
					continue
			else:
				# OK, we have a directive already, and this isn't a matcher or a block,
				# which means that it's an argument
				tmp = argument_regex.match(line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "caddyfile_argument")),
					]
					line = tmp[2]
					continue

		dumps.append(tmpline)

	return dumps

def format_nginx(lines, **kwargs):
	"""
	NGINX formatter; returns the text with syntax highlighting for NGINX

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_regex = re.compile(r"^(\s*)(#.*$|}|\S+|$)(.+;|.+{|)(\s*#.*$|)")

	for line in lines:
		dump = []
		if len(line.strip()) == 0:
			if len(dump) == 0:
				dump += [
					("", ("types", "generic"))
				]
			dumps.append(dump)
			continue

		# key {
		# key value[ value...];
		# key value[ value...] {
		tmp = key_regex.match(line)
		if tmp is not None:
			if len(tmp[1]) > 0:
				dump += [
					(tmp[1], ("types", "generic")),	# whitespace
				]
			if len(tmp[2]) > 0:
				if tmp[2] == "}":
					dump += [
						(tmp[2], ("types", "generic")),	# block end
					]
				elif tmp[2].startswith("#"):
					dump += [
						(tmp[2], ("types", "nginx_comment"))
					]
				else:
					dump += [
						(tmp[2], ("types", "nginx_key"))
					]
			if len(tmp[3]) > 0:
				dump += [
					(tmp[3][:-1], ("types", "nginx_value")),
					(tmp[3][-1:], ("types", "generic")),	# block start / statement end
				]
			if len(tmp[4]) > 0:
				dump += [
					(tmp[4], ("types", "nginx_comment"))
				]
			dumps.append(dump)
		else:
			sys.exit(f"__format_nginx(): Couldn't match line={line}")
	return dumps

def format_xml(lines, **kwargs):
	"""
	XML formatter; returns the text with syntax highlighting for XML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []
	tag_open = False
	tag_named = False
	comment = False

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	escape_regex = re.compile(r"^(\s*)(&)(.+?)(;)(.*)")
	# Safe
	content_regex = re.compile(r"^(.*?)(<.*|&.*)")
	# Safe
	tag_open_regex = re.compile(r"^(\s*)(</|<!--|<\?|<)(.*)")
	# Safe
	tag_named_regex = re.compile(r"^(.+?)(\s*>|\s*\?>|\s*$|\s+.*)")
	# Safe
	tag_close_regex = re.compile(r"^(\s*)(/>|\?>|-->|>)(.*)")
	# Safe
	remainder_regex = re.compile(r"^(\s*\S+?)(=|)(\"[^\"]+?\"|)(\s*$|\s*/>|\s*\?>|\s*-->|\s*>|\s+)(.*|)")

	i = 0
	for line in lines:
		tmpline = []

		# Empty line
		if len(line) == 0 and len(tmpline) == 0:
			tmpline = [
				("", ("types", "xml_content")),
			]

		while len(line) > 0:
			before = line
			if tag_open == False:
				# Are we opening a tag?
				tmp = tag_open_regex.match(line)
				if tmp is not None:
					tag_open = True
					tag_named = False

					# Don't add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "xml_declaration")),
						]

					if tmp[2] == "<?":
						# declaration tags are implicitly named
						tag_named = True
						tmpline += [
							(tmp[2], ("types", "xml_declaration")),
						]
						line = tmp[3]
						continue

					if tmp[2] == "<!--":
						comment = True
						tmpline += [
							(tmp[2], ("types", "xml_comment")),
						]
						line = tmp[3]
						continue

					tmpline += [
						(tmp[2], ("types", "xml_tag")),
					]
					line = tmp[3]
					continue

				# Is this an escape?
				tmp = escape_regex.match(line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "xml_content")),
						(tmp[2], ("types", "xml_escape")),
						(tmp[3], ("types", "xml_escape_data")),
						(tmp[4], ("types", "xml_escape")),
					]
					line = tmp[5]
					continue

				# Nope, it's content; split to first & or <
				tmp = content_regex.match(line)
				if tmp is not None:
					tmpline += [
						(tmp[1], ("types", "xml_content")),
					]
					line = tmp[2]
				else:
					tmpline += [
						(line, ("types", "xml_content")),
					]
					line = ""
			else:
				# Are we closing a tag?
				tmp = tag_close_regex.match(line)
				if tmp is not None:
					# Don't add 0-length "indentation"
					if len(tmp[1]) > 0:
						tmpline += [
							(tmp[1], ("types", "xml_comment")),
						]

					# > is ignored within comments
					if tmp[2] == ">" and comment == True or tmp[2] == "-->":
						tmpline += [
							(tmp[2], ("types", "xml_comment")),
						]
						line = tmp[3]
						if tmp[2] == "-->":
							comment = False
							tag_open = False
						continue

					if tmp[2] == "?>":
						tmpline += [
							(tmp[2], ("types", "xml_declaration")),
						]
						line = tmp[3]
						tag_open = False
						continue

					tmpline += [
						(tmp[2], ("types", "xml_tag")),
					]
					line = tmp[3]
					tag_open = False
					continue

				if tag_named == False and comment == False:
					# Is this either "[<]tag", "[<]tag ", "[<]tag>" or "[<]tag/>"?
					tmp = tag_named_regex.match(line)
					if tmp is not None:
						tmpline += [
							(tmp[1], ("types", "xml_tag")),
						]
						line = tmp[2]
						tag_named = True
						continue
				else:
					# This *should* match all remaining cases
					tmp = remainder_regex.match(line)
					if tmp is None:
						raise SyntaxError(f"XML syntax highlighter failed to parse {line}")

					if comment == True:
						tmpline += [
							(tmp[1], ("types", "xml_comment")),
							(tmp[2], ("types", "xml_comment")),
							(tmp[3], ("types", "xml_comment")),
						]
					else:
						tmpline += [
							(tmp[1], ("types", "xml_attribute_key")),
						]

						if len(tmp[2]) > 0:
							tmpline += [
								(tmp[2], ("types", "xml_content")),
								(tmp[3], ("types", "xml_attribute_value")),
							]
					line = tmp[4] + tmp[5]
					continue
			if before == line:
				raise SyntaxError(f"XML syntax highlighter parse failure at line #{i + 1}:\n"
						   "{lines}\n"
						   "Parsed fragments of line:\n"
						   "{tmpline}\n"
						   "Unparsed fragments of line:\n"
						   "{line}")

		dumps.append(tmpline)
		i += 1

	return dumps

def format_toml(lines, **kwargs):
	"""
	TOML formatter; returns the text with syntax highlighting for TOML

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	# FIXME: necessary improvements:
	# * Instead of only checking for lines that end with a comment for key = value,
	#   and for full comment lines, check for lines that end with a comment
	#   in any situation (except multiline). Split out the comment and add it last.
	# * Handle quoting and escaping of quotes; \''' shouldn't end a multiline, for instance.
	# * XXX: should we highlight key=value for inline tables? Probably not
	# * XXX: should we highlight different types (integer, string, etc.)? Almost certainly not.
	dumps = []
	multiline_basic = False
	multiline_literal = False

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S+)(\s*=\s*)(\S+)")
	# Safe
	comment_end_regex = re.compile(r"^(.*)(#.*)")

	for line in lines:
		if len(line) == 0:
			continue

		if multiline_basic == True or multiline_literal == True:
			tmpline += [
				(line, ("types", "toml_value")),
			]
			dumps.append(tmpline)
			if multiline_basic == True and line.lstrip(" ").endswith("\"\"\""):
				multiline_basic = False
			elif multiline_literal == True and line.lstrip(" ").endswith("'''"):
				multiline_literal = False
			continue

		tmpline = []
		if line.lstrip().startswith("#"):
			tmpline += [
				(line, ("types", "toml_comment")),
			]
			dumps.append(tmpline)
			continue

		if line.lstrip().startswith("[") and line.rstrip(" ").endswith("]"):
			tmpline += [
				(line, ("types", "toml_table")),
			]

			dumps.append(tmpline)
			continue

		tmp = key_value_regex.match(line)
		if tmp is not None:
			indentation = tmp[1]
			key = tmp[2]
			separator = tmp[3]
			value = tmp[4]
			if value.rstrip(" ").endswith("\"\"\""):
				multiline_basic = True
			elif value.rstrip(" ").endswith("'''"):
				multiline_literal = True
			else:
				# Does this line end with a comment?
				tmp = comment_end_regex.match(value)
				if tmp is not None:
					value = tmp[1]
					comment = tmp[2]
				else:
					comment = ""
			tmpline += [
				(f"{indentation}", ("types", "generic")),
				(f"{key}", ("types", "toml_key")),
				(f"{separator}", ("types", "toml_key_separator")),
				(f"{value}", ("types", "toml_value")),
			]
			if len(comment) > 0:
				tmpline += [
					(f"{comment}", ("types", "toml_comment")),
				]
			dumps.append(tmpline)
		# dumps.append([(line, ("types", "generic"))])
	return dumps

def format_fluentbit(lines, **kwargs):
	"""
	FluentBit formatter; returns the text with syntax highlighting for FluentBit

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S*)(\s*)(.*)")

	for line in lines:
		if line.lstrip().startswith("#"):
			tmpline = [
				(line, ("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				(line, ("types", "ini_section")),
			]
		elif len(line.strip()) == 0:
			tmpline = [
				("", ("types", "generic")),
			]
		else:
			tmp = key_value_regex.match(line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					(f"{indentation}", ("types", "generic")),
					(f"{key}", ("types", "ini_key")),
					(f"{separator}", ("types", "ini_key_separator")),
					(f"{value}", ("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

def format_ini(lines, **kwargs):
	"""
	INI formatter; returns the text with syntax highlighting for INI

		Parameters:
			lines (list[str]): A list of strings
			*or*
			lines (str): A string with newlines that should be split
			kwargs (dict): Unused
		Returns:
			list[themearray]: A list of themearrays
	"""

	dumps = []

	if deep_get(kwargs, "raw", False) == True:
		return format_none(lines)

	if isinstance(lines, str):
		lines = split_msg(lines)

	# Safe
	key_value_regex = re.compile(r"^(\s*)(\S+)(\s*=\s*)(\S+)")

	for line in lines:
		tmpline = []
		if line.lstrip().startswith(("#", ";")):
			tmpline = [
				(line, ("types", "ini_comment")),
			]
		elif line.lstrip().startswith("[") and line.rstrip().endswith("]"):
			tmpline = [
				(line, ("types", "ini_section")),
			]
		else:
			tmp = key_value_regex.match(line)
			if tmp is not None:
				indentation = tmp[1]
				key = tmp[2]
				separator = tmp[3]
				value = tmp[4]

				tmpline = [
					(f"{indentation}", ("types", "generic")),
					(f"{key}", ("types", "ini_key")),
					(f"{separator}", ("types", "ini_key_separator")),
					(f"{value}", ("types", "ini_value")),
				]
		dumps.append(tmpline)
	return dumps

def map_dataformat(dataformat):
	"""
	Identify what formatter to use, based either on a file ending or an explicit dataformat tag

		Parameters:
			dataformat: The data format *or* the name of the file
		Returns:
			(function reference): The formatter to use
	"""

	if dataformat in ("YAML", "JSON") or dataformat.endswith((".yml", ".yaml", ".json")):
		formatter = format_yaml
	elif dataformat == "TOML" or dataformat.endswith((".toml")):
		formatter = format_toml
	elif dataformat == "CRT" or dataformat.endswith((".crt", "tls.key", ".pem", "CAKey")):
		formatter = format_crt
	elif dataformat == "XML" or dataformat.endswith((".xml")):
		formatter = format_xml
	elif dataformat == "INI" or dataformat.endswith((".ini")):
		formatter = format_ini
	elif dataformat == "FluentBit":
		formatter = format_fluentbit
	elif dataformat == "CaddyFile":
		formatter = format_caddyfile
	elif dataformat == "NGINX":
		formatter = format_nginx
	else:
		formatter = format_none
	return formatter

# Formatters acceptable for direct use in view files
formatter_allowlist = {
	"format_caddyfile": format_caddyfile,
	"format_crt": format_crt,
	"format_fluentbit": format_fluentbit,
	"format_ini": format_ini,
	"format_nginx": format_nginx,
	"format_none": format_none,
	"format_toml": format_toml,
	"format_xml": format_xml,
	"format_yaml": format_yaml,
}
