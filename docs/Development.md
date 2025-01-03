# Development

## Contributing

Contributions are warmly welcome!  All contributors MUST follow the guidelines in
[CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
All contributions must be made under license specified in [LICENSE.md](../LICENSE.md).

## Roadmap

If you want to contribute, but cannot quite decide what to prioritise it might
be good to consult the
[project roadmap](roadmap/Project_roadmap.md#project-roadmap).
It tries to provide a highlevel view of what is planned for the upcoming year or so.

## Testing

All contributions MUST be tested when applicable. Remember: tested contributions are good,
contributions that can be tested by others are better, but contributions that can be tested
automatically are the best.

### Unit-tests

When adding new method or functions, or modifying existing ones, you should add
or update the corresponding tests in the tests listed below.  All test-cases
are expected to pass; please do not submit commits that causes them to fail,
and definitely do not submit commits that modifies or disables tests just to
get a perfect score.

If the file you're modifying is not listed here you can either implement one on your own,
or ask for help.

| File:                  | Tests:                 | Notes:                                |
| :--------------------- | :--------------------- | :------------------------------------ |
| `ansithemeprint.py`    | `tests/atptests`       | Optional manual tests                 |
| `ansible_helper.py`    | `tests/ansibletests`   | Ansible setup required                |
| `checks.py`            | `tests/checkstests`    |                                       |
| `cmtio.py`             | `tests/iotests`        |                                       |
| `cmtio_yaml.py`        | `tests/iotests`        |                                       |
| `cmtlib.py`            | `tests/cmtlibtests`    | Ansible & cluster setup optional      |
| `cmtvalidators.py`     | `tests/validatortests` |                                       |
| `cmttypes.py`          | `tests/typetests`      |                                       |
| `cni_data.py`          | `tests/cnitests`       |                                       |
| `commandparser.py`     | `tests/clptests`       |                                       |
| `curses_helper.py`     | `tests/cursestests`    |                                       |
| `datagetters.py`       | `tests/dgtests`        |                                       |
| `fieldgetters.py`      | `tests/fgtests`        |                                       |
| `generators.py`        | `tests/gentests`       |                                       |
| `formatter.py`         | `tests/fmttests`       |                                       |
| `infogetters.py`       | `tests/infogtests`     |                                       |
| `itemgetters.py`       | `tests/itemgtests`     |                                       |
| `kubernetes_helper.py` | `tests/khtests`        | Cluster setup optional                |
| `listgetters.py`       | `tests/lgtests`        |                                       |
| `listgetters_async.py` | `tests/lgtests`        | Cluster setup required                |
| `logparser.py`         | `tests/logtests`       |                                       |
| `objgetters.py`        | `tests/ogtests`        |                                       |
| `networkio.py`         | `tests/iotests`        |                                       |
| `networkio.py`         | `tests/networkiotests` | Tests in iotests should be moved here |
| `reexecutor.py`        | `tests/async_fetch`    | Cluster setup required                |

_Note_:

* Optional manual tests mean that there are optional testcases that require manual input
* Ansible setup optional means that there are optional testcases that require cmt to
  be installed and configured with an inventory.
* Ansible setup required means that all or almost all testcases require cmt to
  be installed and configured with an inventory.
* Cluster setup optional means that there are optional testcases that require access
  to a cluster.
* Cluster setup required means that all or almost all testcases require access
  to a cluster; these tests may be hidden behind the `--include-cluster` flag.

At some point this might be revisited; ideally most most functions that only rely
indirectly on a working cluster or Ansible setup should be passed dummy data instead.
That would also allow us to test rare conditions that would not be observed
under normal conditions, such as errors, unresponsive nodes, etc.

### Manual tests

Some of the more complex functionality, especially in `cmu`,
may require a lot of state and many steps, making manual testing a good complement
to unit-tests.  For such tests a step-by-step description should be provided.

### Adding New Testcases

Please do! Unit-tests should be added in the tests-directory and should be written in Python.
They should return 0 on success, number of failed testcases on failure.
They may output useful information to the screen.
Unit-tests must not require user input by default, but may enable such tests
with a flag for the purpose of coverage testing.  The same goes for unit-tests
that would require a functional cluster.

`tests/logtests` can serve as a template.

### Testing Python

To verify that changes to the Python code do not introduce vulnerabilities,
the code MUST be checked code using:

```
make bandit (should not report any issues)
make regexploit (should not report any issues)
make semgrep (should not report any issues)
```

You SHOULD also run:

```
make tests
```

If you modify any of the files listed in the unit-test table, you _must_ run `make tests`.

You _should_ also check for code quality issues using:

```
make flake8 (should not report any issues)
make mypy (will report a lot of issues; but should not report more issues after your changes than before)
```

Note: some files will generate a __lot__ of errors from mypy, due to missing type-annotations.
You are not responsible for errors in other files, unless your changes introduce them,
but new or changed code should not introduce more errors.

### Testing _Parser-files_, _Themes_, _View-files_

If you add or modify _parser-files_, _themes_, or _view-files_ you need to use

```
make validate_yaml (should not report any issues)
```

### Testing Ansible Playbooks

If you add or modify Ansible playbooks you should use:

```
make validate_playbooks (should not report any issues)
```

### Testing Documentation

Make sure, within your own branch, to test all Markdown files you modify/add.
This has to be done manually. All new text should be in English. It is RECOMMENDED
that you check the spelling and grammar.

### Testing Other YAML-files

If you modify other YAML-files, you can use:

```
make yamllint (should not report any issues)
```

## New Functionality

Any new major functionality __must__ have unit-tests. Additionally it is recommended
that any complex features should  include steps for manual testing.

## New Dependencies

New dependencies MUST NOT be introduced without discussion. This applies to anything that would require
installing new distro-packages or adding something to [requirements.txt](../requirements.txt).

## Submitting Contributions

Contributions should be submitted as Pull Requests.  All contributions __MUST__ have a Signed-off-by line
at the end of the change description in every commit. If the submission fixes an issue in the Issue Tracker
you SHOULD add a comment to the issue tracker that references the Pull Request. You MUST NOT resolve the issue
as fixed until the Pull Request has been merged.  If possible mention the resolved issue in the commit message.

## Coding Standard

The coding style for __CMT__ is PEP8 with 100 character lines. `pylint --disable W0511` (do not warn
about FIXME/XXX/TODO) and and `flake8 --max-line-length 100 --ignore F841,W503` (line breaks should be before
binary operators, don't warn about unused variables since Flake8 doesn't understand the ignoring
results with `_ignore`).

### Type Annotations and Documentation

All new functions and methods MUST have type annotations and MUST be documented (general description,
parameters, returns). Code SHOULD be documented if it's not immediately obvious what it does.

### Python Version

__CMT__ uses Python 3.9 to allow for compatibility with some (not all) older enterprise distros.
This means that type annotations and the features used MUST NOT require newer versions of Python.
In some corner cases this means using Any for type hints, and being very generic about the definitions
for dicts.

## Documentation

Ensure that you keep documentation up to date. This also applies for screenshots.
If you add new documentation to the _docs_ directory, make sure to add links to all chapters
to the newly added documentation from [Table of Contents](Table_of_contents.md#table-of-contents).

## Commandline tool helptexts

If you add, remove, or change the behaviour of any of the commandline options for any of the executables,
you need to update docs/_COMMAND_\_helptext.md accordingly.  This can be done using:

```
make generate_helptexts
```
