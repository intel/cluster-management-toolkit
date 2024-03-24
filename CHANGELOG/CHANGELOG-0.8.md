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
        * [validate_playbooks](#validate-playbooks-results-for-v080)
        * [validate_yaml](#validate-yaml-results-for-v080)
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

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`
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
| noxfile.py              | __Found 3 errors in 1 file (checked 1 source file)__    |
| objgetters.pya          | Success: no issues found in 1 source file               |
| pvtypes.py              | Success: no issues found in 1 source file               |
| reexecutor.py           | Success: no issues found in 1 source file               |

### Pylint Results for v0.8.0

Commandline: `pylint --disable W0511`
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
