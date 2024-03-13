#! /usr/bin/env python3
# vim: ts=4 filetype=python expandtab shiftwidth=4 softtabstop=4 syntax=python
#
# Show coverage statistics
# SPDX-License-Identifier: MIT

"""
Show coverage statistics
"""

import json

tmp = {}

with open("coverage.json", "r", encoding="utf-8") as f:
    data = f.read()
    tmp = json.loads(data)

print(f"  Totals: {tmp['totals']['num_statements']:>5}")
print(f" Covered: {tmp['totals']['covered_lines']:>5}")
print(f" Missing: {tmp['totals']['missing_lines']:>5}")
print(f"Excluded: {tmp['totals']['excluded_lines']:>5}")
print(f"Covered%: {tmp['totals']['percent_covered']:>5.1f}%")
print()

num_branches = tmp['totals']['num_branches']
covered_branches = tmp['totals']['covered_branches']
missing_branches = tmp['totals']['missing_branches']
percent_missing_branches = 100 * (covered_branches / num_branches)
print(f"Branches: {num_branches:>5}")
print(f" Covered: {covered_branches:>5}")
print(f" Missing: {missing_branches:>5}")
print(f" Partial: {tmp['totals']['num_partial_branches']:>5}")
print(f"Covered%: {percent_missing_branches:>5.1f}%")
