#! /usr/bin/env python3
# Requires: python3 (>= 3.6)
from getpass import getpass
import os
import sys
import yaml

theme = None
themepath = None

def __themearray_to_string(themearray):
	string = ""
	for _string, theme_attr_ref in themearray:
		if theme is not None:
			if theme_attr_ref in theme["term"]:
				attr = theme["term"][theme_attr_ref]
				reset = theme["term"]["reset"]
				string += f"{attr}{_string}{reset}"
			else:
				raise Exception(f"attribute (\"term\", \"{theme_attr_ref}\") does not exist in {themepath}")
		else:
			string += _string

	if len(string) > 0:
		string = string.replace("\x0033", "\033")

	return string

# themearray is a list of format strings of the format:
# (string, theme_attr_ref); context is implicitly understood to be term
def iktinput(themearray):
	string = __themearray_to_string(themearray)
	return input(string)

# themearray is a list of format strings of the format:
# (string, theme_attr_ref); context is implicitly understood to be term
def iktinput_password(themearray):
	string = __themearray_to_string(themearray)
	return getpass(string)

# themearray is a list of format strings of the format:
# (string, theme_attr_ref); context is implicitly understood to be term
def iktprint(themearray, stderr = False):
	string = __themearray_to_string(themearray)

	if stderr == True:
		print(string, file = sys.stderr)
	else:
		print(string)

def init_iktprint(themefile):
	global theme
	global themepath

	themepath = themefile

	if os.path.isfile(themefile) is False:
		print(f"Warning: themefile ”{themefile}” does not exist", file = sys.stderr)
		return

	with open(themefile) as f:
		theme = yaml.safe_load(f)
