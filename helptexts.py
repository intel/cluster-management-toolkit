#! /usr/bin/env python3

"""
This module contains helptexts for cmu
"""

from about import PROGRAM_SUITE_FULL_NAME, PROGRAM_SUITE_VERSION, UI_PROGRAM_NAME, UI_PROGRAM_VERSION

from ansithemeprint import ANSIThemeString
from curses_helper import ThemeAttr, ThemeString

# Improve to handle embedded color codes; probably through storing the log messages
# as a list of lines

about = [
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString("    ◢███ ██████  ████ ◣  ◢█████  ████ █████████    ", ThemeAttr("main", "logo_dark"))]),
	(0, [ThemeString("    ████         ████ █◣◢██████       ████         ", ThemeAttr("main", "logo_medium"))]),
	(0, [ThemeString("    ████         ████ ████◤████       ████         ", ThemeAttr("main", "logo_bright"))]),
	(0, [ThemeString("    ████         ████ ◥██◤ ████       ████         ", ThemeAttr("main", "logo_medium"))]),
	(0, [ThemeString("    ◥███ ██████  ████  ◥◤  ████       ████         ", ThemeAttr("main", "logo_dark"))]),
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(f" {PROGRAM_SUITE_FULL_NAME} ", ThemeAttr("main", "about_text_highlight")), ThemeString("v", ThemeAttr("main", "about_text")), ThemeString(f"{PROGRAM_SUITE_VERSION} ", ThemeAttr("main", "about_version"))]), # pylint: disable=line-too-long
	(0, [ThemeString(f" {UI_PROGRAM_NAME} ", ThemeAttr("main", "about_text_highlight")), ThemeString("v", ThemeAttr("main", "about_text")), ThemeString(f"{UI_PROGRAM_VERSION}", ThemeAttr("main", "about_version"))]), # pylint: disable=line-too-long
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Copyright © 2019-2023 Intel Corporation", ThemeAttr("main", "about_text_highlight"))]),
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Author(s):", ThemeAttr("main", "about_text_highlight"))]),
	(0, [ThemeString(" David Weinehall", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Testing:", ThemeAttr("main", "about_text_highlight"))]),
	(0, [ThemeString(" Valtteri Rantala", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Ukri Niemimuukko", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Eero Tamminen", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString(" Alexey Fomenko", ThemeAttr("main", "about_text"))]),
	(0, [ThemeString("", ThemeAttr("main", "about_text"))]),
]

toggleborders = [
	("[Shift] + B", "Toggle borders"),
]

togglewidth = [
	("[Shift] + W", "Toggle custom/narrow/normal/wide fields (when available)"),
]

listviewheader = [
	("[Ctrl] + X", "Exit program"),
	("[Shift] + M", "Toggle mouse on/off"),
] + togglewidth + toggleborders + [
	("", ""),
	("[F1] / [Shift] + H", "Show this helptext"),
	("[F2]", "Switch main view"),
	("[F3]", "Switch main view (recheck available API resources)"),
	("[F5]", "Refresh list"),
	("[F7]", "Perform Cluster-wide actions"),
	("[F12]", "Show information about the program"),
	("", ""),
]

openresource = [
	("[Enter]", "Open info page for selected resource"),
]

tagactions = [
	("T", "Tag / Untag item"),
	("[Shift] + T", "Tag item by pattern"),
	("[Ctrl] + T", "Untag item by pattern"),
	("[Shift] + L", "List tagged items"),
	(";", "Perform action on tagged items"),
]

selectoractions = [
	("L", "Show labels for all tagged items"),
	("F", "Select labels and filter by label selector"),
	("[Shift] + F", "Clear label selector"),
]

infoviewheader_part1 = [
	("[ESC]", "Return to previous screen"),
	("[Ctrl] + X", "Exit program"),
	("[Shift] + M", "Toggle mouse on/off"),
]
infoviewheader_part2 = [
] + toggleborders + [
	("", ""),
	("[F1] / [Shift] + H", "Show this helptext"),
	("[F2]", "Switch main view"),
	("[F3]", "Switch main view (recheck available API resources)"),
	("[F5]", "Refresh information"),
	("[F12]", "Show information about the program"),
]

irreversiblelistmovement = [
	("[Left]", "Scroll left"),
	("[Right]", "Scroll right"),
	("[Down]", "Move to next row"),
	("[Up]", "Move to previous row"),
	("[Shift] + [Left]", "Change sortcolumn"),
	("[Shift] + [Right]", "Change sortcolumn"),
	("[Tab]", "Jump to next group in sortcolumn"),
	("[Shift] + [Tab]", "Jump to previous group in sortcolumn"),
	("§", "Jump to next sortcolumn"),
	("½", "Jump to previous sortcolumn"),
	("/", "Search forwards within column"),
	("N", "Search forwards for next match within column"),
	("?", "Search backwards within column"),
	("P", "Search backwards for previous match within column"),
	("[Page Up]", "Scroll 10 lines up"),
	("[Page Down]", "Scroll 10 lines down"),
	("[Shift] + [Home]", "Jump to beginning"),
	("[Shift] + [End]", "Jump to end"),
]

listmovement = [
	("R", "Reverse sortorder"),
] + irreversiblelistmovement

linewrap = [
	("[Shift] + W", "Toggle line wrapping"),
]

toggleformatter = [
	("[Shift] + R", "Toggle highlighting / formatting (default: On)"),
]

logmovement = [
	("[Cursor keys]", "Scroll log up / down / left / right"),
	("/", "Search forwards"),
	("N", "Search forwards for next match"),
	("?", "Search backwards"),
	("P", "Search backwards for previous match"),
	("[Page Up]", "Scroll one page up"),
	("[Page Down]", "Scroll one page down"),
	("[Shift] + [Home]", "Jump to beginning"),
	("[Shift] + [End]", "Jump to end"),
	("[Home]", "Jump to beginning of currently visible lines"),
	("[End]", "Jump to end of currently visible lines"),
	("[Shift] + [Left]", "Scroll a half page left"),
	("[Shift] + [Right]", "Scroll a half page right"),
]

annotations = [
	("A", "Show annotations"),
]

labels = [
	("L", "Show labels"),
]

spacer = [
	("", ""),
]

configmapdata = infoviewheader_part1 + infoviewheader_part2 + spacer + [
	("[Shift] + R", "Toggle highlighting / formatting (default: On)"),
] + spacer + logmovement

containerinfo = [
	("[ESC]", "Return to previous screen"),
	("", ""),
	("[F1]", "Show this helptext"),
	("[F2]", "Switch view"),
	("[F3]", "Switch main view (recheck available API resources)"),
	("[F4]", "Pause/Unpause the log (Default: Paused)"),
	("", "  Note: when tracking the log all manual movement is disabled."),
	("[F5]", "Refresh log"),
	("[F8]", "Load full log (Potentially very slow) (Default: limited)"),
	("[F12]", "Show information about the program"),
	("", ""),
	("[Shift] + I", "Open info page for container image"),
	("[Shift] + R", "Toggle highlighting / formatting (default: On)"),
	("[Shift] + T", "Toggle timestamps (default: On)"),
	("[Shift] + D", "Toggle merging of duplicate messages"),
] + linewrap + toggleborders + [
	("[Shift] + P", "Override logparser"),
	("", "  This allows for manually choosing the parser used; please report"),
	("", "  if a different parser than the default seems to be more appropriate"),
	("[Shift] + L", "Change log level"),
	("", "  All log messages with a severity lower than this will be filtered out"),
	("[Shift] + F", "Toggle log unfolding"),
	("", "  This affects log messages that contain multiple messages in one line;"),
	("", "  such messages are typical for structured log formats."),
	("", "  If this is enabled such messages will be split into multiple lines."),
	("[Shift] + V", "Change facility level"),
	("", ""),
	("[Shift] + E", "Export log to a file"),
	("", "  The log format is decided by current mode; if you are viewing the raw"),
	("", "  log it will be exported as such; otherwise the parsed log will be exported."),
	("", ""),
	("[Tab]", "Jump to next elevated severity"),
	("[Shift] + [Tab]", "Jump to previous elevated severity"),
] + spacer + logmovement

usage  = [ANSIThemeString("[", "separator"), ANSIThemeString("COMMAND", "command"), ANSIThemeString("]", "separator"),
	  ANSIThemeString(" [", "separator"), ANSIThemeString("OPTION", "option"), ANSIThemeString("]", "separator"), ANSIThemeString("...", "option"),
	  ANSIThemeString(" [", "separator"), ANSIThemeString("ARGUMENT", "argument"), ANSIThemeString("]", "separator"), ANSIThemeString("...\n", "argument")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("UI for managing Kubernetes clusters\n", "description")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("VIEW", "command"),
          ANSIThemeString("                     start in ", "description"), ANSIThemeString("VIEW\n", "command")]
usage += [ANSIThemeString("VIEW ", "command"), ANSIThemeString("NAME ", "argument"),
	  ANSIThemeString("[", "separator"), ANSIThemeString("NAMESPACE", "argument"), ANSIThemeString("]", "separator"),
          ANSIThemeString("    start in ", "description"), ANSIThemeString("VIEW", "command"),
	  ANSIThemeString(" for the object matching\n", "description")]
usage += [ANSIThemeString("                         NAME", "argument"), ANSIThemeString(" and, optionally, ", "description"), ANSIThemeString("NAMESPACE\n", "argument")]
usage += [ANSIThemeString("VIEW ", "command"), ANSIThemeString("NAMESPACE/NAME", "argument"),
          ANSIThemeString("      same as above; alternate syntax\n", "description")]
usage += [ANSIThemeString("pod ", "command"), ANSIThemeString("NAME NAMESPACE CONTAINER\n", "argument")]
usage += [ANSIThemeString("pod ", "command"), ANSIThemeString("[", "separator"), ANSIThemeString("NAMESPACE/", "argument"), ANSIThemeString("]", "separator"),
	  ANSIThemeString("NAME:", "argument"), ANSIThemeString("[", "separator"), ANSIThemeString("CONTAINER", "argument"), ANSIThemeString("]\n", "separator")]
usage += [ANSIThemeString("                         start in container info view matching\n", "description")]
usage += [ANSIThemeString("                         NAME", "argument"), ANSIThemeString(", ", "description"),
	  ANSIThemeString("NAMESPACE", "argument"), ANSIThemeString(", ", "description"),
	  ANSIThemeString("CONTAINER", "argument"), ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("configmap ", "command"), ANSIThemeString("NAME NAMESPACE CONFIGMAP\n", "argument")]
usage += [ANSIThemeString("configmap ", "command"), ANSIThemeString("[", "separator"), ANSIThemeString("NAMESPACE/", "argument"), ANSIThemeString("]", "separator"), # pylint: disable=line-too-long
	  ANSIThemeString("NAME:", "argument"), ANSIThemeString("[", "separator"), ANSIThemeString("CONFIGMAP", "argument"), ANSIThemeString("]\n", "separator")]
usage += [ANSIThemeString("                         start in the configmap info view matching\n", "description")]
usage += [ANSIThemeString("                         NAME", "argument"), ANSIThemeString(", ", "description"),
	  ANSIThemeString("NAMESPACE", "argument"), ANSIThemeString(", ", "description"),
	  ANSIThemeString("CONFIGMAP", "argument"), ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("list-views     ", "command"),
          ANSIThemeString("          list view information and exit\n", "description")]
usage += [ANSIThemeString("list-namespaces", "command"),
          ANSIThemeString("          list valid namespaces and exit\n", "description")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("Global Options:\n", "description")]
usage += [ANSIThemeString("  --read-only ", "option"),
          ANSIThemeString("           disable all commands that modify state", "description")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("  --namespace ", "option"), ANSIThemeString("NAMESPACE", "argument"),
          ANSIThemeString("  only show namespace ", "description"), ANSIThemeString("NAMESPACE\n", "argument")]
usage += [ANSIThemeString("\n", "description")]
usage += [ANSIThemeString("help", "command"), ANSIThemeString("|", "separator"), ANSIThemeString("--help", "command"),
          ANSIThemeString("              display this help and exit\n", "description")]
usage += [ANSIThemeString("version", "command"), ANSIThemeString("|", "separator"), ANSIThemeString("--version", "command"),
          ANSIThemeString("        output version information and exit\n", "description")]
