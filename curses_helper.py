#! /usr/bin/env python3
# Before calling into this helper you need to call init_colors()

import curses
from datetime import datetime
from operator import attrgetter
import os
import sys
import yaml

import iktlib
from iktlib import stgroup, stgroup_mapping
from logparser import loglevel, loglevel_to_name

theme = {}

mousemask = 0

class curses_configuration:
	abouttext = None
	mousescroll_enable = False
	mousescroll_up = 0b10000000000000000
	mousescroll_down = 0b1000000000000000000000000000

class retval:
	NOMATCH = 0	# No keypress matched/processed; further checks needed (if any)
	MATCH = 1	# keypress matched/processed; no further action
	RETURNONE = 2	# keypress matched/processed; return up one level
	RETURNFULL = 3	# keypress matched/processed, callback called; return up entire callstack
	RETURNDONE = 4	# We've done our Return One

def set_mousemask(mask):
	global mousemask
	curses.mousemask(mask)
	mousemask = mask

def get_mousemask():
	global mousemask
	return mousemask

color = {
}

__pairs = {
}

def get_theme_ref():
	return theme

def __convert_color_pair(color_pair):
	fg, bg = color_pair

	if type(fg) == list:
		fg, attr = fg
		if attr == "normal":
			attr = 0
		elif attr == "bright":
			attr = 8
		else:
			raise Exception(f"Unknown attribute {attr}")
	else:
		attr = 0

	fg = eval(f"curses.COLOR_{fg.upper()}")
	fg += attr

	if type(bg) == list:
		bg, attr = bg
		if attr == "normal":
			attr = 0
		elif attr == "bright":
			attr = 8
		else:
			raise Exception(f"Unknown attribute {attr}")
	else:
		attr = 0

	bg = eval(f"curses.COLOR_{bg.upper()}")
	bg += attr

	return (fg, bg)

def init_pair(color_pair, color_nr):
	fg, bg = color_pair
	try:
		curses.init_pair(color_nr, fg, bg)
	except:
		# Most likely we failed due to the terminal only
		# supporting colours 0-7. If "bright black" was
		# requested, we need to remap it. Fallback to blue;
		# hopefully there are no cases of bright black on blue.
		if fg & 7 == curses.COLOR_BLACK:
			fg = curses.COLOR_BLUE
		bg &= 7
		curses.init_pair(color_nr, fg & 7, bg)

def read_theme(configthemefile, defaultthemefile):
	global theme
	themefile = None

	for item in [configthemefile, f"{configthemefile}.yaml", defaultthemefile]:
		if os.path.isfile(item) is True:
			themefile = item
			break

	if themefile is None:
		print(f"{os.path.basename(sys.argv[0])}: couldn't load theme “{themefile}”; exiting.", file = sys.stderr)
		sys.exit(2)

	with open(themefile) as f:
		theme = yaml.safe_load(f)

def init_curses():
	color_last = 1

	# First we set the colour palette
	if "colors" in theme:
		for col, curses_col in [("black", curses.COLOR_BLACK), ("red", curses.COLOR_RED), ("green", curses.COLOR_GREEN), ("yellow", curses.COLOR_YELLOW), ("blue", curses.COLOR_BLUE), ("magenta", curses.COLOR_MAGENTA), ("cyan", curses.COLOR_CYAN), ("white", curses.COLOR_WHITE)]:
			r, g, b = theme["colors"][col]
			curses.init_color(curses_col, r, g, b)

	# Next we need to define all necessary colour pairs;
	# most of them come in selected and unselected variants
	for pair in theme["color_pairs_curses"]:
		if type(theme["color_pairs_curses"][pair]) == list:
			unselected = __convert_color_pair(theme["color_pairs_curses"][pair])
			selected = unselected
		else:
			unselected = __convert_color_pair(theme["color_pairs_curses"][pair]["unselected"])
			selected = __convert_color_pair(theme["color_pairs_curses"][pair]["selected"])

		if unselected not in __pairs:
			init_pair(unselected, color_last)
			__pairs[unselected] = curses.color_pair(color_last)
			color_last += 1
		unselected_index = __pairs[unselected]
		if selected not in __pairs:
			init_pair(selected, color_last)
			__pairs[selected] = curses.color_pair(color_last)
			color_last += 1
		selected_index = __pairs[selected]
		color[pair] = (unselected_index, selected_index)

def color_log_severity(severity, selected):
	return attr_to_curses_merged("logview", f"severity_{loglevel_to_name(severity).lower()}", selected)

def color_ram_usage(used, selected):
	if float(used) < 80.0: # Green
		attribute = attr_to_curses_merged("types", "watermark_low", selected)
	elif float(used) < 90.0: # Yellow
		attribute = attr_to_curses_merged("types", "watermark_medium", selected)
	else: # Red
		attribute = attr_to_curses_merged("types", "watermark_high", selected)

	return attribute

def color_status_group(status_group, selected = False):
	return attr_to_curses_merged("main", stgroup_mapping[status_group], selected = selected)

def window_tee_hline(win, y, start, end, attribute = None):
	_ltee = theme["boxdrawing"].get("ltee", curses.ACS_LTEE)
	_rtee = theme["boxdrawing"].get("rtee", curses.ACS_RTEE)
	_hline = theme["boxdrawing"].get("hline", curses.ACS_HLINE)
	if attribute is not None:
		win.addch(y, start, _ltee, attribute)
	else:
		win.addch(y, start, _ltee)

	x = start + 1
	while x < end:
		if attribute is not None:
			win.addch(y, x, _hline, attribute)
		else:
			win.addch(y, x, _hline)
		x += 1

	if attribute is not None:
		win.addch(y, end, _rtee, attribute)
	else:
		win.addch(y, end, _rtee)

def window_tee_vline(win, x, start, end, attribute = None):
	_ttee = theme["boxdrawing"].get("ttee", curses.ACS_TTEE)
	_btee = theme["boxdrawing"].get("btee", curses.ACS_BTEE)
	_vline = theme["boxdrawing"].get("vline", curses.ACS_VLINE)
	if attribute is not None:
		win.addch(start, x, _ttee, attribute)
	else:
		win.addch(start, x, _ttee)

	y = start + 1
	while y < end:
		if attribute is not None:
			win.addch(y, x, _vline, attribute)
		else:
			win.addch(y, x, _vline)
		y += 1

	if attribute is not None:
		win.addch(end, x, _btee, attribute)
	else:
		win.addch(end, x, _btee)

def scrollbar_vertical(win, x, miny, maxy, height, yoffset, clear_color):
	_arrowup = theme["boxdrawing"].get("arrowup", "▲")
	_arrowdown = theme["boxdrawing"].get("arrowdown", "▼")
	_scrollbar = theme["boxdrawing"].get("scrollbar", "▒")
	_verticaldragger_upper = theme["boxdrawing"].get("verticaldragger_upper", "█")
	_verticaldragger_midpoint = theme["boxdrawing"].get("verticaldragger_midpoint", "◉")
	_verticaldragger_lower = theme["boxdrawing"].get("verticaldragger_lower", "█")
	_vline = theme["boxdrawing"].get("vline", curses.ACS_VLINE)
	upperarrow = -1, -1
	lowerarrow = -1, -1
	vdragger = -1, -1, -1

	maxoffset = height - (maxy - miny) - 1

	# We only need a scrollbar if we can actually scroll
	if maxoffset > 0:
		win.addch(miny, x, _arrowup, attr_to_curses_merged("main", "scrollbar_arrows"))
		upperarrow = miny, x
		y = miny + 1
		while y < maxy:
			win.addch(y, x, _scrollbar, attr_to_curses_merged("main", "scrollbar"))
			y += 1
		win.addch(maxy, x, _arrowdown, attr_to_curses_merged("main", "scrollbar_arrows"))
		lowerarrow = maxy, x
		curpos = miny + 1 + int((maxy - miny) * (yoffset / (maxoffset)))
		curpos = min(curpos, maxy - 3)
		vdragger = curpos, x, 3
		win.addch(curpos, x, _verticaldragger_upper, attr_to_curses_merged("main", "dragger"))
		win.addch(curpos + 1, x, _verticaldragger_midpoint, attr_to_curses_merged("main", "dragger_midpoint"))
		win.addch(curpos + 2, x, _verticaldragger_lower, attr_to_curses_merged("main", "dragger"))
	# But we might need to cover up the lack of one if the window has been resized
	else:
		for y in range(miny, maxy + 1):
			win.addch(y, x, _vline, clear_color)

	# (y, x Upper arrow), (y, x Lower arrow), (y, x, len vertical dragger)
	return upperarrow, lowerarrow, vdragger

def scrollbar_horizontal(win, y, minx, maxx, width, xoffset, clear_color):
	_arrowleft = theme["boxdrawing"].get("arrowleft", "◀")
	_arrowright = theme["boxdrawing"].get("arrowright", "▶")
	_scrollbar = theme["boxdrawing"].get("scrollbar", "▒")
	_horizontaldragger_left = theme["boxdrawing"].get("horizontaldragger_left", "█")
	_horizontaldragger_midpoint = theme["boxdrawing"].get("horizontaldragger_midpoint", "◉")
	_horizontaldragger_right = theme["boxdrawing"].get("horizontaldragger_right", "█")
	_hline = theme["boxdrawing"].get("hline", curses.ACS_HLINE)
	leftarrow = -1, -1
	rightarrow = -1, -1
	hdragger = -1, -1, -1

	maxoffset = width - (maxx - minx) - 1

	# We only need a scrollbar if we can actually scroll
	if maxoffset > 0:
		win.addch(y, minx, _arrowleft, attr_to_curses_merged("main", "scrollbar_arrows"))
		leftarrow = y, minx

		x = minx + 1
		while x < maxx:
			win.addch(y, x, _scrollbar, attr_to_curses_merged("main", "scrollbar"))
			x += 1
		win.addch(y, maxx, _arrowright, attr_to_curses_merged("main", "scrollbar_arrows"))
		rightarrow = y, maxx

		curpos = minx + 1 + int((maxx - minx) * (xoffset / (maxoffset)))
		curpos = min(curpos, maxx - 5)
		win.addch(y, curpos, _horizontaldragger_left, attr_to_curses_merged("main", "dragger"))
		win.addch(_horizontaldragger_left, attr_to_curses_merged("main", "dragger"))
		win.addch(_horizontaldragger_midpoint, attr_to_curses_merged("main", "dragger_midpoint"))
		win.addch(_horizontaldragger_right, attr_to_curses_merged("main", "dragger"))
		win.addch(_horizontaldragger_right, attr_to_curses_merged("main", "dragger"))
		hdragger = y, curpos, 5
	# But we might need to cover up the lack of one if the window has been resized
	else:
		for x in range(minx, maxx + 1):
			win.addch(y, x, _hline, clear_color)

	# (y, x Upper arrow), (y, x Lower arrow), (y, x, len horizontal dragger)
	return leftarrow, rightarrow, hdragger

# This does not draw a heatmap; it only generates an array of string arrays
def generate_heatmap(maxwidth, stgroups, selected):
	array = []
	row = []
	block = theme["boxdrawing"].get("smallblock", "■")
	selectedblock = theme["boxdrawing"].get("block", "█")
	x = 0

	color = -1
	tmp = ""

	# Try to make minimise the colour changes
	for i in range(0, len(stgroups)):
		heat = stgroups[i]
		nextcolor = color_status_group(heat, False)
		if selected == i:
			sblock = selectedblock
		else:
			sblock = block

		if x > maxwidth:
			row.append((tmp, color))
			x = 0
			array.append(row)
			color = -1
			row = []

		# If we have a new colour we need a new element in the array,
		# otherwise we just extend the current element
		if color == -1:
			color = nextcolor
			tmp = f"{sblock}"
		elif nextcolor == color:
			tmp += f"{sblock}"
		elif nextcolor != color:
			row.append((tmp, color))
			tmp = f"{sblock}"
			color = nextcolor

		x += 1
		if i == len(stgroups) - 1:
			row.append((tmp, color))
			array.append(row)
			break

	return array

def percentagebar(win, y, minx, maxx, total, subsets):
	block = theme["boxdrawing"].get("smallblock", "■")
	barwidth = maxx - minx - 3
	barpos = minx + 1

	win.addstr(y, minx, "[")
	ax = barpos
	for subset in subsets:
		rx = 0
		pct, col = subset
		subsetwidth = int((pct / total) * barwidth)

		while rx < subsetwidth and ax < barwidth:
			win.addstr(y, ax, block, col)
			rx += 1
			ax += 1
	win.addstr(y, maxx, "]")
	return win

def __notification(stdscr, y, x, message, formatting):
	height = 3
	width = 2 + len(message)
	ypos = y - height // 2
	xpos = x - width // 2

	win = curses.newwin(height, width, ypos, xpos)
	col, __discard = attr_to_curses("windowwidget", "boxdrawing")
	win.attrset(col)
	win.clear()
	_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
	_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
	_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
	_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
	_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
	_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
	_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
	_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
	win.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
	win.addstr(1, 1, message, attr_to_curses_merged(formatting[0], formatting[1]))
	win.noutrefresh()
	curses.doupdate()
	return win

def notice(stdscr, y, x, message):
	return __notification(stdscr, y, x, message, ("windowwidget", "notice"))

def alert(stdscr, y, x, message):
	return __notification(stdscr, y, x, message, ("windowwidget", "alert"))

# Usage: Initialise by calling with a reference to a variable set to None
# Pass in progress in 0-100; once done clean up with:
# stdscr.touchwin()
# stdscr.refresh()
def progressbar(win, y, minx, maxx, progress, title = None):
	width = maxx - minx + 1

	if progress < 0:
		sys.exit("You cannot use a progress bar with negative progress; this isn't a regression bar.")
	elif progress > 100:
		sys.exit("That's impossible. No one can give more than 100%. By definition, that is the most anyone can give.")

	if win is None:
		win = curses.newwin(3, width, y, minx)
		col, __discard = attr_to_curses("windowwidget", "boxdrawing")
		win.attrset(col)
		win.clear()
		_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
		_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
		_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
		_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
		_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
		_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
		_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
		_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
		win.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
		col, __discard = attr_to_curses("windowwidget", "default")
		win.bkgd(" ", col)
		if title is not None:
			win.addstr(0, 1, title, attr_to_curses_merged("windowwidget", "title"))

	# progress is in % of the total length
	for x in range(0, width - 2):
		if x < (width * progress) // 100:
			win.addch(1, x + 1, theme["boxdrawing"]["solidblock"], attr_to_curses_merged("main", "progressbar"))
		else:
			win.addch(1, x + 1, theme["boxdrawing"]["dimmedblock"], attr_to_curses_merged("main", "progressbar"))

	win.noutrefresh()
	curses.doupdate()

	return win

ignoreinput = False

def inputwrapper(keypress):
	global ignoreinput

	if keypress == 27:	# ESCAPE
		ignoreinput = True
		return 7
	else:
		return keypress

# Show a one line high pad the width of the current pad with a border
# and specified title in the middle of the screen
def inputbox(stdscr, y, x, height, width, title):
	# Show the cursor
	curses.curs_set(True)

	global ignoreinput
	ignoreinput = False

	win = curses.newwin(3, width, y, x)
	col, __discard = attr_to_curses("windowwidget", "boxdrawing")
	win.attrset(col)
	win.clear()
	_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
	_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
	_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
	_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
	_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
	_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
	_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
	_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
	win.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
	win.addstr(0, 1, title, attr_to_curses_merged("windowwidget", "title"))
	win.noutrefresh()

	inputarea = win.subwin(1, width - 2, y + 1, x + 1)
	inputarea.bkgd(" ", attr_to_curses_merged("windowwidget", "title"))
	inputarea.attrset(attr_to_curses_merged("windowwidget", "title"))
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
def confirmationbox(stdscr, y, x, title = "", default = False):
	global ignoreinput
	ignoreinput = False
	retval = default

	question = "Are you sure [%s]: " % ("Y/n" if default else "y/N")
	height = 3
	width = 2 + max(len(question), len(title))
	ypos = y - height // 2
	xpos = x - width // 2

	win = curses.newwin(height, width, ypos, xpos)
	col, __discard = attr_to_curses("windowwidget", "boxdrawing")
	win.attrset(col)
	win.clear()
	_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
	_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
	_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
	_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
	_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
	_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
	_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
	_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
	win.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
	win.addstr(0, 1, title, attr_to_curses_merged("windowwidget", "title"))
	win.addstr(1, 1, question.ljust(width - 2), attr_to_curses_merged("windowwidget", "default"))
	win.noutrefresh()
	curses.doupdate()

	while True:
		stdscr.timeout(100)
		c = stdscr.getch()
		if c == 27:	# ESCAPE
			break
		elif c == ord(""):
			sys.exit()
		elif c == curses.KEY_ENTER or c == 10 or c == 13:
			break
		elif c == ord("y") or c == ord("Y"):
			retval = True
			break
		elif c == ord("n") or c == ord("N"):
			retval = False
			break

	del win
	stdscr.touchwin()
	stdscr.noutrefresh()
	curses.doupdate()

	return retval

def move_xoffset_rel(xoffset, maxxoffset, movement):
	xoffset = max(0, xoffset + movement)
	xoffset = min(maxxoffset, xoffset)
	return xoffset

def move_yoffset_rel(yoffset, maxyoffset, movement):
	yoffset = max(0, yoffset + movement)
	yoffset = min(maxyoffset, yoffset)
	return yoffset

def move_cur_with_offset(curypos, listlen, yoffset, maxcurypos, maxyoffset, movement, wraparound = False):
	newcurypos = curypos + movement
	newyoffset = yoffset

	# If we are being asked to move forward but we're already
	# at the end of the list, it's prudent not to move,
	# even if the caller so requests.
	# It's just good manners, really; likewise if we're being asked to move
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

def addstr(win, string, y = -1, x = -1, attribute = curses.A_NORMAL):
	cury, curx = win.getyx()
	winmaxy, winmaxx = win.getmaxyx()
	newmaxy = max(y, winmaxy)
	newmaxx = max(winmaxx, len(string) + curx + 1)
	win.resize(newmaxy, newmaxx)
	if y == -1:
		y = cury
	if x == -1:
		x = curx
	win.addstr(y, x, string, attribute)
	cury, curx = win.getyx()
	return cury, curx

def addarray(win, array, y = -1, x = -1):
	# This way we can print a single (string, attr) too
	if type(array) == tuple:
		array = [array]

	for string, attr in array:
		if type(attr) == tuple:
			raise Exception(f"addarray() called with attr: {attr} (type: tuple); must be integer")
		y, x = addstr(win, string, y, x, attr)
	return y, x

# addthemearray() takes an array as input.
# The elements in the array can be:
# (string, (context, theme_attr_ref)),
# (string, (context, theme_attr_ref), selected),
# (string, (context, curses_attr)),
# (context, theme_ref),
# (context, theme_ref, selected),
def addthemearray(win, array, y = -1, x = -1, selected = False):
	for item in array:
		if type(item) != tuple:
			raise Exception(f"unexpected item-type passed to addthemearray):\ntype(item): {type(item)}\nitem: {item}\narray: {array}")

		if len(item) == 3:
			_p1, _p2, _selected = item
		else:
			_p1, _p2 = item
			_selected = selected

		if type(_p2) == tuple:
			string = _p1
			if len(_p2) == 3:
				context, _p3, _selected = _p2
			else:
				context, _p3 = _p2
			if type(_p3) == int:
				attr = _p3
			else:
				attr = attr_to_curses_merged(context, _p3, selected = _selected)
			y, x = addstr(win, string, y, x, attr)
		elif type(_p2) == int:
			string = _p1
			attr = _p2
			y, x = addstr(win, string, y, x, attr)
		else:
			if type(_p1) == tuple:
				context, attr_ref = _p1
				_selected = _p2
			else:
				attr_ref = _p2
				context = _p1
				_selected = selected

			strarray = themearray_to_strarray(attr_ref, context = context, selected = _selected)
			y, x = addarray(win, strarray, y = y, x = x)
	return y, x


class widgetlineattrs:
	NORMAL = 0		# No specific attributes
	SEPARATOR = 1		# Separators start a new category; they are not selectable
	DISABLED = 2		# Disabled items are not selectable, but aren't treated as a new category
	UNSELECTABLE = 4	# Unselectable items are not selectable, but aren't skipped when navigating
	INVALID = 8		# Invalid items are not selectable; to be used for parse error etc.

def __attr_to_curses(attr, selected = False):
	if type(attr) == list:
		col, attr = attr
		if type(attr) == str:
			attr = [attr]
		else:
			attr = list(attr)
		tmp = 0
		for item in attr:
			# attr can be one or more of "dim", "normal", "bold", "underline"
			tmp |= eval(f"curses.A_{item.upper()}")
		attr = tmp
	else:
		col = attr
		attr = curses.A_NORMAL

	return color[col][selected], attr

def __attr_to_curses_merged(attr, selected = False):
	col, attr = __attr_to_curses(attr, selected)
	return col | attr

def attr_to_curses(context, attr, selected = False):
	# <attr> is a string that references a field in the section <context> of the themes-file;
	# that field can either be either a string, which in that case will be used directly against
	# the colour lookup table, or a list, in which case the first entry is the colour,
	# and the second entry is a curses attribute; recognised attributes (dim, normal, bold, underline)
	attr = theme[context][attr]
	if type(attr) == dict:
		if selected == True:
			attr = attr["selected"]
		else:
			attr = attr["unselected"]
	return __attr_to_curses(attr, selected)

def attr_to_curses_merged(context, attr, selected = False):
	# <attr> is a string that references a field in the section <context> of the themes-file;
	# that field can either be either a string, which in that case will be used directly against
	# the colour lookup table, or a list, in which case the first entry is the colour,
	# and the second entry is a curses attribute; recognised attributes (dim, normal, bold, underline)
	attr = theme[context][attr]
	if type(attr) == dict:
		if selected == True:
			attr = attr["selected"]
		else:
			attr = attr["unselected"]
	return __attr_to_curses_merged(attr, selected)

def themearray_to_strarray(key, context = "main", selected = False):
	array = theme[context][key]

	strarray = []
	for item in array:
		string = item[0]
		attr = __attr_to_curses_merged(item[1], selected)
		strarray.append((string, attr))

	return strarray

def strarray_extract_string(strarray):
	string = ""
	for _string, _attr in strarray:
		string += _string
	return string

def strarray_wrap_line(strarray, maxwidth = -1, wrap_marker = True):
	if maxwidth == -1 or len(strarray_extract_string(strarray)) < maxwidth:
		return [strarray]

	strarrays = []
	i = 0
	tmpstrarray = []
	tmplen = 0
	linebreak = themearray_to_strarray("line_break", context = "separators")
	if wrap_marker == True:
		linebreaklen = len(strarray_extract_string(linebreak))
	else:
		linebreaklen = 0

	while True:
		if type(strarray[i]) == tuple and len(strarray[i]) == 2 and type(strarray[i][1]) == str:
			strarray[i] = themearray_to_strarray(strarray[i][1], strarray[i][0])[0]
		_string, _attr = strarray[i]

		# If this is the last fragment and it fits, don't add a linebreak marker
		if tmplen + len(_string) <= maxwidth and i == len(strarray) - 1:
			tmpstrarray.append((_string, _attr))
			strarrays.append(tmpstrarray)
			tmpstrarray = []
			tmplen = 0
			break
		# If this fragment fits (and we need room for a linebreak character),
		# add it and continue
		elif len(_string) + tmplen < (maxwidth - linebreaklen):
			tmpstrarray.append((_string, _attr))
			tmplen += len(_string)
			i += 1
		# If the fragment doesn't fit, slice it up and replace the element
		# with the remainder
		else:
			tmpstrarray.append((_string[0:maxwidth - linebreaklen - tmplen], _attr))
			if wrap_marker == True:
				tmpstrarray += linebreak
			strarrays.append(tmpstrarray)
			strarray[i] = (_string[maxwidth - linebreaklen - tmplen:], _attr)
			tmpstrarray = []
			tmplen = 0

	return strarrays

def themearray_extract_string(key, context = "main", selected = False):
	string = ""
	try:
		strarray = themearray_to_strarray(key, context, selected)
	except:
		strarray = key
	return strarray_extract_string(strarray)

def themearray_get_string(themearray):
	string = ""

	if type(themearray) == tuple:
		themearray = [themearray]

	# If this is just a string, return it
	if type(themearray) == str:
		string = themearray
	else:
		for item in themearray:
			# If item is a tuple of length 2, with both items being strings,
			# it's a theme string lookup; if it's length 2 with the second
			# item being a tuple, it's a themed string
			_p1, _p2 = item
			if len(item) == 2:
				if type(_p1) == str:
					if type(_p2) == str:
						string += themearray_extract_string(_p2, context = _p1)
					elif type(_p2) == tuple:
						string += _p1
				else:
					raise Exception("type(item)={type(item)\nlen(item)={len(item)}\nitem={item}")

	return string

def themearray_get_length(themearray):
	return len(themearray_get_string(themearray))

# A generic window widget
# items is a list of tuples, like so:
# (widgetlineattr, strarray, strarray, ...)
# A strarray is a list of tuples, where every tuple is of the format (string, attribute)
def windowwidget(stdscr, maxy, maxx, y, x, items, headers = None, title = "", preselection = "", cursor = True, taggable = False, confirm = False, confirm_buttons = []):
	stdscr.refresh()
	global ignoreinput
	ignoreinput = False

	padwidth = 2
	listpadheight = len(items)

	# This is only used by helptexts
	if type(items[0][0]) != int:
		tmpitems = []
		for item in items:
			tmpitems.append((widgetlineattrs.NORMAL, [(item[0], ("windowwidget", "highlight"))], [(item[1], ("windowwidget", "default"))]))
		items = tmpitems

	columns = len(items[0]) - 1
	lengths = [0] * columns

	if headers is not None:
		if len(headers) != columns:
			raise Exception(f"Mismatch: Number of headers passed to windowwidget ({len(headers)}) does not match number of columns ({columns})")
		else:
			for i in range(0, columns):
				lengths[i] = len(headers[i])


	tagprefix = themearray_extract_string("tag", context = "separators")

	# Leave room for a tag prefix column if needed
	if taggable == True:
		tagprefixlen = len(tagprefix)
	else:
		tagprefixlen = 0

	# Every item is a line
	for item in items:
		for i in range(0, columns):
			length = 0
			for string, attribute in item[i + 1]:
				length += len(string)
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
	col, __discard = attr_to_curses("windowwidget", "boxdrawing")
	win.attrset(col)
	win.clear()
	_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
	_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
	_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
	_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
	_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
	_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
	_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
	_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
	win.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
	col, __discard = attr_to_curses("windowwidget", "default")
	win.bkgd(" ", col)
	win.addstr(0, 1, title, attr_to_curses_merged("windowwidget", "title"))
	listpad = curses.newpad(listpadheight + 1, listpadwidth + 1)
	col, __discard = attr_to_curses("windowwidget", "default")
	listpad.bkgd(" ", col)

	if headers is not None:
		headerpad = curses.newpad(1, listpadwidth + 1)
		col, __discard = attr_to_curses("windowwidget", "header")
		headerpad.bkgd(" ", col)

	if confirm == True:
		buttonpad = curses.newpad(1, listpadwidth + 1)
		col, __discard = attr_to_curses("windowwidget", "header")
		headerpad.bkgd(" ", col)

	selection = None
	curypos = 0

	headerarray = []

	# Generate headers
	if headers is not None:
		if taggable == True:
			headerarray.append((f"{tagprefix}", ("windowwidget", "highlight")))
		for i in range(0, columns):
			extrapad = padwidth
			if i == columns - 1:
				extrapad = 0
			headerarray.append(((headers[i].ljust(lengths[i] + extrapad)), attr_to_curses_merged("windowwidget", "header")))

	# Move to preselection
	if type(preselection) == str:
		if preselection != "":
			for y in range(0, len(items)):
				if items[y][1][0][0] == preselection:
					curypos, yoffset = move_cur_with_offset(0, height, yoffset, maxcurypos, maxyoffset, y)
					break
		tagged_items = set()
	elif type(preselection) == set:
		tagged_items = preselection

	while selection == None:
		for y in range(0, len(items)):
			if cursor == True:
				_selected = (yoffset + curypos == y)
			else:
				_selected = False

			lineattributes = items[y][0]
			linearray = []

			if taggable == True:
				if y in tagged_items:
					linearray.append((f"{tagprefix}", ("windowwidget", "tag")))
				else:
					linearray.append(("".ljust(tagprefixlen), ("windowwidget", "tag")))

			for x in range(0, columns):
				strarray = []
				length = 0
				tmpstring = ""

				for string, attribute in items[y][x + 1]:
					tmpstring += string
					length += len(string)
					if lineattributes & (widgetlineattrs.INVALID) != 0:
						attribute = ("windowwidget", "alert")
						strarray.append((string, attribute, _selected))
					elif lineattributes & (widgetlineattrs.DISABLED | widgetlineattrs.UNSELECTABLE) != 0:
						attribute = ("windowwidget", "dim")
						strarray.append((string, attribute, _selected))
					elif lineattributes & widgetlineattrs.SEPARATOR != 0:
						if attribute == ("windowwidget", "default"):
							attribute = ("windowwidget", "highlight")
						tpad = listpadwidth - len(string)
						lpad = int(tpad / 2)
						rpad = tpad - lpad
						lpadstr = "".ljust(lpad, "─")
						rpadstr = "".rjust(rpad, "─")

						strarray.append((lpadstr, ("windowwidget", "highlight"), _selected))
						strarray.append((string, attribute, _selected))
						strarray.append((rpadstr, ("windowwidget", "highlight"), _selected))
					else:
						strarray.append((string, attribute, _selected))


				if lineattributes & widgetlineattrs.SEPARATOR == 0:
					padstring = "".ljust(lengths[x] - length + padwidth)
					strarray.append((padstring, attribute, _selected))

				linearray += strarray

			addthemearray(listpad, linearray, y = y, x = 0)

		upperarrow, lowerarrow, vdragger = scrollbar_vertical(win, width - 1, scrollbarypos, height - 2, listpadheight, yoffset, attr_to_curses_merged("windowwidget", "boxdrawing"))
		leftarrow, rightarrow, hdragger = scrollbar_horizontal(win, height - 1, 1, width - 2, listpadwidth, xoffset, attr_to_curses_merged("windowwidget", "boxdrawing"))

		if headers is not None:
			addthemearray(headerpad, headerarray, y = 0, x = 0)
			headerxoffset = 0
			if len(headers) > 0:
				headerxoffset = xoffset
			headerpad.noutrefresh(0, headerxoffset, headerpadypos, xpos + 1, headerpadypos, xpos + width - 2)
			window_tee_hline(win, 2, 0, width - 1, attr_to_curses_merged("windowwidget", "boxdrawing"))

		listpad.noutrefresh(yoffset, xoffset, listpadypos, xpos + 1, ypos + height - 2, xpos + width - 2)

		if confirm == True:
			x = width - button_lengths - 2
			col, __discard = attr_to_curses("windowwidget", "header")
			buttonpad.bkgd(" ", col)
			for button in confirm_buttons[1:]:
				_, x = addthemearray(buttonpad, button, y = 0, x = x)
				x += 1
			buttonpad.noutrefresh(0, 0, buttonpadypos, xpos + 1, buttonpadypos, xpos + width - 2)
			window_tee_hline(win, height - 3, 0, width - 1, attr_to_curses_merged("windowwidget", "boxdrawing"))

		win.noutrefresh()
		curses.doupdate()

		stdscr.timeout(100)
		oldcurypos = curypos
		oldyoffset = yoffset
		c = stdscr.getch()
		if c == 27:	# ESCAPE
			selection = (0, [("", None)])
			confirm_press = c
			break
		elif c == ord(""):
			sys.exit()
		elif taggable == True and c == ord(" "):
			if curypos + yoffset in tagged_items:
				tagged_items.remove(curypos + yoffset)
			else:
				tagged_items.add(curypos + yoffset)
		elif ord("a") <= c <= ord("z") and cursor == True and confirm == False:
			# Find the next entry starting with the pressed letter; wrap around if the bottom is hit
			# stop if oldycurypos + oldyoffset is hit
			while True:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1, wraparound = True)
				lineattributes = items[yoffset + curypos][0]
				if items[yoffset + curypos][1][0][0][0].lower() == chr(c).lower() and lineattributes & widgetlineattrs.DISABLED == 0:
					break
				if (curypos + yoffset) == (oldcurypos + oldyoffset):
					# While we're at the same position in the list we might not be at the same offsets
					curypos = oldcurypos
					yoffset = oldyoffset
					break
		elif ord("A") <= c <= ord("Z") and cursor == True and confirm == False:
			# Find the previous entry starting with the pressed letter; wrap around if the top is hit
			# stop if oldycurypos + oldyoffset is hit
			while True:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1, wraparound = True)
				lineattributes = items[yoffset + curypos][0]
				if items[yoffset + curypos][1][0][0][0].lower() == chr(c).lower() and lineattributes & widgetlineattrs.DISABLED == 0:
					break
				if (curypos + yoffset) == (oldcurypos + oldyoffset):
					# While we're at the same position in the list we might not be at the same offsets
					curypos = oldcurypos
					yoffset = oldyoffset
					break
		elif c == ord("\t") and cursor == True:
			# Find next group
			while items[yoffset + curypos][0] & widgetlineattrs.SEPARATOR == 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (curypos + yoffset) == (maxcurypos + maxyoffset):
					break
				# OK, we found a group, now find the first not-group
			while items[yoffset + curypos][0] & widgetlineattrs.SEPARATOR != 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (curypos + yoffset) == (maxcurypos + maxyoffset):
					break
		elif c == curses.KEY_BTAB and cursor == True:
			# Find previous group
			while items[yoffset + curypos][0] & widgetlineattrs.SEPARATOR == 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (curypos + yoffset) == 0:
					break
			# OK, we found a group, now find the previous not-group
			while items[yoffset + curypos][0] & widgetlineattrs.SEPARATOR != 0:
				curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (curypos + yoffset) == 0:
					break
			# Finally find the first entry in that group
			while (curypos + yoffset) > 0 and items[yoffset + curypos][0] & widgetlineattrs.SEPARATOR != 0:
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
		elif (c == curses.KEY_ENTER or c == 10 or c == 13) and items[yoffset + curypos][0] & (widgetlineattrs.UNSELECTABLE) == 0 and confirm == False:
			selection = items[yoffset + curypos]
			break
		elif confirm == True and c in confirm_buttons[0]:
			confirm_press = c
			break

		# These only apply if we use a cursor
		if cursor == True:
			# Find the last acceptable line
			if (yoffset + curypos) == (maxcurypos + maxyoffset):
				while items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
			# We tried moving backwards; do we need to go farther?
			if (yoffset + curypos) > (oldyoffset + oldcurypos):
				while (yoffset + curypos) < len(items) and items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
				if (yoffset + curypos) == len(items) and items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
					yoffset = oldyoffset
					curypos = oldcurypos
			# Find the first acceptable line
			elif (yoffset + curypos) == 0:
				while items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, +1)
			# We tried moving backwards; do we need to go farther?
			elif (yoffset + curypos) < (oldyoffset + oldcurypos):
				while (yoffset + curypos) > 0 and items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
					curypos, yoffset = move_cur_with_offset(curypos, height, yoffset, maxcurypos, maxyoffset, -1)
				if (yoffset + curypos) == 0 and items[yoffset + curypos][0] & (widgetlineattrs.SEPARATOR | widgetlineattrs.DISABLED) != 0:
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
	elif confirm == True:
		return (confirm_press, selection)
	else:
		return selection

label_headers = ["Label:", "Value:"]

def get_labels(labels):
	if labels is None:
		return None

	rlabels = []
	for label in labels:
		rlabels.append((widgetlineattrs.NORMAL, [(label, attr_to_curses("windowwidget", "default"))], [(labels[label].replace("\n", "\\n"), attr_to_curses("windowwidget", "default"))]))
	return rlabels

annotation_headers = ["Annotation:", "Value:"]

def get_annotations(annotations):
	return get_labels(annotations)

class UIProps:
	def __init__(self, stdscr):
		self.stdscr = stdscr

		# Helptext
		self.helptext = None

		# Info to use for populating lists, etc.
		self.info = None
		self.sorted_list = None
		self.sortorder_reverse = False

		# Used for label list
		self.labels = None

		# Used for annotation list
		self.annotations = None

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
		# -1 -- Don't update
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
		self.field_list = None
		# Should there be a timestamp in the upper right corner?
		self.timestamp = True

		self.selected = None

		# For important status;
		# shown next to the window title
		self.extra_status = None

		# For generic information
		self.infopadminwidth = 0
		self.infopadypos = 0
		self.infopadxpos = 0
		self.infopadheight = 0
		self.infopadwidth = 0
		self.infopad = None
		# For the list of pods
		self.headerpadminwidth = 0
		self.headerpadypos = 0
		self.headerpadxpos = 0
		self.headerpadheight = 0
		self.headerpadwidth = 0
		self.headerpad = None
		self.listpadypos = 0
		self.listpadxpos = 0
		self.listpadheight = 0
		self.listpadwidth = 0
		self.listpad = None
		# For logs with a timestamp column
		self.tspadypos = 0
		self.tspadxpos = 0
		self.tspadheight = 0
		self.tspadwidth = len("YYYY-MM-DD HH:MM:SS")
		self.tspad = None
		self.borders = None
		self.logpadypos = 0
		self.logpadxpos = 0
		self.logpadheight = 0
		self.logpadwidth = 0
		self.logpad = None
		self.loglen = 0
		self.statusbar = None
		self.continuous_log = False
		# For checking clicks/drags of the scrollbars
		self.leftarrow = -1, -1
		self.rightarrow = -1, -1
		self.hdragger = -1, -1, -1
		self.upperarrow = -1, -1
		self.lowerarrow = -1, -1
		self.vdragger = -1, -1, -1

		# Function handler for <enter> / <double-click>
		self.activatedfun = None
		self.extraref = None
		self.data = None

	def __del__(self):
		if self.infopad is not None:
			del self.infopad
		if self.listpad is not None:
			del self.listpad
		if self.headerpad is not None:
			del self.headerpad
		if self.logpad is not None:
			del self.logpad

	def set_extra_status(self, extra_status = None):
		self.extra_status = extra_status

	def update_sorted_list(self):
		sortkey1, sortkey2 = self.get_sortkeys()
		self.sorted_list = sorted(self.info, key = attrgetter(sortkey1, sortkey2), reverse = self.sortorder_reverse)

	def update_info(self, info):
		self.info = info
		self.listlen = len(self.info)

		return self.listlen

	def update_log_info(self, timestamps, facilities, severities, messages):
		self.timestamps = timestamps
		self.facilities = facilities
		self.severities = severities
		self.messages = messages

	def set_update_delay(self, delay):
		self.update_delay = delay

	def force_update(self):
		self.update_count = 0
		self.refresh = True

	def disable_update(self):
		self.update_count = -1

	def reset_update_delay(self):
		self.update_count = self.update_delay

	def countdown_to_update(self):
		if self.update_count > 0:
			self.update_count -= 1

	def is_update_triggered(self):
		return self.update_count == 0

	def select(self, selection):
		self.selected = selection

	def select_if_y(self, y, selection):
		if self.yoffset + self.curypos == y:
			self.select(selection)

	def is_selected(self, selected):
		if selected == None:
			return False
		else:
			return self.selected == selected

	def get_selected(self):
		return self.selected

	# Default behaviour:
	# timestamps enabled, no automatic updates, default sortcolumn = "status"
	def init_window(self, field_list, view = None, windowheader = "", timestamp = True, update_delay = -1, sortcolumn = "status", sortorder_reverse = False, reversible = True, helptext = None, activatedfun = None, extraref = None, data = None):
		self.field_list = field_list
		self.searchkey = ""
		self.sortcolumn = sortcolumn
		self.sortorder_reverse = sortorder_reverse
		self.reversible = reversible
		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.set_update_delay(update_delay)
		self.timestamp = timestamp
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

		self.activatedfun = activatedfun
		self.extraref = extraref
		self.data = data

	def reinit_window(self, field_list, sortcolumn):
		self.field_list = field_list
		self.searchkey = ""
		self.sortcolumn = sortcolumn
		self.sortkey1, self.sortkey2 = self.get_sortkeys()
		self.resize_window()

	def update_window(self):
		maxyx = self.stdscr.getmaxyx()
		if self.maxy != (maxyx[0] - 1) or self.maxx != (maxyx[1] - 1):
			self.resize_window()
		self.stdscr.erase()
		_ltee = theme["boxdrawing"].get("ltee", curses.ACS_LTEE)
		_rtee = theme["boxdrawing"].get("rtee", curses.ACS_RTEE)
		_vline = theme["boxdrawing"].get("vline", curses.ACS_VLINE)
		_hline = theme["boxdrawing"].get("hline", curses.ACS_HLINE)
		_ls = theme["boxdrawing"].get("vline_left", curses.ACS_VLINE)
		_rs = theme["boxdrawing"].get("vline_right", curses.ACS_VLINE)
		_ts = theme["boxdrawing"].get("hline_top", curses.ACS_HLINE)
		_bs = theme["boxdrawing"].get("hline_bottom", curses.ACS_HLINE)
		_tl = theme["boxdrawing"].get("ulcorner", curses.ACS_ULCORNER)
		_tr = theme["boxdrawing"].get("urcorner", curses.ACS_URCORNER)
		_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
		_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)
		self.stdscr.border(_ls, _rs, _ts, _bs, _tl, _tr, _bl, _br)
		# If we don't have sideborders we need to clear the right border we just painted,
		# just in case the content of the logpad isn't wide enough to cover it
		if self.borders == False:
			for y in range(self.logpadypos, self.maxy - 1):
				self.stdscr.addch(y, self.maxx, " ")

		self.draw_winheader()
		self.update_timestamp(0, self.maxx, ralign = True)

		if self.headerpad is not None:
			self.headerpad.clear()
			# Whether to have one or two hlines depends on if we
			# overlap with the upper border or not
			if self.headerpadypos > 1:
				window_tee_hline(self.stdscr, self.headerpadypos - 1, 0, self.maxx)
			window_tee_hline(self.stdscr, self.headerpadypos + 1, 0, self.maxx)
			if self.borders == False:
				if self.headerpadypos > 1:
					self.stdscr.addch(self.headerpadypos - 1, 0, _hline)
					self.stdscr.addch(self.headerpadypos - 1, self.maxx, _hline)
				self.stdscr.addch(self.headerpadypos + 1, 0, _hline)
				self.stdscr.addch(self.headerpadypos + 1, self.maxx, _hline)
		elif self.listpad is not None and self.borders == False:
			self.stdscr.addch(self.listpadypos - 1, 0, " ")
			self.stdscr.addch(self.listpadypos - 1, self.maxx, " ")

		if self.logpad is not None:
			if self.logpadypos > 2:
				window_tee_hline(self.stdscr, self.logpadypos - 1, 0, self.maxx)
			if self.borders == True:
				window_tee_hline(self.stdscr, self.maxy - 2, 0, self.maxx)
				if self.tspad is not None and self.tspadxpos != self.logpadxpos and self.loglen > 0:
					window_tee_vline(self.stdscr, self.logpadxpos - 1, self.logpadypos - 1, self.maxy - 2)
			else:
				# If the window lacks sideborders we want lines
				self.stdscr.addch(self.logpadypos - 1, 0, _hline)
				self.stdscr.addch(self.logpadypos - 1, self.maxx, _hline)

		self.reset_update_delay()

	def update_timestamp(self, ypos, xpos, ralign = False):
		_ltee = theme["boxdrawing"].get("ltee", curses.ACS_LTEE)
		_rtee = theme["boxdrawing"].get("rtee", curses.ACS_RTEE)
		lastupdatestr = "%s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
		if ralign:
			xpos -= len(lastupdatestr)
			if self.borders == True:
				xpos -= 2
		self.stdscr.addch(0, xpos, _rtee)
		self.stdscr.addstr(lastupdatestr, attr_to_curses_merged("main", "last_update"))
		if self.borders == True:
			self.stdscr.addch(_ltee)

	def draw_winheader(self):
		_ltee = theme["boxdrawing"].get("ltee", curses.ACS_LTEE)
		_rtee = theme["boxdrawing"].get("rtee", curses.ACS_RTEE)
		if self.windowheader != "":
			winheaderarray = [("separators", "mainheader_prefix")]
			winheaderarray.append((f"{self.windowheader}", ("main", "header")))
			winheaderarray.append(("separators", "mainheader_suffix"))
			if self.borders == True:
				self.stdscr.addch(0, 1, _rtee)
				self.addthemearray(self.stdscr, winheaderarray, y = 0, x = 2)
			else:
				self.addthemearray(self.stdscr, winheaderarray, y = 0, x = 0)
			if self.extra_status is not None:
				self.stdscr.addch(_vline)
				extra_msg, extra_status = self.extra_status
				self.stdscr.addstr(extra_msg, color_status_group(extra_status, False))
			self.stdscr.addch(_ltee)

	def refresh_window(self):
		_ltee = theme["boxdrawing"].get("ltee", curses.ACS_LTEE)
		_rtee = theme["boxdrawing"].get("rtee", curses.ACS_RTEE)
		_vline = theme["boxdrawing"].get("vline", curses.ACS_VLINE)
		_hline = theme["boxdrawing"].get("hline", curses.ACS_HLINE)
		_bl = theme["boxdrawing"].get("llcorner", curses.ACS_LLCORNER)
		_br = theme["boxdrawing"].get("lrcorner", curses.ACS_LRCORNER)

		if self.borders == True:
			self.stdscr.addch(self.maxy - 2, 0, _bl)
			self.stdscr.addch(self.maxy - 2, self.maxx, _br)

		# The extra status can change, so we need to update the windowheader (which shouldn't change)
		self.draw_winheader()

		mousestatus = "On" if get_mousemask() == -1 else "Off"
		mousearray = [
			("Mouse: ", ("statusbar", "infoheader")), (f"{mousestatus}", ("statusbar", "highlight"))
		]
		xpos = self.maxx - themearray_get_length(mousearray) + 1
		if self.statusbar is not None:
			self.addthemearray(self.statusbar, mousearray, y = 0, x = xpos)
		ycurpos = self.curypos + self.yoffset
		maxypos = self.maxcurypos + self.maxyoffset
		if ycurpos != 0 or maxypos != 0:
			curposarray = [
				("Line: ", ("statusbar", "infoheader")), (f"{ycurpos + 1}".rjust(len(str(maxypos + 1))), ("statusbar", "highlight")), ("separators", "statusbar_fraction"), (f"{maxypos + 1}", ("statusbar", "highlight"))
			]
			xpos = self.maxx - themearray_get_length(curposarray) + 1
			if self.statusbar is not None:
				self.addthemearray(self.statusbar, curposarray, y = 1, x = xpos)
		self.stdscr.noutrefresh()

	# This should be called when a resize event is detected
	def resize_window(self):
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

	def refresh_all(self):
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
	def init_infopad(self, height, width, ypos, xpos, labels = None, annotations = None):
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
	def resize_infopad(self, height, width):
		self.infopadminwidth = self.maxx - self.infopadxpos
		if height != -1:
			self.infopadheight = height
		self.infopad.erase()
		if width != -1:
			self.infopadwidth = max(width, self.infopadminwidth)
		self.infopad.resize(max(self.infopadheight, self.maxy), self.infopadwidth)

	def refresh_infopad(self):
		if self.infopad is not None:
			height = self.infopadheight
			if self.borders == True:
				if self.logpad is None and self.listpad is None:
					height = self.maxy - 3
				self.infopad.noutrefresh(0, 0, self.infopadypos, self.infopadxpos, height, self.maxx - 1)
			else:
				if self.logpad is None and self.listpad is None:
					height = self.maxy - 2
				self.infopad.noutrefresh(0, 0, self.infopadypos, self.infopadxpos - 1, height, self.maxx)

			# If there's no logpad and no listpad, then the infopad is responsible for scrollbars
			if self.listpad is None and self.logpad is None and self.borders == True:
				self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, self.maxx, self.infopadypos, self.maxy - 3, self.infopadheight, self.yoffset, attr_to_curses_merged("main", "boxdrawing"))
				self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, self.maxy - 2, self.infopadxpos, self.maxx - 1, self.infopadwidth - 1, self.xoffset, attr_to_curses_merged("main", "boxdrawing"))

	# For (optionally) scrollable lists of information,
	# optionally with a header
	# Pass -1 as width to use listpadminwidth
	def init_listpad(self, listheight, width, ypos, xpos, header = True):
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
		self.listpadheight = listheight
		self.listpadwidth = max(width, self.listpadminwidth)
		self.listpad = curses.newpad(max(self.listpadheight, self.maxy), self.listpadwidth)
		self.selected = None

		return self.headerpad, self.listpad

	# Pass -1 to keep the current height/width
	def resize_listpad(self, height, width):
		self.listpadminwidth = self.maxx
		if height != -1:
			self.listpadheight = height
		else:
			height = self.listpadheight
		self.listpad.erase()
		if width != -1:
			self.listpadwidth = max(width + 1, self.listpadminwidth)
		else:
			width = self.listpadwidth

		if self.borders == True:
			self.maxcurypos = min(height - 1, self.maxy - self.listpadypos - 3)
		else:
			self.maxcurypos = min(height - 1, self.maxy - self.listpadypos - 2)
		self.maxyoffset = height - (self.maxcurypos - self.mincurypos) - 1
		self.headerpadwidth = self.listpadwidth
		self.maxxoffset = max(0, self.listpadwidth - self.listpadminwidth)

		if self.headerpadheight > 0:
			self.headerpad.resize(self.headerpadheight, self.headerpadwidth)
		if self.listpadheight > 0:
			self.listpad.resize(max(self.listpadheight, self.maxy), self.listpadwidth)
		self.curypos = min(self.curypos, self.maxcurypos)
		self.yoffset = min(self.yoffset, self.maxyoffset)

	def refresh_listpad(self):
		xpos = self.listpadxpos
		maxx = self.maxx - 1
		if self.borders == False:
			xpos -= 1
			maxx = self.maxx
		if self.headerpad is not None:
			self.headerpad.noutrefresh(0, self.xoffset, self.headerpadypos, xpos, self.headerpadypos, maxx)
		if self.listpad is not None:
			if self.borders == True:
				self.listpad.noutrefresh(self.yoffset, self.xoffset, self.listpadypos, xpos, self.maxy - 3, maxx)
				self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, x = maxx + 1, miny = self.listpadypos, maxy = self.maxy - 3, height = self.listpadheight, yoffset = self.yoffset, clear_color = attr_to_curses_merged("main", "boxdrawing"))
				self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, y = self.maxy - 2, minx = self.listpadxpos, maxx = maxx, width = self.listpadwidth - 1, xoffset = self.xoffset, clear_color = attr_to_curses_merged("main", "boxdrawing"))
			else:
				self.listpad.noutrefresh(self.yoffset, self.xoffset, self.listpadypos, xpos, self.maxy - 2, maxx)

	# Recalculate the xpos of the log; this is needed when timestamps are toggled
	def recalculate_logpad_xpos(self, tspadxpos = -1, timestamps = None):
		if tspadxpos == -1:
			if self.tspadxpos is None:
				raise Exception("logpad is not initialised and no tspad xpos provided")

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
	def init_logpad(self, width, ypos, xpos, timestamps = True):
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
	# Calling this function directly isn't necessary; the pad never grows down, and self.addstr() calls this when x grows
	def resize_logpad(self, height, width):
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
			self.logpad.resize(self.logpadheight + 1, self.logpadwidth + 1)
		self.maxyoffset = max(0, self.loglen - self.logpadheight)
		self.maxxoffset = max(0, self.logpadwidth - self.logpadminwidth)
		self.yoffset = min(self.yoffset, self.maxyoffset)

	def refresh_logpad(self):
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
			_hline = theme["boxdrawing"].get("hline", curses.ACS_HLINE)
			if self.borders == True:
				for i in range(0, self.tspadwidth):
					self.stdscr.addch(self.maxy - 2, 1 + i, _hline)
				self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos, self.maxy - 3, self.tspadwidth)
			else:
				self.tspad.noutrefresh(0, 0, self.tspadypos, tspadxpos, self.maxy - 2, self.tspadwidth - 1)
		if self.borders == True:
			self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos, self.maxy - 3, self.maxx - 1)
			self.upperarrow, self.lowerarrow, self.vdragger = scrollbar_vertical(self.stdscr, self.maxx, self.logpadypos, self.maxy - 3, self.loglen, self.yoffset, attr_to_curses_merged("main", "boxdrawing"))
			self.leftarrow, self.rightarrow, self.hdragger = scrollbar_horizontal(self.stdscr, self.maxy - 2, logpadxpos, self.maxx - 1, self.logpadwidth, self.xoffset, attr_to_curses_merged("main", "boxdrawing"))
		else:
			self.logpad.noutrefresh(0, self.xoffset, self.logpadypos, logpadxpos, self.maxy - 2, self.maxx)

	def toggle_timestamps(self, timestamps = None):
		if timestamps is None:
			timestamps = self.tspadxpos == self.logpadxpos

		self.recalculate_logpad_xpos(tspadxpos = self.tspadxpos, timestamps = timestamps)

	def toggle_borders(self, borders = None):
		if borders is None:
			self.borders = not self.borders
		else:
			self.borders = borders

		self.recalculate_logpad_xpos(tspadxpos = self.tspadxpos)

	def init_statusbar(self):
		self.resize_statusbar()

		return self.statusbar

	def refresh_statusbar(self):
		if self.statusbar is not None:
			col, __discard = attr_to_curses("statusbar", "default")
			self.statusbar.bkgd(" ", col)
			self.statusbar.noutrefresh(0, 0, self.statusbarypos, 0, self.maxy, self.maxx)

	def resize_statusbar(self):
		self.statusbarypos = self.maxy - 1
		if self.statusbar is not None:
			self.statusbar.erase()
			self.statusbar.resize(2, self.maxx + 1)
		else:
			self.statusbar = curses.newpad(2, self.maxx + 1)

	def addstr(self, win, string, y = -1, x = -1, attribute = curses.A_NORMAL):
		cury, curx = win.getyx()
		winmaxy, winmaxx = win.getmaxyx()
		newmaxy = max(y, winmaxy)
		newmaxx = max(winmaxx, len(string) + curx + 1)

		if win != self.stdscr:
			win.resize(newmaxy, newmaxx)
		elif win == self.stdscr and (winmaxy, winmaxx) != (newmaxy, newmaxx):
			# If there's an attempt to print a message that would resize the window,
			# just pretend success instead of raising an exception
			cury, curx = win.getyx()
			return cury, curx
		if y == -1:
			y = cury
		if x == -1:
			x = curx
		try:
			win.addstr(y, x, string, attribute)
		except Exception as e:
			raise Exception(f"{e}\n  y: {y}\n  x: {x}\n  string: |{string}|\n  length: {len(string)}\n  attribute: {attribute}")

		cury, curx = win.getyx()
		return cury, curx

	def addarray(self, win, array, y = -1, x = -1):
		# This way we can print a single (string, attr) too
		if type(array) == tuple:
			array = [array]

		for string, attr in array:
			if type(attr) == tuple:
				raise Exception(f"addarray() called with attr: {attr} (type: tuple); must be integer")
			y, x = self.addstr(win, string, y, x, attr)
		return y, x

	# addthemearray() takes an array as input.
	# The elements in the array can be:
	# (string, (context, theme_attr_ref)),
	# (string, (context, theme_attr_ref), selected),
	# (string, (context, curses_attr)),
	# (context, theme_ref),
	# (context, theme_ref, selected),
	def addthemearray(self, win, array, y = -1, x = -1, selected = False):
		for item in array:
			if type(item) != tuple:
				raise Exception(f"unexpected item-type passed to addthemearray):\ntype(item): {type(item)}\nitem: {item}\narray: {array}")

			if len(item) == 3:
				_p1, _p2, _selected = item
			else:
				_p1, _p2 = item
				_selected = selected

			if type(_p2) == tuple:
				string = _p1
				if len(_p2) == 3:
					context, _p3, _selected = _p2
				else:
					context, _p3 = _p2
				if type(_p3) == int:
					attr = _p3
				else:
					attr = attr_to_curses_merged(context, _p3, selected = _selected)
				y, x = self.addstr(win, string, y, x, attr)
			elif type(_p2) == int:
				string = _p1
				attr = _p2
				y, x = self.addstr(win, string, y, x, attr)
			else:
				if type(_p1) == tuple:
					context, attr_ref = _p1
					_selected = _p2
				else:
					attr_ref = _p2
					context = _p1
					_selected = selected

				strarray = themearray_to_strarray(attr_ref, context = context, selected = _selected)
				y, x = self.addarray(win, strarray, y = y, x = x)
		return y, x

	def move_xoffset_abs(self, position):
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

	def move_yoffset_abs(self, position):
		if position == -1:
			self.yoffset = self.maxyoffset
		elif position == 0:
			self.yoffset = 0
		else:
			self.yoffset = max(0, position)
			self.yoffset = min(self.yoffset, self.maxyoffset)
		self.refresh = True

	def move_xoffset_rel(self, movement):
		if self.borders == True:
			sideadjust = 0
		else:
			sideadjust = 2
		self.xoffset = max(0, self.xoffset + movement)
		self.xoffset = min(self.xoffset, self.maxxoffset - sideadjust)
		self.refresh = True

	def move_yoffset_rel(self, movement):
		self.yoffset = max(0, self.yoffset + movement)
		self.yoffset = min(self.maxyoffset, self.yoffset)
		self.refresh = True

	def move_cur_abs(self, position):
		if position == -1:
			self.curypos = self.maxcurypos
			self.yoffset = self.maxyoffset
		elif position == 0:
			self.curypos = self.mincurypos
			self.yoffset = 0
		else:
			raise Exception("FIXME")

	def move_cur_with_offset(self, movement):
		newcurypos = self.curypos + movement
		newyoffset = self.yoffset

		# If we are being asked to move forward but we're already
		# at the end of the list, it's prudent not to move,
		# even if the caller so requests.
		# It's just good manners, really.
		if self.yoffset + newcurypos > self.listpadheight:
			newcurypos = min(newcurypos, self.maxcurypos)
			newyoffset = self.maxyoffset
		elif newcurypos > self.maxcurypos:
			newyoffset = min(self.yoffset - (self.maxcurypos - newcurypos), self.maxyoffset)
			newcurypos = self.maxcurypos
		elif newcurypos < self.mincurypos:
			newyoffset = max(self.yoffset + (newcurypos - self.mincurypos), 0)
			newcurypos = self.mincurypos
		else:
			newoffset = self.yoffset

		self.curypos = newcurypos
		self.yoffset = newyoffset

	# Find the next line that matches the search criteria
	def find_next_line_by_searchkey(self, messages, searchkey):
		y = 0
		newoffset = self.yoffset

		if searchkey == "":
			return

		for message in messages:
			# The messages can either be raw strings,
			# or themearrays, so we need to flatten them to just text first
			message = themearray_get_string(message)
			# We're only searching forward
			if y > self.yoffset and searchkey in message:
				newoffset = y
				break
			y += 1

		self.yoffset = min(newoffset, self.maxyoffset)

	# Find the prev line that matches the search criteria
	def find_prev_line_by_searchkey(self, messages, searchkey):
		y = 0
		newoffset = self.yoffset

		if searchkey == "":
			return

		for message in messages:
			# The messages can either be raw strings,
			# or themearrays, so we need to flatten them to just text first
			message = themearray_get_string(message)
			# We're only searching backward
			if y == self.yoffset:
				break
			if searchkey in message:
				newoffset = y
			y += 1

		self.yoffset = min(newoffset, self.maxyoffset)

	# Find the next line that has severity > NOTICE
	def next_line_by_severity(self, severities):
		y = 0
		newoffset = self.yoffset

		if severities is None:
			return

		for severity in severities:
			# We're only searching forward
			if y > self.yoffset and severity < loglevel.NOTICE:
				newoffset = y
				break
			y += 1

		self.yoffset = min(newoffset, self.maxyoffset)
		self.refresh = True

	# Find the prev line that has severity > NOTICE
	def prev_line_by_severity(self, severities):
		y = 0
		newoffset = self.yoffset

		if severities is None:
			return

		for severity in severities:
			# We're only searching backward
			if y == self.yoffset:
				break
			if severity < loglevel.NOTICE:
				newoffset = y
			y += 1

		self.yoffset = newoffset
		self.refresh = True

	def next_by_sortkey(self, info):
		if self.sortkey1 is None:
			return

		pos = self.curypos + self.yoffset
		y = 0
		newpos = 0
		current = None
		sortkey1, sortkey2 = self.get_sortkeys()
		sortkey = sortkey2 if sortkey1 == "status_group" else sortkey1

		# Search forward within sort category
		# next namespace when sorted by namespace
		# next (existing) letter when sorted by name
		# next status when sorted by status
		# next node when sorted by node
		for entry in sorted(info, key = attrgetter(sortkey1, sortkey2)):
			# OK, from here we want to go to next entry
			if y == pos:
				if sortkey == "age" or self.sortkey1 == "seen":
					current = iktlib.seconds_to_age(getattr(entry, sortkey))
				else:
					current = getattr(entry, sortkey)
			elif y > pos:
				if sortkey == "name":
					if current[0] != entry.name[0]:
						newpos = y - pos
						break
				elif sortkey == "age" or self.sortkey1 == "seen":
					if current != iktlib.seconds_to_age(getattr(entry, sortkey)):
						newpos = y - pos
						break
				else:
					if current != getattr(entry, sortkey):
						newpos = y - pos
						break
			y += 1

		# If we don't match we'll just end up with the old pos
		self.move_cur_with_offset(newpos)

	def prev_by_sortkey(self, info):
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
		for entry in sorted(info, key = attrgetter(sortkey1, sortkey2)):
			if current is None:
				if sortkey == "age" or self.sortkey1 == "seen":
					current = iktlib.seconds_to_age(getattr(entry, sortkey))
				else:
					current = getattr(entry, sortkey)

			if y == pos:
				break

			if sortkey == "name":
				if current[0] != entry.name[0]:
					current = entry.name
					newpos = y - pos
			elif sortkey == "age":
				if current != iktlib.seconds_to_age(getattr(entry, sortkey)):
					current = iktlib.seconds_to_age(getattr(entry, sortkey))
					newpos = y - pos
			else:
				if current != getattr(entry, sortkey):
					current = getattr(entry, sortkey)
					newpos = y - pos
			y += 1

		# If we don't match we'll just end up with the old pos
		if newpos == 0:
			self.move_cur_abs(0)
		else:
			self.move_cur_with_offset(newpos)

	def find_next_by_sortkey(self, info, searchkey):
		pos = self.curypos + self.yoffset
		offset = 0

		# Search within sort category
		sorted_list = sorted(info, key = attrgetter(self.sortkey1, self.sortkey2))
		for y in range(pos, len(sorted_list)):
			tmp2 = getattr(sorted_list[y], self.sortcolumn)
			if self.sortkey1 == "age" or self.sortkey1 == "seen":
				tmp2 = iktlib.seconds_to_age(tmp2)
			else:
				tmp2 = str(tmp2)
			tmp2 = tmp2[0:len(searchkey)].rstrip().lower()
			if searchkey == tmp2:
				offset = y - pos
				if offset > 0:
					break

		# If we don't match we'll just end up with the old pos
		self.move_cur_with_offset(offset)

	def find_prev_by_sortkey(self, info, searchkey):
		pos = self.curypos + self.yoffset
		offset = 0

		# Search within sort category
		sorted_list = sorted(info, key = attrgetter(self.sortkey1, self.sortkey2))
		for y in reversed(range(0, pos)):
			tmp2 = getattr(sorted_list[y], self.sortcolumn)
			if self.sortkey1 == "age" or self.sortkey1 == "seen":
				tmp2 = iktlib.seconds_to_age(tmp2)
			else:
				tmp2 = str(tmp2)
			tmp2 = tmp2[0:len(searchkey)].rstrip().lower()
			if searchkey == tmp2:
				offset = y - pos
				if offset < 0:
					break

		# If we don't match we'll just end up with the old pos
		self.move_cur_with_offset(offset)

	# This function is used to find the first match based on command line input
	# The sort order used will still be the default, to ensure that the partial
	# match ends up being the first.
	def goto_first_match_by_name_namespace(self, name, namespace):
		if self.info is None or name is None or len(name) == 0 or hasattr(self.info, "name") == False:
			return None

		# Search within sort category
		sorted_list = sorted(self.info, key = attrgetter(self.sortkey1, self.sortkey2))
		first_match = None
		unique_match = None
		match_count = 0

		for y in range(0, len(sorted_list)):
			if hasattr(sorted_list[0],  "namespace"):
				if namespace is not None and sorted_list[y].namespace != namespace:
					continue

			if sorted_list[y].name == name:
				first_match = y
				match_count = 1
				break
			elif sorted_list[y].name.startswith(name):
				if first_match == None:
					first_match = y
				match_count += 1

		if first_match is not None:
			self.move_cur_with_offset(first_match)
		if match_count == 1:
			unique_match = sorted_list[self.curypos + self.yoffset].ref

		return unique_match

	def next_sortcolumn(self):
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

	def prev_sortcolumn(self):
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

	def get_sortcolumn(self):
		return self.sortcolumn

	def get_sortkeys(self):
		if self.field_list is None:
			return None, None

		field = self.field_list.get(self.sortcolumn)

		if field is None:
			valid_fields = []
			for f in self.field_list:
				valid_fields.append(f)
			raise Exception(f"Invalid sortcolumn: {self.sortcolumn} does not exist in field_list:\nvalid fields are: {valid_fields}")
		else:
			sortkey1 = self.field_list[self.sortcolumn]["sortkey1"]
			sortkey2 = self.field_list[self.sortcolumn]["sortkey2"]
			if sortkey1 == "status":
				sortkey1 = "status_group"
				sortkey2 = "status"
			return sortkey1, sortkey2

	def handle_mouse_events(self, win, sorted_list, activatedfun, extraref, data):
		try:
			eventid, x, y, z, bstate = curses.getmouse()
		except curses.error as e:
			return False

		if win == self.listpad:
			if self.listpad is None:
				return False
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
			# We don't care about selection
			selections = False
		else:
			return False

		cmaxy = self.maxy
		cmaxx = self.maxx
		cyoffset = self.yoffset
		ypos = y - cypos
		xpos = x - cxpos

		#if bstate == curses.BUTTON1_PRESSED:
			# Here goes handling of dragging scrollbars
		if bstate == curses.BUTTON1_DOUBLE_CLICKED and selections == True:
			# double-clicks on list items
			if activatedfun is not None and y >= cypos and y < min(cheight + cypos, cmaxy) and x >= cxpos and x < cmaxx:
				selected = sorted_list[ypos + cyoffset]
				self.select(selected)
				self.curypos = ypos

				if selected.ref is not None:
					if extraref is not None:
						view = getattr(selected, extraref, self.view)

						if data is not None:
							retval = activatedfun(self.stdscr, selected.ref, view, info = data)
						else:
							retval = activatedfun(self.stdscr, selected.ref, view)
					else:
						retval = activatedfun(self.stdscr, selected.ref, self.view)
					if retval != None:
						self.force_update()
					return retval
		elif bstate == curses.BUTTON1_CLICKED:
			# clicks on list items
			if y >= cypos and y < min(cheight + cypos, cmaxy) and x >= cxpos and x < cmaxx and selections == True:
				selected = self.get_selected()

				# If we're clicking on something that isn't selected (or if nothing is selected), move here
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

							if data is not None:
								retval = activatedfun(self.stdscr, selected.ref, view, info = data)
							else:
								retval = activatedfun(self.stdscr, selected.ref, view)
						else:
							retval = activatedfun(self.stdscr, selected.ref, self.view)
						if retval != None:
							self.force_update()
						return retval
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
				if y > self.upperarrow[0] and y < self.lowerarrow[0]:
					# Don't count the arrows
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
				if x > self.leftarrow[1] and x < self.rightarrow[1]:
					# Don't count the arrows
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
			return True
		elif curses_configuration.mousescroll_enable and bstate == curses_configuration.mousescroll_down:
			if self.listpad is not None:
				self.move_cur_with_offset(5)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(5)
			return True

		return False

	def enter_handler(self, activatedfun, extraref, data):
		selected = self.get_selected()

		if activatedfun is not None and selected is not None and selected.ref is not None:
			if extraref is not None:
				view = getattr(selected, extraref, self.view)

				if data is not None:
					retval = activatedfun(self.stdscr, selected.ref, view, info = data)
				else:
					retval = activatedfun(self.stdscr, selected.ref, view)
			else:
				retval = activatedfun(self.stdscr, selected.ref, self.view)
			if retval != None:
				self.force_update()
			return retval

		return False

	def generic_keycheck(self, c):
		if c == curses.KEY_RESIZE:
			self.resize_window()
			return retval.MATCH
		elif c == 27:	# ESCAPE
			del self
			return retval.RETURNONE
		elif c == curses.KEY_MOUSE:
			return self.handle_mouse_events(self.listpad, self.sorted_list, self.activatedfun, self.extraref, self.data)
		elif c == curses.KEY_ENTER or c == 10 or c == 13:
			return self.enter_handler(self.activatedfun, self.extraref, self.data)
		elif c == ord("M"):
			# Toggle mouse support on/off to allow for copy'n'paste
			if get_mousemask() == 0:
				set_mousemask(-1)
			else:
				set_mousemask(0)
			self.statusbar.erase()
			self.refresh_all()
			return retval.MATCH
		elif c == ord("") or c == ord(""):
			sys.exit()
		elif c == curses.KEY_F1 or c == ord("H"):
			if self.helptext is not None:
				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2, self.helptext, title = "Help", cursor = False)
			self.refresh_all()
			return retval.MATCH
		elif c == curses.KEY_F12:
			if curses_configuration.abouttext is not None:
				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2, curses_configuration.abouttext, title = "About", cursor = False)
			self.refresh_all()
			return retval.MATCH
		elif c == curses.KEY_F5:
			# We need to rate limit this somehow
			self.force_update()
			return retval.MATCH
		elif c == ord("r"):
			# Reverse the sort order
			if self.listpad is not None and self.reversible == True:
				self.sortorder_reverse = not self.sortorder_reverse
		elif c == curses.KEY_SLEFT:
			# For listpads we switch sort column with this; for logpads we move half a page left/right
			if self.listpad is not None:
				self.prev_sortcolumn()
			elif self.logpad is not None and self.continuous_log == False:
				self.move_xoffset_rel(-(self.logpadminwidth // 2))
			return retval.MATCH
		elif c == curses.KEY_SRIGHT:
			if self.listpad is not None:
				self.next_sortcolumn()
			elif self.logpad is not None and self.continuous_log == False:
				self.move_xoffset_rel(self.logpadminwidth // 2)
			return retval.MATCH
		elif c == curses.KEY_UP:
			if self.listpad is not None:
				self.move_cur_with_offset(-1)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(-1)
			return retval.MATCH
		elif c == curses.KEY_DOWN:
			if self.listpad is not None:
				self.move_cur_with_offset(1)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(1)
			return retval.MATCH
		elif c == curses.KEY_LEFT:
			if self.logpad is not None and self.continuous_log:
				return retval.MATCH

			self.move_xoffset_rel(-1)
			return retval.MATCH
		elif c == curses.KEY_RIGHT:
			if self.logpad is not None and self.continuous_log:
				return retval.MATCH

			self.move_xoffset_rel(1)
			return retval.MATCH
		elif c == curses.KEY_HOME:
			if self.logpad is not None and self.continuous_log:
				return retval.MATCH

			self.move_xoffset_abs(0)
			return retval.MATCH
		elif c == curses.KEY_END:
			if self.logpad is not None and self.continuous_log:
				return retval.MATCH

			self.move_xoffset_abs(-1)
			return retval.MATCH
		elif c == curses.KEY_SHOME:
			if self.logpad is not None:
				if self.continuous_log:
					return retval.MATCH
				else:
					self.move_yoffset_abs(0)
			elif self.listpad is not None:
				self.move_cur_abs(0)
			return retval.MATCH
		elif c == curses.KEY_SEND:
			if self.logpad is not None:
				if self.continuous_log:
					return retval.MATCH
				else:
					self.move_yoffset_abs(-1)
			elif self.listpad is not None:
				self.move_cur_abs(-1)
			return retval.MATCH
		elif c == curses.KEY_PPAGE:
			if self.listpad is not None:
				self.move_cur_with_offset(-10)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(-(self.logpadheight - 2))
			return retval.MATCH
		elif c == curses.KEY_NPAGE:
			if self.listpad is not None:
				self.move_cur_with_offset(10)
			elif self.logpad is not None and self.continuous_log == False:
				self.move_yoffset_rel(self.logpadheight - 2)
			return retval.MATCH
		elif c == ord("\t"):
			if self.listpad is not None:
				self.next_by_sortkey(self.info)
			elif self.logpad is not None and self.continuous_log == False:
				self.next_line_by_severity(self.severities)
			return retval.MATCH
		elif c == curses.KEY_BTAB:
			if self.listpad is not None:
				self.prev_by_sortkey(self.info)
			elif self.logpad is not None and self.continuous_log == False:
				self.prev_line_by_severity(self.severities)
			return retval.MATCH
		elif c == ord("") or c == ord("/"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return retval.MATCH

				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Search in '%s': " % (self.sortcolumn)).rstrip().lower()
				if searchkey is None or searchkey == "":
					return retval.MATCH

				self.find_next_by_sortkey(self.info, searchkey)
				self.searchkey = searchkey
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return retval.MATCH

				self.refresh = True
				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Find: ")
				if searchkey is None or searchkey == "":
					return retval.MATCH

				self.find_next_line_by_searchkey(self.messages, searchkey)
				# For use when searching for next match
				self.searchkey = searchkey
			return retval.MATCH
		elif c == ord("?"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return retval.MATCH

				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Search in '%s': " % (self.sortcolumn)).rstrip().lower()
				if searchkey is None or searchkey == "":
					return retval.MATCH

				self.find_prev_by_sortkey(self.info, searchkey)
				self.searchkey = searchkey
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return retval.MATCH

				self.refresh = True
				searchkey = inputbox(self.stdscr, self.maxy // 2, 1, self.maxy - 1, self.maxx - 1, "Find: ")
				if searchkey is None or searchkey == "":
					return retval.MATCH

				self.find_prev_line_by_searchkey(self.messages, searchkey)
				# For use when searching for next match
				self.searchkey = searchkey
			return retval.MATCH
		elif c == ord("n"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return retval.MATCH

				if self.searchkey is None or self.searchkey == "":
					return retval.MATCH

				self.find_next_by_sortkey(self.info, self.searchkey)
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return retval.MATCH

				self.refresh = True
				if self.searchkey is None or self.searchkey == "":
					return retval.MATCH

				self.find_next_line_by_searchkey(self.messages, self.searchkey)
			return retval.MATCH
		elif c == ord("p"):
			if self.listpad is not None:
				if self.listpadheight < 2:
					return retval.MATCH

				if self.searchkey is None or self.searchkey == "":
					return retval.MATCH

				self.find_prev_by_sortkey(self.info, self.searchkey)
			elif self.logpad is not None:
				if self.maxyoffset == 0 or self.continuous_log:
					return retval.MATCH

				self.refresh = True
				if self.searchkey is None or self.searchkey == "":
					return retval.MATCH

				self.find_prev_line_by_searchkey(self.messages, self.searchkey)
			return retval.MATCH
		elif c == ord("a"):
			if self.annotations is not None:
				title = ""

				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2, self.annotations, headers = annotation_headers, title = title, cursor = False)

				self.refresh_all()
				return retval.MATCH
		elif c == ord("l"):
			if self.labels is not None:
				title = ""

				windowwidget(self.stdscr, self.maxy, self.maxx, self.maxy // 2, self.maxx // 2, self.labels, headers = label_headers, title = title, cursor = False)

				self.refresh_all()
				return retval.MATCH

		# Nothing good enough for you, eh?
		return retval.NOMATCH
