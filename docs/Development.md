# Development

## Contributing

Contributions are warmly welcome!  All contributors MUST follow the guidelines in
![CONTRIBUTING.md](../CONTRIBUTING.md) and ![CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
All contributions must be made under license specified in ![LICENSE.md](../LICENSE.md)

## Testing

All contributions MUST be tested when applicable.

### Python

To verify that changes to the Python code do not introduce vulnerabilities,
the code MUST be checked code using:

```
make bandit
make regexploit
```

You SHOULD also check for code quality issues using:

```
make flake8
make mypy
```

Note: some files will generate a __lot__ of errors from mypy, due to missing type-annotations.
You are not responsible for errors in other files, unless your changes introduce them,
but new or changed code should not introduce more errors.

### _parser-files_, _themes_, _view-files_

If you add or modify _parser-files_, _themes_, or _view-files_ you need to use

```
make validate_yaml
```

### Ansible Playbooks

If you add or modify Ansible playbooks you should use:

```
make validate_playbooks
```

### Documentation

Make sure, within your own branch, to test all Markdown files you modify/add.
This has to be done manually. All new text should be in English. It is RECOMMENDED
that you check the spelling and grammar.

### Other YAML-files

If you modify other YAML-files, you can use:

```
make yamllint
```

## New Dependencies

New dependencies MUST NOT be introduced without discussion. This applies to anything that would require
installing new distro-packages or adding something to ![requirements.txt](../requirements.txt).

## Submitting Contributions

Contributions should be submitted as Pull Requests.  All contributions __MUST__ have a Signed-off-by line
at the end of the change description in every commit. If the submission fixes an issue in the Issue Tracker
you SHOULD add a comment to the issue tracker that references the Pull Request. You MUST NOT resolve the issue
as fixed until the Pull Request has been merged.

## Coding Standard

Unlike many other Python project, __CMT__ uses tabs for indentation; space is only used to align indentation.
Other than that the coding standard is very similar to the upstream Python coding standard as dictated by Pylint,
Flake8, etc.

Note: __CMT__ prioritises legibility over line length, hence the use of tabs for indentation and the less
strict enforcement of line length.

### Type Annotations and Documentation

All new functions and methods MUST have type annotations and MUST be documented (general description,
parameters, returns). Code SHOULD be documented if it's not immediately obvious what it does.

### Python Version

__CMT__ uses Python 3.8 to allow for compatibility with some (not all) older enterprise distros.
This means that type annotations and the features used MUST NOT require newer versions of Python.

## Documentation

If you add new documentation to the _docs_ directory, make sure to add links to all chapters
to the newly added documentation from [Table of Contents](Table_of_contents.md#table-of-contents).
