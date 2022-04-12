#! /usr/bin/env python3

import about

# Improve to handle embedded color codes; probably through storing the log messages
# as a list of lines

about = [
	(0, [("", ("main", "about_text"))]),
	(0, [("   ████   ", ("main", "logo_bullet")), ("████    ◢███◤  ████████████████   ", ("main", "logo_letter"))]),
	(0, [("   ████   ", ("main", "logo_bullet")), ("████   ◢███◤         ████         ", ("main", "logo_letter"))]),
	(0, [("          ████  ◢███◤          ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████ ◢███◤           ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████◢███◤            ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████◥███◣            ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████ ◥███◣           ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████  ◥███◣          ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████   ◥███◣         ████         ", ("main", "logo_letter"))]),
	(0, [("   ████   ████    ◥███◣        ████         ", ("main", "logo_letter"))]),
	(0, [("", ("main", "about_text"))]),
	(0, [(f" {about.program_suite_full_name} ", ("main", "about_text_highlight")), ("v", ("main", "about_text")), (f"{about.program_suite_version}", ("main", "about_version"))]),
	(0, [(f" {about.ui_program_name} ", ("main", "about_text_highlight")), ("v", ("main", "about_text")), (f"{about.ui_program_version}", ("main", "about_version"))]),
	(0, [("", ("main", "about_text"))]),
	(0, [(" Copyright © 2019-2022 Intel Corporation", ("main", "about_text_highlight"))]),
	(0, [("", ("main", "about_text"))]),
	(0, [(" Author(s):", ("main", "about_text_highlight"))]),
	(0, [(" David Weinehall", ("main", "about_text"))]),
	(0, [("", ("main", "about_text"))]),
	(0, [(" Testing:", ("main", "about_text_highlight"))]),
	(0, [(" Valtteri Rantala", ("main", "about_text"))]),
	(0, [(" Ukri Niemimuukko", ("main", "about_text"))]),
	(0, [(" Eero Tamminen", ("main", "about_text"))]),
	(0, [(" Alexey Fomenko", ("main", "about_text"))]),
	(0, [("", ("main", "about_text"))]),
]

toggleborders = [
	("[Shift] + B", "Toggle borders"),
]

listviewheader = [
	("[Ctrl] + X", "Exit program"),
	("[Shift] + M", "Toggle mouse on/off"),
	("[Shift] + W", "Toggle custom/normal/wide fields (when available)"),
] + toggleborders + [
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

infoviewheader = [
	("[ESC]", "Return to previous screen"),
	("[Ctrl] + X", "Exit program"),
	("[Shift] + M", "Toggle mouse on/off"),
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
	("[Shift] + R", "Toggle syntax highlighting"),
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

clusteroverview = [
	("[Ctrl] + X", "Exit program"),
	("[Shift] + M", "Toggle mouse on/off"),
] + toggleborders + spacer + [
	("[F1] / [Shift] + H", "Show this helptext"),
	("[F2]", "Switch main view"),
	("[F3]", "Switch main view (recheck available API resources)"),
	("[Shift] + N", "Open info page for Node [Node context only]"),
	("[Shift] + N", "Open info page for Namespace [Pod context only]"),
	("[Shift] + P", "Open info page for Pod [Pod context only]"),
	("[Shift] + V", "Show package versions"),
] + spacer + [
	("[Cursor keys]", "Move cursor up / down / left / right within resource map"),
	("[Shift] + [Left]", "Switch to previous resource map"),
	("[Shift] + [Right]", "Switch to next resource map"),
	("[Home]", "Jump to first column of resource map"),
	("[End]", "Jump to last column of resource map"),
	("[Tab]", "Jump to next elevated severity in resource map"),
	("[Shift] + [Tab]", "Jump to previous elevated severity in resource map"),
	("[Shift] + [Home]", "Jump to first row of resource map"),
	("[Shift] + [End]", "Jump to last row of resource map"),
]

configmapdata = infoviewheader + spacer + [
	("[Shift] + R", "Toggle syntax highlighting (default: On)"),
] + spacer + logmovement

inventorylist = listviewheader + [
	("[Enter]", "Open info page for selected host"),
	("[Shift] + S", "SSH to selected host"),
] + tagactions + [
	("[Shift] + A", "Set / unset Ansible groups for tagged items"),
] + spacer + listmovement

networkinfo = infoviewheader + [
	("", ""),
	("[Shift] + U", "Update CNI network (if a newer candidate is available)"),
]

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
	("[Shift] + R", "Toggle log parsing (default: On)"),
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
	("", "  The log format is decided by current mode; if you're viewing the raw"),
	("", "  log it will be exported as such; otherwise the parsed log will be exported."),
	("", ""),
	("[Tab]", "Jump to next elevated severity"),
	("[Shift] + [Tab]", "Jump to previous elevated severity"),
] + spacer + logmovement

usage  = [("[", "separator"), ("COMMAND", "command"), ("]", "separator"), (" [", "separator"), ("OPTION", "option"), ("]", "separator"), ("...", "option"), (" [", "separator"), ("ARGUMENT", "argument"), ("]", "separator"), ("...\n", "argument")]
usage += [("\n", "description")]
usage += [("UI for managing Kubernetes clusters\n", "description")]
usage += [("\n", "description")]
usage += [("VIEW", "command"),
          ("                     start in the ", "description"), ("VIEW", "command"), (" view\n", "description")]
usage += [("VIEW ", "command"), ("NAME ", "argument"), ("[", "separator"), ("NAMESPACE", "argument"), ("]", "separator"),
          ("    start in ", "description"), ("VIEW", "argument"), (" for the object matching ", "description"), ("NAME", "argument"), (" and, optionally, ", "description"), ("NAMESPACE\n", "argument")]
usage += [("VIEW ", "command"), ("NAMESPACE/NAME", "argument"),
          ("      same as above; alternate syntax\n", "description")]
usage += [("pod ", "command"), ("NAME NAMESPACE CONTAINER\n", "argument")]
usage += [("pod ", "command"), ("[", "separator"), ("NAMESPACE/", "argument"), ("]", "separator"), ("NAME:", "argument"), ("[", "separator"), ("CONTAINER", "argument"), ("]\n", "separator")]
usage += [("                         start in container info view matching ", "description"), ("NAME", "argument"), (", ", "description"), ("NAMESPACE", "argument"), (", ", "description"), ("CONTAINER", "argument"), (";\n", "description")]
usage += [("                         if ", "description"), ("NAME", "argument"), (" has exactly one container, then ", "description"), ("NAME:", "argument"), (" opens that container\n", "description")]
usage += [("configmap ", "command"), ("NAME NAMESPACE CONFIGMAP\n", "argument")]
usage += [("configmap ", "command"), ("[", "separator"), ("NAMESPACE/", "argument"), ("]", "separator"), ("NAME:", "argument"), ("[", "separator"), ("CONFIGMAP", "argument"), ("]\n", "separator")]
usage += [("                         start in the configmap info view matching ", "description"), ("NAME", "argument"), (", ", "description"),  (" NAMESPACE", "argument"), (", ", "description"),  (" CONFIGMAP", "argument"), (";\n", "description")]
usage += [("                         if ", "description"), ("NAME", "argument"), (" has exactly one configmap, then ", "description"), ("NAME:", "argument"), (" opens that configmap\n", "description")]
usage += [("\n", "description")]
usage += [("  --read-only ", "option"),
          ("  disable all commands that modify state", "description")]
usage += [("\n", "description")]
usage += [("  --namespace ", "option"), ("NAMESPACE", "argument"),
          ("  only show namespace ", "description"), ("NAMESPACE", "argument"), (" (valid for all namespaced views)\n", "description")]
usage += [("\n", "description")]
usage += [("list-views     ", "command"),
          ("          list view information and exit\n", "description")]
usage += [("list-namespaces", "command"),
          ("          list valid namespaces and exit\n", "description")]
usage += [("\n", "description")]
usage += [("help", "command"), ("|", "separator"), ("--help", "command"),
          ("              display this help and exit\n", "description")]
usage += [("version", "command"), ("|", "separator"), ("--version", "command"),
          ("        output version information and exit\n", "description")]
usage += [("\n", "description")]
