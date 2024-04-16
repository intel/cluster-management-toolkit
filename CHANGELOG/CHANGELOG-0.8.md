* [v0.8.3](#v083)
    * [Downloads](#downloads-for-v083)
        * [Source Code](#source-code-for-v083)
        * [Distro Packages](#distro-packages-for-v083)
    * [General Release Notes](#general-release-notes-for-v083)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v083)
    * [Changes by Component](#changes-by-component-in-v083)
        * [Changes to _cmt_](#changes-to-cmt-in-v083)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v083)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v083)
        * [Changes to _cmu_](#changes-to-cmu-in-v083)
        * [Changes to other files](#changes-to-other-files-in-v083)
    * [Fixed Issues](#fixed-issues-in-v083)
    * [Known Regressions](#known-regressions-in-v083)
    * [Dependencies](#dependencies-for-v083)
    * [Test Results](#test-results-for-v083)
        * [Bandit](#bandit-results-for-v083)
        * [Coverage](#coverage-results-for-v083)
        * [Flake8](#flake8-results-for-v083)
        * [Pylint](#pylint-results-for-v083)
        * [Regexploit](#regexploit-results-for-v083)
        * [Ruff](#ruff-results-for-v083)
        * [Semgrep](#semgrep-results-for-v083)
        * [validate_playbooks](#validate_playbooks-results-for-v083)
        * [validate_yaml](#validate_yaml-results-for-v083)
        * [YAMLlint](#yamllint-results-for-v083)

# v0.8.3

## Downloads for v0.8.3

### Source Code for v0.8.3

CMT v0.8.3 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.3

CMT v0.8.3 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.3

This is a tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.3

This release fixes the check for new github-releases of Kubernetes and other components.

## Changes by Component in v0.8.3

### Changes to _cmt_ in v0.8.3

* The github-release check is now correct.

### Changes to _cmtadm_ in v0.8.3

* The github-release check is now correct.

### Changes to _cmtinv_ in v0.8.3

No changes.

### Changes to _cmu_ in v0.8.3

No changes.

### Changes to other files in v0.8.3

* `sources/helm.yaml` + `views/__VersionData.yaml`: show version information for Helm (if installed).

## Fixed Issues in v0.8.3

The check for new github-releases of Kubernetes and other components.

## Known Regressions in v0.8.3

Pylint fails to test the executables; this is an issue in Pylint though, not in CMT.

## Known Issues in v0.8.3

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data.
  The version data can be refreshed using `cmtadm cv`.
* Installing to the system path is currently not supported.

## Dependencies for v0.8.3

### Python

| PIP Name       | Minimum Version | Note                                    |
| -------------- | --------------- | --------------------------------------- |
| ansible-runner | 2.1.3           | openSUSE/SLES/RHEL, unsupported distros |
| cryptography   |                 | openSUSE, unsupported distros           |
| natsort        | 8.0.2           | openSUSE/SLES/RHEL, unsupported distros |
| paramiko       |                 | openSUSE/SLES/RHEL, unsupported distros |
| PyYAML         | 6.0             | Unsupported distros                     |
| ujson          | 5.4.0           | openSUSE/SLES/RHEL, unsupported distros |
| urllib3        | 1.26.18         | openSUSE/SLES, unsupported distros      |
| validators     | 0.22.0          | openSUSE/SLES/RHEL, unsupported distros |

### Distro Packages

| Package Name           | Distro             |
| ---------------------- | ------------------ |
| ansible                | Debian/Ubuntu/SUSE |
| python3-ansible-runner | Debian/Ubuntu      |
| python3-cryptographya  | Debian/RHEL/Ubuntu |
| python3-natsort        | Debian/Ubuntu      |
| python3-paramiko       | Debian/Ubuntu      |
| python3-pip            | Debian/Ubuntu      |
| python3-pyyaml         | RHEL               |
| python3-ujson          | Debian/Ubuntu      |
| python3-urllib3        | Debian/Ubuntu/RHEL |
| python3-validators     | Debian/Ubuntu      |
| python3-yaml           | Debian/Ubuntu      |
| sshpass                | All                |

### Manual Installation or Unknown Distro Packages

| Software | Distro              |
| -------- | ------------------- |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.3

Before release the code quality has been checked with _pylint_, _flake8_, _mypy_, and _ruff_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.3

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
        No issues identified.

Code scanned:
        Total lines of code: 71473
        Total lines skipped (#nosec): 15

Run metrics:
        Total issues (by severity):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
        Total issues (by confidence):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
Files skipped (0):
```

### Coverage Results for v0.8.3

Commandline: `python3-coverage run --branch --append <file> && python3-coverage report --sort cover --precision 1`.

Execute with:

```
make coverage
make coverage-ansible
make coverage-cluster
```

Output:

```
Name                         Stmts   Miss Branch BrPart  Cover
--------------------------------------------------------------
listgetters_async.py           119    100     58      0  10.7%
listgetters.py                1169    961    634     17  15.0%
curses_helper.py              2393   1832   1118     68  19.2%
checks.py                      609    457    226     28  19.6%
networkio.py                   288    218    149      6  21.1%
itemgetters.py                 443    323    254      0  23.8%
logparser.py                  1898   1282   1055     30  27.9%
generators.py                  740    494    390      5  30.2%
infogetters.py                 420    288    208      2  33.4%
kubernetes_helper.py          1433    852    748    103  33.7%
fieldgetters.py                 80     39     46     11  41.3%
datagetters.py                 274    148    142     11  42.5%
formatters.py                  767    324    408     29  54.6%
ansible_helper.py              796    199    488     27  73.8%
cmtlib.py                      604    106    346     28  80.2%
cmtio.py                       423     35    240     17  91.0%
reexecutor.py                   72      2     34      3  95.3%
ansithemeprint.py              211      1     80      3  98.6%
cmtvalidators.py               324      1    200      1  99.6%
commandparser.py               411      0    254      1  99.8%
about.py                        19      0      0      0 100.0%
cmtio_yaml.py                   34      0      6      0 100.0%
cmtpaths.py                     80      0      0      0 100.0%
cmttypes.py                    468      0    178      0 100.0%
cni_data.py                     38      0      8      0 100.0%
helptexts.py                    23      0      0      0 100.0%
kubernetes_resources.py          4      0      0      0 100.0%
objgetters.py                   55      0     12      0 100.0%
pvtypes.py                       2      0      0      0 100.0%
recommended_permissions.py      11      0      0      0 100.0%
--------------------------------------------------------------
TOTAL                        14208   7662   7282    390  42.8%
```


### Flake8 Results for v0.8.3

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.3

Commandline: `mypy --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators`.
Execute with `make mypy-markdown`.

| Source file             | Score                                                   |
| ----------------------- | ------------------------------------------------------- |
| cmt                     | Success: no issues found in 1 source file               |
| cmtadm                  | Success: no issues found in 1 source file               |
| cmt-install             | Success: no issues found in 1 source file               |
| cmtinv                  | Success: no issues found in 1 source file               |
| cmu                     | __Found 545 errors in 2 files (checked 1 source file)__ |
| about.py                | Success: no issues found in 1 source file               |
| ansible_helper.py       | Success: no issues found in 1 source file               |
| ansithemeprint.py       | Success: no issues found in 1 source file               |
| checks.py               | Success: no issues found in 1 source file               |
| cmtio.py                | Success: no issues found in 1 source file               |
| cmtio_yaml.py           | Success: no issues found in 1 source file               |
| cmtlib.py               | Success: no issues found in 1 source file               |
| cmtpaths.py             | Success: no issues found in 1 source file               |
| cmttypes.py             | Success: no issues found in 1 source file               |
| cmtvalidators.py        | Success: no issues found in 1 source file               |
| cni_data.py             | Success: no issues found in 1 source file               |
| commandparser.py        | Success: no issues found in 1 source file               |
| curses_helper.py        | Success: no issues found in 1 source file               |
| datagetters.py          | Success: no issues found in 1 source file               |
| fieldgetters.py         | Success: no issues found in 1 source file               |
| formatters.py           | Success: no issues found in 1 source file               |
| generators.py           | Success: no issues found in 1 source file               |
| helptexts.py            | Success: no issues found in 1 source file               |
| infogetters.py          | Success: no issues found in 1 source file               |
| itemgetters.py          | Success: no issues found in 1 source file               |
| kubernetes_helper.py    | Success: no issues found in 1 source file               |
| kubernetes_resources.py | Success: no issues found in 1 source file               |
| listgetters.py          | Success: no issues found in 1 source file               |
| listgetters_async.py    | Success: no issues found in 1 source file               |
| logparser.py            | __Found 103 errors in 1 file (checked 1 source file)__  |
| networkio.py            | Success: no issues found in 1 source file               |
| objgetters.py           | Success: no issues found in 1 source file               |
| pvtypes.py              | Success: no issues found in 1 source file               |
| reexecutor.py           | Success: no issues found in 1 source file               |

### Pylint Results for v0.8.3

**N/A**. Pylint seems to be broken in Debian at the moment and crashes during testing.

### Regexploit Results for v0.8.3

Commandline: `regexploit`.
Execute with `make regexploit`.

Output:

```
Running regexploit to check for ReDoS attacks

Checking executables
Processed 44 regexes

Checking libraries
Processed 117 regexes
```

### Ruff Results for v0.8.3

Commandline: `ruff`.
Execute with `make ruff`.

Output:

No output.

### Semgrep Results for v0.8.3

Commandline: `semgrep scan --exclude-rule "generic.secrets.security.detected-generic-secret.detected-generic-secret.semgrep-legacy.30980" --timeout=0 --no-git-ignore`.
Execute with `make semgrep`.

Output:

```
┌──── ○○○ ────┐
│ Semgrep CLI │
└─────────────┘

Scanning 911 files with:

✔ Semgrep OSS
  ✔ Basic security coverage for first-party code vulnerabilities.

✔ Semgrep Code (SAST)
  ✔ Find and fix vulnerabilities in the code you write with advanced scanning and expert security rules.

✘ Semgrep Supply Chain (SCA)
  ✘ Find and fix the reachable vulnerabilities in your OSS dependencies.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╸ 100% 0:00:37


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 2 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 73 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 483 rules on 838 files: 0 findings.

⏫  A new version of Semgrep is available. See https://semgrep.dev/docs/upgrading

✨ If Semgrep missed a finding, please send us feedback to let us know!
    See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.3

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

`Passed: 0 failure(s), 0 warning(s) on 55 files. Last profile that met the validation criteria was 'production'.`

### validate_yaml Results for v0.8.3

Commandline: `tests/validate_yaml`.
Execute with: `make validate_yaml`.

Output:

```
Summary:
     fail: 0
     skip: 1
  success: 641
    total: 642
```

### YAMLlint Results for v0.8.3

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.

---

* [v0.8.2](#v082)
    * [Downloads](#downloads-for-v082)
        * [Source Code](#source-code-for-v082)
        * [Distro Packages](#distro-packages-for-v082)
    * [General Release Notes](#general-release-notes-for-v082)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v082)
    * [Changes by Component](#changes-by-component-in-v082)
        * [Changes to _cmt_](#changes-to-cmt-in-v082)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v082)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v082)
        * [Changes to _cmu_](#changes-to-cmu-in-v082)
        * [Changes to other files](#changes-to-other-files-in-v082)
    * [Fixed Issues](#fixed-issues-in-v082)
    * [Known Regressions](#known-regressions-in-v082)
    * [Dependencies](#dependencies-for-v082)
    * [Test Results](#test-results-for-v082)
        * [Bandit](#bandit-results-for-v082)
        * [Coverage](#coverage-results-for-v082)
        * [Flake8](#flake8-results-for-v082)
        * [Pylint](#pylint-results-for-v082)
        * [Regexploit](#regexploit-results-for-v082)
        * [Ruff](#ruff-results-for-v082)
        * [Semgrep](#semgrep-results-for-v082)
        * [validate_playbooks](#validate_playbooks-results-for-v082)
        * [validate_yaml](#validate_yaml-results-for-v082)
        * [YAMLlint](#yamllint-results-for-v082)

# v0.8.2

## Downloads for v0.8.2

### Source Code for v0.8.2

CMT v0.8.2 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.2

CMT v0.8.2 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.2

This is a tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.2

This release fixes crashes in _cmu_ and _cmtadm_.

## Changes by Component in v0.8.2

### Changes to _cmt_ in v0.8.2

Only cosmetic fixes.

### Changes to _cmtadm_ in v0.8.2

* `cmtadm create-cluster` can now create VM nodes.
* A bug in `cmtadm setup-control-plane` that could crash the program has been fixed.

### Changes to _cmtinv_ in v0.8.2

No changes.

### Changes to _cmu_ in v0.8.2

* Fix a crash when switching between different sets of fields
  where the Wide view isn't a strict superset of the Normal view.
* Fix a crash in the Containers view.
* Changing context now shows the update immediately.
* Pressing `J` will now show the object as JSON, just like `Y` shows the object as YAML.

### Changes to other files in v0.8.2

* _ruff_ has been added as a code linter.
* The Version View now lists Kubernetes, CMT, and (if installed) CRC.
* There's now a Node Resources view that lists all known resources that the nodes provide,
  as well as how much of them are allocatable. Currently Node Resources only has a list view.
* Several OpenShift-related views were improved.
* A lot of new unit-tests were added.
* More code refactoring.

## Fixed Issues in v0.8.2

Two crashes in _cmu_ and one crash in _cmtadm_; the the Changes sections for those components.

## Known Regressions in v0.8.2

Pylint fails to test the executables; this is an issue in Pylint though, not in CMT.

## Known Issues in v0.8.2

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data.
  The version data can be refreshed using `cmtadm cv`.
* Installing to the system path is currently not supported.

## Dependencies for v0.8.2

### Python

| PIP Name       | Minimum Version | Note                                    |
| -------------- | --------------- | --------------------------------------- |
| ansible-runner | 2.1.3           | openSUSE/SLES/RHEL, unsupported distros |
| cryptography   |                 | openSUSE, unsupported distros           |
| natsort        | 8.0.2           | openSUSE/SLES/RHEL, unsupported distros |
| paramiko       |                 | openSUSE/SLES/RHEL, unsupported distros |
| PyYAML         | 6.0             | Unsupported distros                     |
| ujson          | 5.4.0           | openSUSE/SLES/RHEL, unsupported distros |
| urllib3        | 1.26.18         | openSUSE/SLES, unsupported distros      |
| validators     | 0.22.0          | openSUSE/SLES/RHEL, unsupported distros |

### Distro Packages

| Package Name           | Distro             |
| ---------------------- | ------------------ |
| ansible                | Debian/Ubuntu/SUSE |
| python3-ansible-runner | Debian/Ubuntu      |
| python3-cryptographya  | Debian/RHEL/Ubuntu |
| python3-natsort        | Debian/Ubuntu      |
| python3-paramiko       | Debian/Ubuntu      |
| python3-pip            | Debian/Ubuntu      |
| python3-pyyaml         | RHEL               |
| python3-ujson          | Debian/Ubuntu      |
| python3-urllib3        | Debian/Ubuntu/RHEL |
| python3-validators     | Debian/Ubuntu      |
| python3-yaml           | Debian/Ubuntu      |
| sshpass                | All                |

### Manual Installation or Unknown Distro Packages

| Software | Distro              |
| -------- | ------------------- |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.2

Before release the code quality has been checked with _pylint_, _flake8_, _mypy_, and _ruff_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.2

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
        No issues identified.

Code scanned:
        Total lines of code: 71169
        Total lines skipped (#nosec): 15

Run metrics:
        Total issues (by severity):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
        Total issues (by confidence):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
Files skipped (0):
```

### Coverage Results for v0.8.2

Commandline: `python3-coverage run --branch --append <file> && python3-coverage report --sort cover --precision 1`.

Execute with:

```
make coverage
make coverage-ansible
make coverage-cluster
```

Output:

```
Name                         Stmts   Miss Branch BrPart  Cover
--------------------------------------------------------------
listgetters_async.py           119    100     58      0  10.7%
curses_helper.py              2390   2006   1116      4  13.6%
listgetters.py                1161    972    628     18  13.9%
checks.py                      609    457    226     28  19.6%
networkio.py                   283    214    145      6  21.3%
itemgetters.py                 443    323    254      0  23.8%
logparser.py                  1898   1282   1055     30  27.9%
generators.py                  740    494    390      5  30.2%
infogetters.py                 420    288    208      2  33.4%
kubernetes_helper.py          1433    852    748    103  33.7%
fieldgetters.py                 60     29     36      2  40.6%
datagetters.py                 274    148    142     11  42.5%
formatters.py                  767    324    408     29  54.6%
ansible_helper.py              796    199    488     27  73.8%
cmtlib.py                      604    106    346     28  80.2%
cmtio.py                       423     35    240     17  91.0%
reexecutor.py                   72      2     34      3  95.3%
ansithemeprint.py              211      1     80      3  98.6%
cmtvalidators.py               324      1    200      1  99.6%
commandparser.py               411      0    254      1  99.8%
about.py                        19      0      0      0 100.0%
cmtio_yaml.py                   34      0      6      0 100.0%
cmtpaths.py                     80      0      0      0 100.0%
cmttypes.py                    468      0    178      0 100.0%
cni_data.py                     38      0      8      0 100.0%
helptexts.py                    23      0      0      0 100.0%
kubernetes_resources.py          4      0      0      0 100.0%
objgetters.py                   55      0     12      0 100.0%
pvtypes.py                       2      0      0      0 100.0%
recommended_permissions.py      11      0      0      0 100.0%
--------------------------------------------------------------
TOTAL                        14172   7833   7260    318  41.8%
```


### Flake8 Results for v0.8.2

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.2

Commandline: `mypy --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators`.
Execute with `make mypy-markdown`.

| Source file             | Score                                                   |
| ----------------------- | ------------------------------------------------------- |
| cmt                     | Success: no issues found in 1 source file               |
| cmtadm                  | Success: no issues found in 1 source file               |
| cmt-install             | Success: no issues found in 1 source file               |
| cmtinv                  | Success: no issues found in 1 source file               |
| cmu                     | __Found 545 errors in 2 files (checked 1 source file)__ |
| about.py                | Success: no issues found in 1 source file               |
| ansible_helper.py       | Success: no issues found in 1 source file               |
| ansithemeprint.py       | Success: no issues found in 1 source file               |
| checks.py               | Success: no issues found in 1 source file               |
| cmtio.py                | Success: no issues found in 1 source file               |
| cmtio_yaml.py           | Success: no issues found in 1 source file               |
| cmtlib.py               | Success: no issues found in 1 source file               |
| cmtpaths.py             | Success: no issues found in 1 source file               |
| cmttypes.py             | Success: no issues found in 1 source file               |
| cmtvalidators.py        | Success: no issues found in 1 source file               |
| cni_data.py             | Success: no issues found in 1 source file               |
| commandparser.py        | Success: no issues found in 1 source file               |
| curses_helper.py        | Success: no issues found in 1 source file               |
| datagetters.py          | Success: no issues found in 1 source file               |
| fieldgetters.py         | Success: no issues found in 1 source file               |
| formatters.py           | Success: no issues found in 1 source file               |
| generators.py           | Success: no issues found in 1 source file               |
| helptexts.py            | Success: no issues found in 1 source file               |
| infogetters.py          | Success: no issues found in 1 source file               |
| itemgetters.py          | Success: no issues found in 1 source file               |
| kubernetes_helper.py    | Success: no issues found in 1 source file               |
| kubernetes_resources.py | Success: no issues found in 1 source file               |
| listgetters.py          | Success: no issues found in 1 source file               |
| listgetters_async.py    | Success: no issues found in 1 source file               |
| logparser.py            | __Found 103 errors in 1 file (checked 1 source file)__  |
| networkio.py            | Success: no issues found in 1 source file               |
| objgetters.py           | Success: no issues found in 1 source file               |
| pvtypes.py              | Success: no issues found in 1 source file               |
| reexecutor.py           | Success: no issues found in 1 source file               |

### Pylint Results for v0.8.2

**N/A**. Pylint seems to be broken in Debian at the moment and crashes during testing.

### Regexploit Results for v0.8.2

Commandline: `regexploit`.
Execute with `make regexploit`.

Output:

```
Running regexploit to check for ReDoS attacks

Checking executables
Processed 44 regexes

Checking libraries
Processed 117 regexes
```

### Ruff Results for v0.8.2

Commandline: `ruff`.
Execute with `make ruff`.

Output:

No output.

### Semgrep Results for v0.8.2

Commandline: `semgrep scan --exclude-rule "generic.secrets.security.detected-generic-secret.detected-generic-secret.semgrep-legacy.30980" --timeout=0 --no-git-ignore`.
Execute with `make semgrep`.

Output:

```
┌──── ○○○ ────┐
│ Semgrep CLI │
└─────────────┘

Scanning 910 files with:

✔ Semgrep OSS
  ✔ Basic security coverage for first-party code vulnerabilities.

✔ Semgrep Code (SAST)
  ✔ Find and fix vulnerabilities in the code you write with advanced scanning and expert security rules.

✘ Semgrep Supply Chain (SCA)
  ✘ Find and fix the reachable vulnerabilities in your OSS dependencies.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╸ 100% 0:00:38


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 2 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 73 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 483 rules on 837 files: 0 findings.

✨ If Semgrep missed a finding, please send us feedback to let us know!
    See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.2

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

`Passed: 0 failure(s), 0 warning(s) on 55 files. Last profile that met the validation criteria was 'production'.`

### validate_yaml Results for v0.8.2

Commandline: `tests/validate_yaml`.
Execute with: `make validate_yaml`.

Output:

```
Summary:
     fail: 0
     skip: 1
  success: 641
    total: 642
```

### YAMLlint Results for v0.8.2

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.

---

* [v0.8.1](#v081)
    * [Downloads](#downloads-for-v081)
        * [Source Code](#source-code-for-v081)
        * [Distro Packages](#distro-packages-for-v081)
    * [General Release Notes](#general-release-notes-for-v081)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v081)
    * [Changes by Component](#changes-by-component-in-v081)
        * [Changes to _cmt_](#changes-to-cmt-in-v081)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v081)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v081)
        * [Changes to _cmu_](#changes-to-cmu-in-v081)
        * [Changes to other files](#changes-to-other-files-in-v081)
    * [Fixed Issues](#fixed-issues-in-v081)
    * [Known Regressions](#known-regressions-in-v081)
    * [Dependencies](#dependencies-for-v081)
    * [Test Results](#test-results-for-v081)
        * [Bandit](#bandit-results-for-v081)
        * [Flake8](#flake8-results-for-v081)
        * [Pylint](#pylint-results-for-v081)
        * [Regexploit](#regexploit-results-for-v081)
        * [Semgrep](#semgrep-results-for-v081)
        * [validate_playbooks](#validate_playbooks-results-for-v081)
        * [validate_yaml](#validate_yaml-results-for-v081)
        * [YAMLlint](#yamllint-results-for-v081)

# v0.8.1

## Downloads for v0.8.1

### Source Code for v0.8.1

CMT v0.8.1 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.1

CMT v0.8.1 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.1

This is a tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.1

Unknown APIs causes the Custom Resource Definition view to crash.

## Changes by Component in v0.8.1

### Changes to _cmt_ in v0.8.1

N/A; this is the first release.

### Changes to _cmtadm_ in v0.8.1

N/A; this is the first release.

### Changes to _cmtinv_ in v0.8.1

N/A; this is the first release.

### Changes to _cmu_ in v0.8.1

N/A; this is the first release.

### Changes to other files in v0.8.1

`generators.py`: Fixed an exception that triggered by the Custom Resource Definition view when encountering an unknown API.
`kubernetes_resources.py`: Added API-signature for `ImageCache.kubefledged.io`.
`docs/Development.md`: Updated the section about the Coding Standard. Added `tests/gentests` to the list of unit-tests.
`parsers/kube-fledged.yaml`: Parser-file for `kube-fledge`.
`tests/gentests`: New file. Unit-tests for generators.py.

## Fixed Issues in v0.8.1

N/A; this is the first release.

## Known Regressions in v0.8.1

N/A; this is the first release.

## Known Issues in v0.8.1

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data, and is currently limited to upstream Kubernetes.
  The version data can be refreshed using `cmtadm cv`.
* Installing to the system path is currently not supported.
* The context view doesn't update when selecting a new context (the context still changes; this is purely a cosmetic issue).

## Dependencies for v0.8.1

### Python

| PIP Name       | Minimum Version | Note                                    |
| -------------- | --------------- | --------------------------------------- |
| ansible-runner | 2.1.3           | openSUSE/SLES/RHEL, unsupported distros |
| cryptography   |                 | openSUSE, unsupported distros           |
| natsort        | 8.0.2           | openSUSE/SLES/RHEL, unsupported distros |
| paramiko       |                 | openSUSE/SLES/RHEL, unsupported distros |
| PyYAML         | 6.0             | Unsupported distros                     |
| ujson          | 5.4.0           | openSUSE/SLES/RHEL, unsupported distros |
| urllib3        | 1.26.18         | openSUSE/SLES, unsupported distros      |
| validators     | 0.22.0          | openSUSE/SLES/RHEL, unsupported distros |

### Distro Packages

| Package Name           | Distro             |
| ---------------------- | ------------------ |
| ansible                | Debian/Ubuntu/SUSE |
| python3-ansible-runner | Debian/Ubuntu      |
| python3-cryptographya  | Debian/RHEL/Ubuntu |
| python3-natsort        | Debian/Ubuntu      |
| python3-paramiko       | Debian/Ubuntu      |
| python3-pip            | Debian/Ubuntu      |
| python3-pyyaml         | RHEL               |
| python3-ujson          | Debian/Ubuntu      |
| python3-urllib3        | Debian/Ubuntu/RHEL |
| python3-validators     | Debian/Ubuntu      |
| python3-yaml           | Debian/Ubuntu      |
| sshpass                | All                |

### Manual Installation or Unknown Distro Packages

| Software | Distro              |
| -------- | ------------------- |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.1

Before release the code quality has been checked with _pylint_, _flake8_, and _mypy_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.1

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
        No issues identified.

Code scanned:
        Total lines of code: 67195
        Total lines skipped (#nosec): 15

Run metrics:
        Total issues (by severity):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
        Total issues (by confidence):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
```

### Flake8 Results for v0.8.1

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.1

Commandline: `mypy --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators`.
Execute with `make mypy-markdown`.

| Source file             | Score                                                   |
| ----------------------- | ------------------------------------------------------- |
| cmt                     | Success: no issues found in 1 source file               |
| cmtadm                  | Success: no issues found in 1 source file               |
| cmt-install             | Success: no issues found in 1 source file               |
| cmtinv                  | Success: no issues found in 1 source file               |
| cmu                     | __Found 611 errors in 2 files (checked 1 source file)__ |
| about.py                | Success: no issues found in 1 source file               |
| ansible_helper.py       | Success: no issues found in 1 source file               |
| ansithemeprint.py       | Success: no issues found in 1 source file               |
| checks.py               | Success: no issues found in 1 source file               |
| cmtio.py                | Success: no issues found in 1 source file               |
| cmtio_yaml.py           | Success: no issues found in 1 source file               |
| cmtlib.py               | Success: no issues found in 1 source file               |
| cmtpaths.py             | Success: no issues found in 1 source file               |
| cmttypes.py             | Success: no issues found in 1 source file               |
| cmtvalidators.py        | Success: no issues found in 1 source file               |
| cni_data.py             | Success: no issues found in 1 source file               |
| commandparser.py        | Success: no issues found in 1 source file               |
| curses_helper.py        | Success: no issues found in 1 source file               |
| datagetters.py          | Success: no issues found in 1 source file               |
| fieldgetters.py         | Success: no issues found in 1 source file               |
| formatters.py           | Success: no issues found in 1 source file               |
| generators.py           | Success: no issues found in 1 source file               |
| helptexts.py            | Success: no issues found in 1 source file               |
| infogetters.py          | Success: no issues found in 1 source file               |
| itemgetters.py          | Success: no issues found in 1 source file               |
| kubernetes_helper.py    | Success: no issues found in 1 source file               |
| kubernetes_resources.py | Success: no issues found in 1 source file               |
| listgetters.py          | Success: no issues found in 1 source file               |
| listgetters_async.py    | Success: no issues found in 1 source file               |
| logparser.py            | __Found 103 errors in 1 file (checked 1 source file)__  |
| networkio.py            | Success: no issues found in 1 source file               |
| objgetters.py           | Success: no issues found in 1 source file               |
| pvtypes.py              | Success: no issues found in 1 source file               |
| reexecutor.py           | Success: no issues found in 1 source file               |

### Pylint Results for v0.8.1

Commandline: `pylint --disable W0511`.
Table generated with `make pylint-strict-markdown`.
Currently all complaints are due to missing function, method, or class docstrings.

Output:

| Source file                  | Score       |
| ---------------------------- | -----       |
| cmt                          | 10.00/10    |
| cmtadm                       | 10.00/10    |
| cmt-install                  | 10.00/10    |
| cmtinv                       | 10.00/10    |
| cmu                          | __9.88/10__ |
| about.py                     | 10.00/10    |
| ansible_helper.py            | 10.00/10    |
| ansithemeprint.py            | 10.00/10    |
| checks.py                    | 10.00/10    |
| cmtio.py                     | 10.00/10    |
| cmtio_yaml.py                | 10.00/10    |
| cmtlib.py                    | 10.00/10    |
| cmtpaths.py                  | 10.00/10    |
| cmttypes.py                  | 10.00/10    |
| cmtvalidators.py             | 10.00/10    |
| cni_data.py                  | 10.00/10    |
| commandparser.py             | 10.00/10    |
| curses_helper.py             | __9.77/10__ |
| datagetters.py               | 10.00/10    |
| fieldgetters.py              | 10.00/10    |
| formatters.py                | 10.00/10    |
| generators.py                | __9.70/10__ |
| helptexts.py                 | 10.00/10    |
| infogetters.py               | 10.00/10    |
| itemgetters.py               | 10.00/10    |
| kubernetes_helper.py         | 10.00/10    |
| kubernetes_resources.py      | 10.00/10    |
| listgetters.py               | __9.78/10__ |
| listgetters_async.py         | 10.00/10    |
| logparser.py                 | __9.92/10__ |
| networkio.py                 | 10.00/10    |
| objgetters.py                | 10.00/10    |
| pvtypes.py                   | 10.00/10    |
| reexecutor.py                | 10.00/10    |

### Regexploit Results for v0.8.1

Commandline: `regexploit`.
Execute with `make regexploit`.

Output:

```
Running regexploit to check for ReDoS attacks

Checking executables
Processed 44 regexes

Checking libraries
Processed 115 regexes
```

### Semgrep Results for v0.8.1

Commandline: `semgrep scan --exclude-rule "generic.secrets.security.detected-generic-secret.detected-generic-secret.semgrep-legacy.30980" --timeout=0 --no-git-ignore`.
Execute with `make semgrep`.

Output:

```
┌──── ○○○ ────┐
│ Semgrep CLI │
└─────────────┘

Scanning 888 files with:

✔ Semgrep OSS
  ✔ Basic security coverage for first-party code vulnerabilities.

✔ Semgrep Code (SAST)
  ✔ Find and fix vulnerabilities in the code you write with advanced scanning and expert security rules.

✘ Semgrep Supply Chain (SCA)
  ✘ Find and fix the reachable vulnerabilities in your OSS dependencies.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:47


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 5 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 70 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 483 rules on 818 files: 0 findings.

✨ If Semgrep missed a finding, please send us feedback to let us know!
    See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.1

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

`Passed: 0 failure(s), 0 warning(s) on 46 files. Last profile that met the validation criteria was 'production'.`

### validate_yaml Results for v0.8.1

Commandline: `tests/validate_yaml`.
Execute with: `make validate_yaml`.

Output:

```
Summary:
     fail: 0
     skip: 1
  success: 640
    total: 641
```

### YAMLlint Results for v0.8.1

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.

---

* [v0.8.0](#v080)
    * [Downloads](#downloads-for-v080)
        * [Source Code](#source-code-for-v080)
        * [Distro Packages](#distro-packages-for-v080)
    * [General Release Notes](#general-release-notes-for-v080)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v080)
    * [Changes by Component](#changes-by-component-in-v080)
        * [Changes to _cmt_](#changes-to-cmt-in-v080)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v080)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v080)
        * [Changes to _cmu_](#changes-to-cmu-in-v080)
    * [Fixed Issues](#fixed-issues-in-v080)
    * [Known Regressions](#known-regressions-in-v080)
    * [Dependencies](#dependencies-for-v080)
    * [Test Results](#test-results-for-v080)
        * [Bandit](#bandit-results-for-v080)
        * [Flake8](#flake8-results-for-v080)
        * [Pylint](#pylint-results-for-v080)
        * [Regexploit](#regexploit-results-for-v080)
        * [Semgrep](#semgrep-results-for-v080)
        * [validate_playbooks](#validate_playbooks-results-for-v080)
        * [validate_yaml](#validate_yaml-results-for-v080)
        * [YAMLlint](#yamllint-results-for-v080)

# v0.8.0

## Downloads for v0.8.0

### Source Code for v0.8.0

CMT v0.8.0 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.0

CMT v0.8.0 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| -------- | ----------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.0

This is the first tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.0

N/A; this is the first release.

## Changes by Component in v0.8.0

### Changes to _cmt_ in v0.8.0

N/A; this is the first release.

### Changes to _cmtadm_ in v0.8.0

N/A; this is the first release.

### Changes to _cmtinv_ in v0.8.0

N/A; this is the first release.

### Changes to _cmu_ in v0.8.0

N/A; this is the first release.

## Fixed Issues in v0.8.0

N/A; this is the first release.

## Known Regressions in v0.8.0

N/A; this is the first release.

## Known Issues in v0.8.0

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data, and is currently limited to upstream Kubernetes.
  The version data can be refreshed using `cmtadm cv`.
* Installing to the system path is currently not supported.

## Dependencies for v0.8.0

### Python

| PIP Name       | Minimum Version | Note                                    |
| -------------- | --------------- | --------------------------------------- |
| ansible-runner | 2.1.3           | openSUSE/SLES/RHEL, unsupported distros |
| cryptography   |                 | openSUSE, unsupported distros           |
| natsort        | 8.0.2           | openSUSE/SLES/RHEL, unsupported distros |
| paramiko       |                 | openSUSE/SLES/RHEL, unsupported distros |
| PyYAML         | 6.0             | Unsupported distros                     |
| ujson          | 5.4.0           | openSUSE/SLES/RHEL, unsupported distros |
| urllib3        | 1.26.18         | openSUSE/SLES, unsupported distros      |
| validators     | 0.22.0          | openSUSE/SLES/RHEL, unsupported distros |

### Distro Packages

| Package Name           | Distro             |
| ---------------------- | ------------------ |
| ansible                | Debian/Ubuntu/SUSE |
| python3-ansible-runner | Debian/Ubuntu      |
| python3-cryptographya  | Debian/RHEL/Ubuntu |
| python3-natsort        | Debian/Ubuntu      |
| python3-paramiko       | Debian/Ubuntu      |
| python3-pip            | Debian/Ubuntu      |
| python3-pyyaml         | RHEL               |
| python3-ujson          | Debian/Ubuntu      |
| python3-urllib3        | Debian/Ubuntu/RHEL |
| python3-validators     | Debian/Ubuntu      |
| python3-yaml           | Debian/Ubuntu      |
| sshpass                | All                |

### Manual Installation or Unknown Distro Packages

| Software | Distro              |
| -------- | ------------------- |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.0

Before release the code quality has been checked with _pylint_, _flake8_, and _mypy_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.0

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
        No issues identified.

Code scanned:
        Total lines of code: 66629
        Total lines skipped (#nosec): 15

Run metrics:
        Total issues (by severity):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
        Total issues (by confidence):
                Undefined: 0.0
                Low: 0.0
                Medium: 0.0
                High: 0.0
```

### Flake8 Results for v0.8.0

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.0

Commandline: `mypy --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators`.
Execute with `make mypy-markdown`.

| Source file             | Score                                                   |
| ----------------------- | ------------------------------------------------------- |
| cmt                     | Success: no issues found in 1 source file               |
| cmtadm                  | Success: no issues found in 1 source file               |
| cmt-install             | Success: no issues found in 1 source file               |
| cmtinv                  | Success: no issues found in 1 source file               |
| cmu                     | __Found 611 errors in 2 files (checked 1 source file)__ |
| about.py                | Success: no issues found in 1 source file               |
| ansible_helper.py       | Success: no issues found in 1 source file               |
| ansithemeprint.py       | Success: no issues found in 1 source file               |
| checks.py               | Success: no issues found in 1 source file               |
| cmtio.py                | Success: no issues found in 1 source file               |
| cmtio_yaml.py           | Success: no issues found in 1 source file               |
| cmtlib.py               | Success: no issues found in 1 source file               |
| cmtlog.py               | __Found 18 errors in 1 file (checked 1 source file)__   |
| cmtpaths.py             | Success: no issues found in 1 source file               |
| cmttypes.py             | Success: no issues found in 1 source file               |
| cmtvalidators.py        | Success: no issues found in 1 source file               |
| cni_data.py             | Success: no issues found in 1 source file               |
| commandparser.py        | Success: no issues found in 1 source file               |
| curses_helper.py        | Success: no issues found in 1 source file               |
| datagetters.py          | Success: no issues found in 1 source file               |
| fieldgetters.py         | Success: no issues found in 1 source file               |
| formatters.py           | Success: no issues found in 1 source file               |
| generators.py           | Success: no issues found in 1 source file               |
| helptexts.py            | Success: no issues found in 1 source file               |
| infogetters.py          | Success: no issues found in 1 source file               |
| itemgetters.py          | Success: no issues found in 1 source file               |
| kubernetes_helper.py    | Success: no issues found in 1 source file               |
| kubernetes_resources.py | Success: no issues found in 1 source file               |
| listgetters.py          | Success: no issues found in 1 source file               |
| listgetters_async.py    | Success: no issues found in 1 source file               |
| logparser.py            | __Found 103 errors in 1 file (checked 1 source file)__  |
| networkio.py            | Success: no issues found in 1 source file               |
| objgetters.py           | Success: no issues found in 1 source file               |
| pvtypes.py              | Success: no issues found in 1 source file               |
| reexecutor.py           | Success: no issues found in 1 source file               |

### Pylint Results for v0.8.0

Commandline: `pylint --disable W0511`.
Table generated with `make pylint-strict-markdown`.
Currently all complaints are due to missing function, method, or class docstrings.

Output:

| Source file                  | Score       |
| ---------------------------- | -----       |
| cmt                          | 10.00/10    |
| cmtadm                       | 10.00/10    |
| cmt-install                  | 10.00/10    |
| cmtinv                       | 10.00/10    |
| cmu                          | __9.88/10__ |
| about.py                     | 10.00/10    |
| ansible_helper.py            | 10.00/10    |
| ansithemeprint.py            | 10.00/10    |
| checks.py                    | 10.00/10    |
| cmtio.py                     | 10.00/10    |
| cmtio_yaml.py                | 10.00/10    |
| cmtlib.py                    | 10.00/10    |
| cmtpaths.py                  | 10.00/10    |
| cmttypes.py                  | 10.00/10    |
| cmtvalidators.py             | 10.00/10    |
| cni_data.py                  | 10.00/10    |
| commandparser.py             | 10.00/10    |
| curses_helper.py             | __9.77/10__ |
| datagetters.py               | 10.00/10    |
| fieldgetters.py              | 10.00/10    |
| formatters.py                | 10.00/10    |
| generators.py                | __9.66/10__ |
| helptexts.py                 | 10.00/10    |
| infogetters.py               | 10.00/10    |
| itemgetters.py               | 10.00/10    |
| kubernetes_helper.py         | 10.00/10    |
| kubernetes_resources.py      | 10.00/10    |
| listgetters.py               | __9.78/10__ |
| listgetters_async.py         | 10.00/10    |
| logparser.py                 | __9.92/10__ |
| networkio.py                 | 10.00/10    |
| objgetters.py                | 10.00/10    |
| pvtypes.py                   | 10.00/10    |
| reexecutor.py                | 10.00/10    |

### Regexploit Results for v0.8.0

Commandline: `regexploit`.
Execute with `make regexploit`.

Output:

```
Running regexploit to check for ReDoS attacks

Checking executables
Processed 44 regexes

Checking libraries
Processed 115 regexes
```

### Semgrep Results for v0.8.0

Commandline: `semgrep scan --exclude-rule "generic.secrets.security.detected-generic-secret.detected-generic-secret.semgrep-legacy.30980" --timeout=0 --no-git-ignore`.
Execute with `make semgrep`.

Output:

```
┌──── ○○○ ────┐
│ Semgrep CLI │
└─────────────┘

Scanning 886 files with:

✔ Semgrep OSS
  ✔ Basic security coverage for first-party code vulnerabilities.

✔ Semgrep Code (SAST)
  ✔ Find and fix vulnerabilities in the code you write with advanced scanning and expert security rules.

✘ Semgrep Supply Chain (SCA)
  ✘ Find and fix the reachable vulnerabilities in your OSS dependencies.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:48


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 5 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 70 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 483 rules on 816 files: 0 findings.

✨ If Semgrep missed a finding, please send us feedback to let us know!
    See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.0

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

`Passed: 0 failure(s), 0 warning(s) on 46 files. Last profile that met the validation criteria was 'production'.`

### validate_yaml Results for v0.8.0

Commandline: `tests/validate_yaml`.
Execute with: `make validate_yaml`.

Output:

```
Summary:
     fail: 0
     skip: 1
  success: 639
    total: 640
```

### YAMLlint Results for v0.8.0

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.
