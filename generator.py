#! /usr/bin/env python3

"""
This generates elements for various more complex types
"""

# pylint: disable=too-many-arguments

from datetime import datetime
from typing import cast, List, Tuple, Union

from curses_helper import color_status_group, themearray_len, themearray_to_string
import iktlib
from iktlib import datetime_to_timestamp, deep_get, deep_get_with_fallback, timestamp_to_datetime
from ikttypes import DictPath, StatusGroup, ThemeAttr, ThemeRef, ThemeString

def format_list(items, fieldlen, pad, ralign, selected,
		item_separator = None,
		field_separators = None,
		field_colors = None,
		ellipsise: int = -1,
		ellipsis = None,
		field_prefixes = None,
		field_suffixes = None,
		mapping = None):
	array: List[Tuple[Union[ThemeRef, ThemeString], bool]] = []
	totallen = 0

	if item_separator == None:
		item_separator = ThemeRef("separators", "list")

	if ellipsis is None:
		ellipsis = ThemeRef("separators", "ellipsis")

	if field_separators is None:
		field_separators = [ThemeRef("separators", "field")]

	if field_colors is None:
		field_colors = [ThemeAttr("types", "generic")]

	if not isinstance(field_separators, list):
		raise Exception(f"field_separators should be a list of (context, style) tuple, not a single tuple; {field_separators}")

	if not isinstance(field_colors, list):
		raise Exception(f"field_colors should be a list of (context, style) tuple, not a single tuple; {field_colors}")

	if not isinstance(items, list):
		items = [items]

	if mapping is None:
		mapping = {}

	elcount = 0
	skip_separator = True

	for item in items:
		if len(array) > 0:
			totallen += themearray_len([item_separator])
			array.append((item_separator, selected))
			elcount += 1

		if elcount == ellipsise:
			array.append((ellipsis, selected))
			break

		# Treat all types as tuples no matter if they are; since tuples consist of 2+ elements we add None
		if not isinstance(item, tuple):
			item = (item, None)

		for i in range(0, len(item)):
			if item[i] is None:
				continue

			string = str(item[i])

			if len(string) == 0:
				continue

			if i > 0 and skip_separator == False:
				field_separator = field_separators[min(i - 1, len(field_separators) - 1)]
				totallen += themearray_len([field_separator])
				array.append((field_separator, selected))

			if string == "<none>":
				fmt = ThemeAttr("types", "none")
				formatted_string = ThemeString(string, fmt, selected)
			elif string == "<not ready>":
				fmt = color_status_group(StatusGroup.NOT_OK)
				formatted_string = ThemeString(string, fmt, selected)
			else:
				default_field_color = cast(ThemeAttr, field_colors[min(i, len(field_colors) - 1)])
				formatted_string, __string = map_value(string, selected = selected, default_field_color = default_field_color, mapping = mapping)

			# OK, we know now that we'll be appending the field, so do the prefix
			if field_prefixes is not None and i < len(field_prefixes):
				if isinstance(field_prefixes[i], tuple):
					totallen += themearray_len([field_prefixes[i]])
					array.append(field_prefixes[i])
				else:
					for prefix in field_prefixes[i]:
						totallen += themearray_len([prefix])
						array.append((prefix, selected))
			array.append((formatted_string))
			totallen += len(string)
			# And now the suffix
			if field_suffixes is not None and i < len(field_suffixes):
				if isinstance(field_suffixes[i], tuple):
					totallen += themearray_len([field_suffixes[i]])
					array.append(field_suffixes[i])
				else:
					for suffix in field_suffixes[i]:
						totallen += themearray_len([suffix])
						array.append((suffix, selected))
				# RequestPrincipals[*@example.com]
			skip_separator = False

	return align_and_pad(array, pad, fieldlen, totallen, ralign, selected)

# references is unused for now, but will eventually be used to compare against
# reference values (such as using other paths to get the range, instead of getting
# it static from formatting#mapping)
# pylint: disable=unused-argument
def map_value(value, references = None, selected: bool = False, default_field_color: ThemeAttr = ThemeAttr("types", "generic"), mapping = None):
	# If we lack a mapping, use the default color for this field
	if mapping is None or len(mapping) == 0:
		context, attr_ref = default_field_color
		fmt = (context, attr_ref)
		return (value, fmt, selected), value

	substitutions = deep_get(mapping, DictPath("substitutions"), {})
	ranges = deep_get(mapping, DictPath("ranges"), [])
	match_case = deep_get(mapping, DictPath("match_case"), True)
	_mapping = deep_get(mapping, DictPath("mappings"), {})

	field_colors = None

	if value in substitutions:
		# We don't need to check for bool, since it's a subclass of int
		if isinstance(value, int):
			value = substitutions[f"__{str(value)}"]
		else:
			value = substitutions[value]

		# If the substitution is a dict it's a themearray; typically either a separator or a string
		if isinstance(value, (ThemeRef, dict)):
			context = deep_get(value, DictPath("context"), "main")
			attr_ref = deep_get(value, DictPath("type"))
			return ((context, attr_ref), selected), themearray_to_string([(context, attr_ref)])

	# OK, so we want to output output_value, but compare using reference_value
	if isinstance(value, tuple) and len(ranges) > 0:
		output_value, reference_value = value
	else:
		output_value = value
		reference_value = value

	if isinstance(reference_value, (int, float)) and len(ranges) > 0:
		default_index = -1
		for i in range(0, len(ranges)):
			if deep_get(ranges[i], DictPath("default"), False) == True:
				if default_index != -1:
					raise ValueError("Range cannot contain more than one default")
				default_index = i
				continue
			_min = deep_get(ranges[i], DictPath("min"))
			_max = deep_get(ranges[i], DictPath("max"))
			if (_min is None or reference_value >= _min) and (_max is None or reference_value < _max):
				field_colors = deep_get(ranges[i], DictPath("field_colors"))
				break
		if field_colors is None and default_index != -1:
			field_colors = deep_get(ranges[default_index], DictPath("field_colors"))
		string = str(output_value)
	elif isinstance(reference_value, (str, bool)) or len(ranges) == 0:
		string = str(output_value)
		_string = string
		if match_case is False:
			matched = False
			if string in _mapping and string.lower() in _mapping and string != string.lower():
				raise ValueError("When using match_case == False the mapping cannot contain keys that only differ in case")
			for key in _mapping:
				if key.lower() == string.lower():
					_string = key
				matched = True
			if matched == False and "__default" in _mapping:
				_string = "__default"
		elif _string not in _mapping and "__default" in _mapping:
			_string = "__default"
		field_colors = deep_get(_mapping, DictPath(f"{_string}#field_colors"))
	else:
		raise TypeError(f"Unknown type {type(value)} for mapping/range")

	attr_ref = None
	if field_colors is not None:
		context = deep_get(field_colors[0], DictPath("context"), "main")
		attr_ref = deep_get(field_colors[0], DictPath("type"))
	if attr_ref is None:
		context, attr_ref = ("types", "generic")
	fmt = (context, attr_ref)
	return (string, fmt, selected), string

def align_and_pad(array, pad: int, fieldlen: int, stringlen: int, ralign: bool, selected: bool):
	if selected is None:
		if ralign:
			array = [("".ljust(fieldlen - stringlen), ("types", "generic"))] + array
		else:
			array.append(("".ljust(fieldlen - stringlen), ("types", "generic")))
		if pad > 0:
			array.append(("separators", "pad"))
	else:
		if ralign:
			array = [("".ljust(fieldlen - stringlen), ("types", "generic", selected))] + array
		else:
			array.append(("".ljust(fieldlen - stringlen), ("types", "generic", selected)))
		if pad > 0:
			array.append((("separators", "pad"), selected))
	return array

def format_numerical_with_units(string: str, ftype: str, selected: bool, non_units = None, separator_lookup = None) -> List[Union[ThemeRef, ThemeString]]:
	substring = ""
	array = []
	numeric = None
	# This is necessary to be able to use pop
	liststring = list(string)

	if separator_lookup is None:
		separator_lookup = {}

	if "default" not in separator_lookup:
		separator_lookup["default"] = ThemeAttr("types", "unit")

	if non_units is None:
		non_units = set("0123456789")
	else:
		non_units = set(non_units)

	while len(liststring) > 0:
		char = liststring.pop(0)
		if numeric is None:
			numeric = char in non_units
			substring += char
		elif numeric == True:
			# Do we need to flush?
			if not char in non_units:
				if selected is None:
					array.append(ThemeString(substring, ThemeAttr("types", ftype)))
				else:
					array.append(ThemeString(substring, ThemeAttr("types", ftype), selected))
				substring = ""
				numeric = False

			substring += char
		else:
			# Do we need to flush?
			if char in non_units:
				fmt = cast(ThemeAttr, deep_get_with_fallback(separator_lookup, [DictPath(substring), DictPath("default")]))
				if selected is None:
					array.append(ThemeString(substring, fmt))
				else:
					array.append(ThemeString(substring, fmt, selected))
				substring = ""
				numeric = True
			substring += char

		if len(liststring) == 0:
			if numeric == True:
				if selected is None:
					array.append(ThemeString(substring, ThemeAttr("types", ftype)))
				else:
					array.append(ThemeString(substring, ThemeAttr("types", ftype), selected))
			else:
				fmt = cast(ThemeAttr, deep_get_with_fallback(separator_lookup, [DictPath(substring), DictPath("default")]))
				if selected is None:
					array.append(ThemeString(substring, fmt))
				else:
					array.append(ThemeString(substring, fmt, selected))

	if len(array) == 0:
		array = [ThemeString("", ThemeAttr("types", "generic"), selected)]

	return array

def generator_age_raw(value, selected: bool) -> List[ThemeString]:
	if value == -1:
		string = ""
	elif isinstance(value, str):
		string = value
	else:
		string = iktlib.seconds_to_age(value, negative_is_skew = True)

	if string in ("<none>", "<unset>", "<unknown>"):
		fmt = ThemeAttr("types", "none")
		array = [ThemeString(string, fmt, selected)]
	elif string == "<clock skew detected>":
		fmt = ThemeAttr("main", "status_not_ok")
		array = [ThemeString(string, fmt, selected)]
	else:
		array = format_numerical_with_units(string, "age", selected)

	return array

# pylint: disable=unused-argument
def generator_age(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)

	array = generator_age_raw(value, selected)

	return align_and_pad(array, pad, fieldlen, themearray_len(array), ralign, selected)

def generator_address(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	items = getattr(obj, field, [])
	if items is None:
		items = []

	if isinstance(items, str) and items in ("<unset>", "<none>"):
		return format_list([items], fieldlen, pad, ralign, selected)

	if isinstance(items, (str, tuple)):
		items = [items]

	separator_lookup = {}

	separators = deep_get(formatting, DictPath("field_separators"))
	if len(separators) == 0:
		separators = [("separators", "ipv4address"), ("separators", "ipv6address"), ("separators", "ipmask")]

	for separator in separators:
		string = themearray_to_string([separator])
		separator_lookup[string] = separator

	vlist = []
	field_colors = []
	field_separators = []

	subnet = False
	first = True

	for item in items:
		_vlist = []
		tmp = ""
		for ch in item:
			if ch in separator_lookup:
				_vlist.append(tmp)
				if first == True:
					if subnet == True:
						field_colors.append(("types", "ipmask"))
					else:
						field_colors.append(("types", "address"))
					field_separators.append(separator_lookup[ch])
				tmp = ""

				if ch == "/":
					subnet = True
			else:
				tmp += ch

		if len(tmp) > 0:
			_vlist.append(tmp)
			if first == True:
				if subnet == True:
					field_colors.append(("types", "ipmask"))
				else:
					field_colors.append(("types", "address"))
		first = False
		vlist.append(tuple(_vlist))

	return format_list(vlist, fieldlen, pad, ralign, selected, field_separators = field_separators, field_colors = field_colors)

def generator_basic(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)
	string = str(value)
	field_colors = deep_get(formatting, DictPath("field_colors"), [("types", "generic")])

	if string == "None":
		string = "<none>"

	if string in ("<none>", "<unknown>"):
		fmt = ("types", "none")
	elif string == "<default>":
		fmt = ("types", "default")
	elif string == "<undefined>":
		fmt = ("types", "undefined")
	elif string == "<unset>":
		fmt = ("types", "unset")
	else:
		context, attr_ref = field_colors[0]
		fmt = (context, attr_ref)

	array = [
		(string, fmt, selected)
	]

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

# pylint: disable=unused-argument
def generator_hex(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)
	string = str(value)

	array = format_numerical_with_units(string, "field", selected, non_units = set("0123456789abcdefABCDEF"))

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_list(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	items = getattr(obj, field)

	item_separator = deep_get(formatting, DictPath("item_separator"))
	if item_separator is None:
		item_separator = ("separators", "list")

	field_separators = deep_get(formatting, DictPath("field_separators"))
	if field_separators is None:
		field_separators = [("separators", "field")]

	field_colors = deep_get(formatting, DictPath("field_colors"))
	if field_colors is None:
		field_colors = [("types", "field")]

	ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

	ellipsis = deep_get(formatting, DictPath("ellipsis"))
	if ellipsis is None:
		ellipsis = ("separators", "ellipsis")

	field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
	field_suffixes = deep_get(formatting, DictPath("field_suffixes"))

	mapping = deep_get(formatting, DictPath("mapping"), {})

	return format_list(items, fieldlen, pad, ralign, selected,
			   item_separator = item_separator,
			   field_separators = field_separators,
			   field_colors = field_colors,
			   ellipsise = ellipsise,
			   ellipsis = ellipsis,
			   field_prefixes = field_prefixes,
			   field_suffixes = field_suffixes,
			   mapping = mapping)

def generator_list_with_status(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	items = getattr(obj, field)
	if isinstance(items, tuple):
		items = [items]

	item_separator = deep_get(formatting, DictPath("item_separator"))
	if item_separator is None:
		item_separator = ("separators", "list")

	field_separators = deep_get(formatting, DictPath("field_separators"))
	if field_separators is None:
		field_separators = [("separators", "field")]

	ellipsise = deep_get(formatting, DictPath("ellipsise"), -1)

	ellipsis = deep_get(formatting, DictPath("ellipsis"))
	if ellipsis is None:
		ellipsis = ("separators", "ellipsis")

	field_prefixes = deep_get(formatting, DictPath("field_prefixes"))
	field_suffixes = deep_get(formatting, DictPath("field_prefixes"))

	# XXX: Well, this works:ish, but it's ugly beyond belief
	#      it would be solved so much better with a mapping that uses a secondary value
	newitems = []
	field_colors = [
		("main", "status_done"),
		("main", "status_ok"),
		("main", "status_pending"),
		("main", "status_warning"),
		("main", "status_admin"),
		("main", "status_not_ok"),
		("main", "status_unknown"),
		("main", "status_crit"),
		("types", "generic")]
	field_separators = [("separators", "no_pad")]

	for item, status in items:
		if status == StatusGroup.DONE:
			newitems.append((item))
		if status == StatusGroup.OK:
			newitems.append(("", item))
		elif status == StatusGroup.PENDING:
			newitems.append(("", "", item))
		elif status == StatusGroup.WARNING:
			newitems.append(("", "", "", item))
		elif status == StatusGroup.ADMIN:
			newitems.append(("", "", "", "", item))
		elif status == StatusGroup.NOT_OK:
			newitems.append(("", "", "", "", "", item))
		elif status == StatusGroup.UNKNOWN:
			newitems.append(("", "", "", "", "", "", item))
		elif status == StatusGroup.CRIT:
			newitems.append(("", "", "", "", "", "", "", item))
		elif status == StatusGroup.NEUTRAL:
			newitems.append(("", "", "", "", "", "", "", "", item))
		else:
			newitems.append(("", "", "", "", "", "", "", "", item))

	return format_list(newitems, fieldlen, pad, ralign, selected,
			   item_separator = item_separator,
			   field_separators = field_separators,
			   field_colors = field_colors,
			   ellipsise = ellipsise,
			   ellipsis = ellipsis,
			   field_prefixes = field_prefixes,
			   field_suffixes = field_suffixes)

# pylint: disable=unused-argument
def generator_mem(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	free, total = getattr(obj, field)

	if free is None and total is None:
		return generator_basic(obj, field, fieldlen, pad, ralign, selected)

	used = f"{100 - (100 * int(free) / int(total)):0.1f}"

	if float(used) < 80.0:
		attribute = ("types", "watermark_low")
	elif float(used) < 90.0:
		attribute = ("types", "watermark_medium")
	else:
		attribute = ("types", "watermark_high")

	total = f"{int(total) / (1024 * 1024):0.1f}"
	unit = "GiB"

	array = [
		(used, attribute, selected),
		(("separators", "percentage"), selected),
		(" ", attribute, selected),
		(("separators", "fraction"), selected),
		(" ", attribute, selected),
		(total, ("types", "numerical"), selected),
		(unit, ("types", "unit"), selected),
	]
	stringlen = themearray_len(array)

	return align_and_pad(array, pad, fieldlen, stringlen, ralign, selected)

# pylint: disable=unused-argument
def generator_mem_single(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)
	string = str(value)

	array = format_numerical_with_units(string, "numerical", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

# pylint: disable=unused-argument
def generator_numerical(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)

	if value == -1:
		string = ""
	else:
		string = str(value)

	fmt = ("types", "timestamp")

	array = [
		(string, fmt, selected)
	]

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_numerical_with_units(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)

	if value in ("<none>", "<unset>", "<unknown>"):
		fmt = ("types", "none")
		array = [(value, fmt, selected)]
		return align_and_pad(array, pad, fieldlen, len(value), ralign, selected)

	if value == -1 and deep_get(formatting, DictPath("allow_signed")) == False:
		string = ""
	else:
		string = str(value)

	array = format_numerical_with_units(string, "numerical", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_status(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	status = getattr(obj, field)
	status_group = getattr(obj, "status_group")
	attribute = color_status_group(status_group)

	array = [
		(status, attribute, selected)
	]
	stringlen = len(status)

	return align_and_pad(array, pad, fieldlen, stringlen, ralign, selected)

def generator_timestamp(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)

	string = datetime_to_timestamp(value)
	if value is None:
		array = [(string, ("types", "generic"), selected)]
	elif value == datetime.fromtimestamp(0).astimezone():
		array = [(string, ("types", "generic"), selected)]
	else:
		array = format_numerical_with_units(string, "timestamp", selected)

	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

def generator_timestamp_with_age(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	values = getattr(obj, field)

	if len(values) > 2 and len(deep_get(formatting, DictPath("field_colors"), [])) < 2:
		raise ValueError("Received more than 2 fields for timestamp_with_age but no formatting to specify what the values signify")

	if len(values) == 2:
		if values[0] is None:
			array = [
				("<none>", ("types", "none"), selected)
			]
		else:
			timestamp_string = datetime_to_timestamp(values[0])
			array = format_numerical_with_units(timestamp_string, "timestamp", selected)
			array += [
				(" (", ("types", "generic"), selected)
			]
			array += generator_age_raw(values[1], selected)
			array += [
				(")", ("types", "generic"), selected)
			]
	else:
		array = []

		for i in range(0, len(values)):
			# If there's no formatting for this field we assume that
			# it's a generic string
			if len(deep_get(formatting, DictPath("field_colors"), [])) <= i:
				fmt = ("types", "generic")
				array += [(values[i], fmt, selected)]
			elif formatting["field_colors"][i] == ("types", "timestamp"):
				if values[i] is None:
					array += [
						("<unset>", ("types", "none"), selected)
					]
					break

				timestamp = timestamp_to_datetime(values[i])
				timestamp_string = timestamp.astimezone().strftime("%Y-%m-%d %H:%M:%S")
				array += format_numerical_with_units(timestamp_string, "timestamp", selected)
			elif formatting["field_colors"][i] == ("types", "age"):
				array += generator_age_raw(values[i], selected)
			else:
				array += [
					(values[i], formatting["field_colors"][i], selected)
				]

	return align_and_pad(array, pad, fieldlen, themearray_len(array), ralign, selected)

def generator_value_mapper(obj, field, fieldlen: int, pad: int, ralign: bool, selected: bool, **formatting):
	value = getattr(obj, field)

	default_field_color = cast(ThemeAttr, deep_get(formatting, DictPath("field_colors"), [("types", "generic")])[0])

	formatted_string, string = map_value(value, selected = selected,default_field_color = default_field_color,
					     mapping = deep_get(formatting, DictPath("mapping"), {}))
	array = [
		formatted_string
	]
	return align_and_pad(array, pad, fieldlen, len(string), ralign, selected)

# Generators acceptable for direct use in view files
generator_allowlist = {
	"generator_mem": generator_mem,
	"generator_status": generator_status,
}