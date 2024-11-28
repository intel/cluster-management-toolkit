* [v0.8.5](#v085)
    * [Downloads](#downloads-for-v085)
        * [Source Code](#source-code-for-v085)
        * [Distro Packages](#distro-packages-for-v085)
    * [General Release Notes](#general-release-notes-for-v085)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v085)
    * [Changes by Component](#changes-by-component-in-v085)
        * [Changes to _cmt_](#changes-to-cmt-in-v085)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v085)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v085)
        * [Changes to _cmu_](#changes-to-cmu-in-v085)
        * [Changes to other files](#changes-to-other-files-in-v085)
    * [Fixed Issues](#fixed-issues-in-v085)
    * [Known Regressions](#known-regressions-in-v085)
    * [Dependencies](#dependencies-for-v085)
    * [Test Results](#test-results-for-v085)
        * [Bandit](#bandit-results-for-v085)
        * [Coverage](#coverage-results-for-v085)
        * [Flake8](#flake8-results-for-v085)
        * [Mypy](#mypy-results-for-v085)
        * [Pylint](#pylint-results-for-v085)
        * [Regexploit](#regexploit-results-for-v085)
        * [Ruff](#ruff-results-for-v085)
        * [Semgrep](#semgrep-results-for-v085)
        * [validate_playbooks](#validate_playbooks-results-for-v085)
        * [validate_yaml](#validate_yaml-results-for-v085)
        * [YAMLlint](#yamllint-results-for-v085)

# v0.8.5

## Downloads for v0.8.5

### Source Code for v0.8.5

CMT v0.8.5 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.5

CMT v0.8.5 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.5

This is a tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.5

N/A.

## Changes by Component in v0.8.5

### Changes to _cmt_ in v0.8.5

* Fixed a bug in `cmt add-nodes` that caused _cmt_ to fail when reading CA certs.

### Changes to _cmtadm_ in v0.8.5

* `cmtadm import-cluster` now supports the `--save-ansible-logs` option.
* `cmtadm import-cluster` now supports the `--verbose` option.
* `cmtadm upgrade-control-plane` now supports the `--ignore-feature-gates` option.
* `cmtadm upgrade-control-plane` now checks whether feature gates have been altered,
  and refuses to upgrade the cluster if this is the case.
* `cmtadm` now uses `kubeadm.k8s.io/v1beta4` API-version when installing or upgrading to
  _Kubernetes v1.31_

### Changes to _cmtinv_ in v0.8.5

No changes.

### Changes to _cmu_ in v0.8.5

* `cmu` now has the shortcut `^` in info-views, to go up to the parent view.
  This differs from `[ESC]` in that it always goes to the parent view, not to the
  originating view; this difference is significant when arriving to the info-view
  via a shortcut from another infoview.  Note that `^` is a "dead" key on many
  keyboards, so you may need to press the key twice.
* 143 view-files were added.
* The Pod info-view can now has shortcuts to show resources used by the Pod, volume mounts, volumes,
  and topology constraints. It also shows the preemption policy.
* View-files for the new DRA API has been added.
* Other notable view-file changes include _kueue_, _kruise_, _kubeflow_, _volcano_, and _longhorn_.
* 37 parser-files were added.

### Changes to other files in v0.8.5

* _CMT_ can now be installed to, and run from, the system path.
* `cmt-install` now installs _python3-jinja2_.
* Rudimentary support for building views using templates has been added; so far it's only used for `Events*.yaml`.
* A new tool, `mdtable.py` has been added, that creates simple Markdown tables from CSV data.
  It's now used by the `mypy-markdown` and `pylint-markdown` Make targets.
* A lot of code has been refactored, documented, or otherwise improved.
  In total `986 files changed, 66401 insertions(+), 27598 deletions(-)`.

## Fixed Issues in v0.8.5

* _cmtadm_ fixes several issues with upgrading to _Kubernetes 1.31_.

## Known Regressions in v0.8.5

* `cmtadm setup-control-plane` may not be fully working; `cmtadm create-cluster` is now the recommended
  way to setup clusters, and long-term plans is to deprecate and eventually remove `cmtadm setup-control-plane`.

## Known Issues in v0.8.5

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data.
  The version data can be refreshed using `cmtadm cv`.

## Dependencies for v0.8.5

### Python

| PIP Name       | Minimum Version | Note                                    |
| :------------- | :-------------- | :-------------------------------------- |
| ansible-runner | 2.1.4           | openSUSE/SLES/RHEL, unsupported distros |
| cryptography   |                 | openSUSE, unsupported distros           |
| jinja2         | 3.1.4           | openSUSE/SLES/RHEL, unsupported distros |
| natsort        | 8.0.2           | openSUSE/SLES/RHEL, unsupported distros |
| paramiko       |                 | openSUSE/SLES/RHEL, unsupported distros |
| PyYAML         | 6.0             | Unsupported distros                     |
| setuptools     | 70.0.0          | openSUSE/SLES/RHEL, unsupported distros |
| ujson          | 5.4.0           | openSUSE/SLES/RHEL, unsupported distros |
| urllib3        | 1.26.19         | openSUSE/SLES, unsupported distros      |
| validators     | 0.22.0          | openSUSE/SLES/RHEL, unsupported distros |

### Distro Packages

| Package Name           | Distro             |
| :--------------------- | :----------------- |
| ansible                | Debian/Ubuntu/SUSE |
| python3-ansible-runner | Debian/Ubuntu      |
| python3-cryptography   | Debian/RHEL/Ubuntu |
| python3-jinja2         | Debian/Ubuntu      |
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
| :------- | :------------------ |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.5

Before release the code quality has been checked with _pylint_, _flake8_, _mypy_, and _ruff_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.5

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
	No issues identified.

Code scanned:
	Total lines of code: 77503
	Total lines skipped (#nosec): 8

Run metrics:
	Total issues (by severity):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 0
	Total issues (by confidence):
		Undefined: 0
		Low: 0
		Medium: 0
		High: 0
Files skipped (0):
```

### Coverage Results for v0.8.5

Commandline: `python3-coverage run --branch --append <file> && python3-coverage report --sort cover --precision 1`.

Execute with:

```
make coverage
make coverage-ansible
make coverage-cluster
```

Output:

```
Name                                                  Stmts   Miss Branch BrPart  Cover
---------------------------------------------------------------------------------------
clustermanagementtoolkit/listgetters_async.py           119    103     54      0   9.2%
clustermanagementtoolkit/networkio.py                   349    282    173      3  16.9%
clustermanagementtoolkit/infogetters.py                1676   1270   1008     68  21.9%
clustermanagementtoolkit/itemgetters.py                 506    372    290     14  22.6%
clustermanagementtoolkit/fieldgetters.py                 81     54     46      0  27.6%
clustermanagementtoolkit/kubernetes_helper.py          1494   1004    760     62  27.9%
clustermanagementtoolkit/listgetters.py                1212    808    662     90  28.7%
clustermanagementtoolkit/curses_helper.py              2388   1544   1124    125  29.0%
clustermanagementtoolkit/logparser.py                  2008   1275   1125     45  31.1%
clustermanagementtoolkit/datagetters.py                 277    181    142      5  32.2%
clustermanagementtoolkit/generators.py                  726    358    384     44  44.1%
clustermanagementtoolkit/checks.py                      631    310    248     11  47.3%
clustermanagementtoolkit/formatters.py                  807    310    424     25  57.8%
clustermanagementtoolkit/ansible_helper.py              805    199    490     24  74.0%
clustermanagementtoolkit/cmtlib.py                      659    125    388     34  77.2%
clustermanagementtoolkit/cmtio.py                       425     33    242     21  90.7%
clustermanagementtoolkit/ansithemeprint.py              216      6     84      3  96.3%
clustermanagementtoolkit/reexecutor.py                   72      0     34      3  97.2%
clustermanagementtoolkit/commandparser.py               412      1    254      2  99.5%
clustermanagementtoolkit/cmtvalidators.py               324      0    200      1  99.8%
clustermanagementtoolkit/about.py                        18      0      0      0 100.0%
clustermanagementtoolkit/cmtio_yaml.py                   34      0      6      0 100.0%
clustermanagementtoolkit/cmtpaths.py                     89      0      0      0 100.0%
clustermanagementtoolkit/cmttypes.py                    471      0    178      0 100.0%
clustermanagementtoolkit/cni_data.py                     37      0      8      0 100.0%
clustermanagementtoolkit/helptexts.py                    23      0      0      0 100.0%
clustermanagementtoolkit/kubernetes_resources.py          3      0      0      0 100.0%
clustermanagementtoolkit/objgetters.py                   56      0     12      0 100.0%
clustermanagementtoolkit/pvtypes.py                       1      0      0      0 100.0%
clustermanagementtoolkit/recommended_permissions.py      11      0      0      0 100.0%
---------------------------------------------------------------------------------------
TOTAL                                                 15930   8235   8336    580  44.2%
```


### Flake8 Results for v0.8.5

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.5

Commandline: `mypy --follow-imports silent --explicit-package-bases --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators --warn-redundant-casts --warn-unused-ignores`.
Execute with `make mypy-markdown`.

| Source file                                         | Score                                                 |
| :-------------------------------------------------- | :------------------------------------------------     |
| cmt                                                 | Success: no issues found in 1 source file             |
| cmtadm                                              | Success: no issues found in 1 source file             |
| cmt-install                                         | Success: no issues found in 1 source file             |
| cmtinv                                              | Success: no issues found in 1 source file             |
| cmu                                                 | **Found 94 errors in 1 file (checked 1 source file)** |
| clustermanagementtoolkit/about.py                   | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/ansible_helper.py          | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/ansithemeprint.py          | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/checks.py                  | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cluster_actions.py         | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmtio.py                   | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmtio_yaml.py              | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmtlib.py                  | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmtpaths.py                | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmttypes.py                | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cmtvalidators.py           | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/cni_data.py                | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/commandparser.py           | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/curses_helper.py           | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/datagetters.py             | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/fieldgetters.py            | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/formatters.py              | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/generators.py              | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/helptexts.py               | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/infogetters.py             | **Found 18 errors in 1 file (checked 1 source file)** |
| clustermanagementtoolkit/itemgetters.py             | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/kubernetes_helper.py       | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/kubernetes_resources.py    | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/listgetters.py             | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/listgetters_async.py       | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/logparser.py               | **Found 62 errors in 1 file (checked 1 source file)** |
| clustermanagementtoolkit/networkio.py               | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/objgetters.py              | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/pvtypes.py                 | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/recommended_permissions.py | Success: no issues found in 1 source file             |
| clustermanagementtoolkit/reexecutor.py              | Success: no issues found in 1 source file             |

### Pylint Results for v0.8.5

Commandline: `pylint --py-version 3.9 --disable W0511 --enable useless-suppression`.
Table generated with `make pylint-markdown`.
Currently all complaints are due to missing function or method docstrings.

| Source file                                         | Score        |
| :-------------------------------------------------- | -----------: |
| cmt                                                 | 10.00/10     |
| cmtadm                                              | 10.00/10     |
| cmt-install                                         | 10.00/10     |
| cmtinv                                              | 10.00/10     |
| cmu                                                 | 10.00/10     |
| clustermanagementtoolkit/about.py                   | 10.00/10     |
| clustermanagementtoolkit/ansible_helper.py          | 10.00/10     |
| clustermanagementtoolkit/ansithemeprint.py          | 10.00/10     |
| clustermanagementtoolkit/checks.py                  | 10.00/10     |
| clustermanagementtoolkit/cluster_actions.py         | 10.00/10     |
| clustermanagementtoolkit/cmtio.py                   | 10.00/10     |
| clustermanagementtoolkit/cmtio_yaml.py              | 10.00/10     |
| clustermanagementtoolkit/cmtlib.py                  | 10.00/10     |
| clustermanagementtoolkit/cmtpaths.py                | 10.00/10     |
| clustermanagementtoolkit/cmttypes.py                | 10.00/10     |
| clustermanagementtoolkit/cmtvalidators.py           | 10.00/10     |
| clustermanagementtoolkit/cni_data.py                | 10.00/10     |
| clustermanagementtoolkit/commandparser.py           | 10.00/10     |
| clustermanagementtoolkit/curses_helper.py           | **9.85/10**  |
| clustermanagementtoolkit/datagetters.py             | 10.00/10     |
| clustermanagementtoolkit/fieldgetters.py            | 10.00/10     |
| clustermanagementtoolkit/formatters.py              | 10.00/10     |
| clustermanagementtoolkit/generators.py              | 10.00/10     |
| clustermanagementtoolkit/helptexts.py               | 10.00/10     |
| clustermanagementtoolkit/infogetters.py             | 10.00/10     |
| clustermanagementtoolkit/itemgetters.py             | 10.00/10     |
| clustermanagementtoolkit/kubernetes_helper.py       | 10.00/10     |
| clustermanagementtoolkit/kubernetes_resources.py    | 10.00/10     |
| clustermanagementtoolkit/listgetters.py             | **9.95/10**  |
| clustermanagementtoolkit/listgetters_async.py       | 10.00/10     |
| clustermanagementtoolkit/logparser.py               | **9.93/10**  |
| clustermanagementtoolkit/networkio.py               | 10.00/10     |
| clustermanagementtoolkit/objgetters.py              | 10.00/10     |
| clustermanagementtoolkit/pvtypes.py                 | 10.00/10     |
| clustermanagementtoolkit/recommended_permissions.py | 10.00/10     |
| clustermanagementtoolkit/reexecutor.py              | 10.00/10     |

### Regexploit Results for v0.8.5

Commandline: `regexploit`.
Execute with `make regexploit`.

Output:

```
Running regexploit to check for ReDoS attacks

Checking executables
Processed 43 regexes

Checking libraries
Processed 143 regexes
```

### Ruff Results for v0.8.5

Commandline: `ruff check --target-version py39`.
Execute with `make ruff`.

Output:

No output.

### Semgrep Results for v0.8.5

Commandline: `semgrep scan --exclude-rule "generic.secrets.security.detected-generic-secret.detected-generic-secret.semgrep-legacy.30980" --exclude-rule "python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2" --exclude "*.yaml" --exclude "*.j2" --exclude "*.json" --timeout=0 --no-git-ignore`.
Execute with `make semgrep`.

Output:

```
┌──── ○○○ ────┐
│ Semgrep CLI │
└─────────────┘


Scanning 1105 files with:

✔ Semgrep OSS
  ✔ Basic security coverage for first-party code vulnerabilities.

✔ Semgrep Code (SAST)
  ✔ Find and fix vulnerabilities in the code you write with advanced scanning and expert security rules.

✘ Semgrep Supply Chain (SCA)
  ✘ Find and fix the reachable vulnerabilities in your OSS dependencies.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:03:30


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 2 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 948 files matching --exclude patterns, 62 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 600 rules on 95 files: 0 findings.

✨ If Semgrep missed a finding, please send us feedback to let us know!
   See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.5

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

```
Passed: 0 failure(s), 0 warning(s) on 54 files. Last profile that met the validation criteria was 'production'.
```

### validate_yaml Results for v0.8.5

Commandline: `tests/validate_yaml`.
Execute with: `make validate_yaml`.

Output:

```
Summary:
     fail: 0
     skip: 3
  success: 824
    total: 827
```

### YAMLlint Results for v0.8.5

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.

---

* [v0.8.4](#v084)
    * [Downloads](#downloads-for-v084)
        * [Source Code](#source-code-for-v084)
        * [Distro Packages](#distro-packages-for-v084)
    * [General Release Notes](#general-release-notes-for-v084)
    * [Urgent Upgrade Notes](#urgent-upgrade-notes-for-v084)
    * [Changes by Component](#changes-by-component-in-v084)
        * [Changes to _cmt_](#changes-to-cmt-in-v084)
        * [Changes to _cmtadm_](#changes-to-cmtadm-in-v084)
        * [Changes to _cmtinv_](#changes-to-cmtinv-in-v084)
        * [Changes to _cmu_](#changes-to-cmu-in-v084)
        * [Changes to other files](#changes-to-other-files-in-v084)
    * [Fixed Issues](#fixed-issues-in-v084)
    * [Known Regressions](#known-regressions-in-v084)
    * [Dependencies](#dependencies-for-v084)
    * [Test Results](#test-results-for-v084)
        * [Bandit](#bandit-results-for-v084)
        * [Coverage](#coverage-results-for-v084)
        * [Flake8](#flake8-results-for-v084)
        * [Pylint](#pylint-results-for-v084)
        * [Regexploit](#regexploit-results-for-v084)
        * [Ruff](#ruff-results-for-v084)
        * [Semgrep](#semgrep-results-for-v084)
        * [validate_playbooks](#validate_playbooks-results-for-v084)
        * [validate_yaml](#validate_yaml-results-for-v084)
        * [YAMLlint](#yamllint-results-for-v084)

# v0.8.4

## Downloads for v0.8.4

### Source Code for v0.8.4

CMT v0.8.4 does not include source code tarballs. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with source code tarballs.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.4

CMT v0.8.4 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
| [fixme](https://fixme) (Debian 11+ amd64 / Ubuntu 22.04+) | `fixme` |
| [fixme](https://fixme) (RHEL 9+ amd64) | `fixme` |
| [fixme](https://fixme) (SLES/openSUSE 15.4+ amd64) | `fixme` |
-->

## General Release Notes for v0.8.4

This is a tagged release of __Cluster Management Toolkit for Kubernetes__ (CMT).
It provides support for setting up Kubernetes clusters either using templates (recommended)
or step by step.

It also provides tools for managing the underlying hosts (and, optionally, hosts
that are not part of the cluster) using Ansible.

Finally it contains a Curses-based user interface (`cmu`) that provides an overview
of the cluster objects and their relations; for instance the user interface provides
links from the Pod view directly to its controller, config maps, logs, namespace,
secrets, etc.

## Urgent Upgrade Notes for v0.8.4

This release contains another fix for the Kubernetes version check.

## Changes by Component in v0.8.4

### Changes to _cmt_ in v0.8.4

No changes.

### Changes to _cmtadm_ in v0.8.4

* `cmtadm check-versions` now has a `--force` option.

### Changes to _cmtinv_ in v0.8.4

No changes.

### Changes to _cmu_ in v0.8.4

No changes.

### Changes to other files in v0.8.4

* `sources/antrea.yaml`, `sources/calico.yaml`, `sources/cilium.yaml`, and `views/__VersionData.yaml`: show version information for antctl, cilium-cli, and calicoctl (if installed).
* `sources/kubernetes.yaml` now uses the correct version check helper.
* `listgetters.py`: listgetter_files() now has an option to skip empty or missing items.

## Fixed Issues in v0.8.4

Fix version check for Kubernetes.

## Known Regressions in v0.8.4

Pylint fails to test the executables; this is an issue in Pylint though, not in CMT.

## Known Issues in v0.8.4

* The UI flickers until data has been populated; it can also flicker in certain other scenarios.
* The version data view in the UI does not refresh the version data.
  The version data can be refreshed using `cmtadm cv`.
* Installing to the system path is currently not supported.

## Dependencies for v0.8.4

### Python

| PIP Name       | Minimum Version | Note                                    |
| :------------- | :-------------- | :-------------------------------------- |
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
| :--------------------- | :----------------- |
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
| :------- | :------------------ |
| ansible  | Unsupported distros |
| sshpass  | Unsupported distros |

## Test Results for v0.8.4

Before release the code quality has been checked with _pylint_, _flake8_, _mypy_, and _ruff_.
The code has been checked for security issues using _bandit_, _regexploit_, and _semgrep_.
The _Ansible_ playbooks have been checked using _ansible-lint_.
YAML-files have been checked using _yamllint_ and validated against predefined schemas.
Unit-test coverage has been measured using _python3-coverage_.

The results of these tests are as follows:

### Bandit Results for v0.8.4

Commandline: `bandit -c .bandit`.
Execute with `make bandit`.

Output:

```
Test results:
        No issues identified.

Code scanned:
        Total lines of code: 71488
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

### Coverage Results for v0.8.4

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
listgetters.py                1172    959    636     17  15.0%
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
TOTAL                        14211   7660   7284    390  42.8%
```


### Flake8 Results for v0.8.4

Commandline: `flake8 --max-line-length 100 --ignore F841,W503 --statistics`.
Execute with `make flake8`.

Output:

No output.

### mypy Results for v0.8.4

Commandline: `mypy --ignore-missing --disallow-untyped-calls --disallow-untyped-defs --disallow-incomplete-defs --check-untyped-defs --disallow-untyped-decorators`.
Execute with `make mypy-markdown`.

| Source file             | Score                                                   |
| :---------------------- | :------------------------------------------------------ |
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

### Pylint Results for v0.8.4

**N/A**. Pylint seems to be broken in Debian at the moment and crashes during testing.

### Regexploit Results for v0.8.4

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

### Ruff Results for v0.8.4

Commandline: `ruff`.
Execute with `make ruff`.

Output:

No output.

### Semgrep Results for v0.8.4

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

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╸ 100% 0:00:38


┌──────────────┐
│ Scan Summary │
└──────────────┘
Some files were skipped or only partially analyzed.
  Partially scanned: 2 files only partially analyzed due to parsing or internal Semgrep errors
  Scan skipped: 73 files matching .semgrepignore patterns
  For a full list of skipped files, run semgrep with the --verbose flag.

Ran 472 rules on 838 files: 0 findings.

✨ If Semgrep missed a finding, please send us feedback to let us know!
    See https://semgrep.dev/docs/reporting-false-negatives/
```

### validate_playbooks Results for v0.8.4

Commandline: `ansible-lint`.
Execute with: `make validate_playbooks`.

`Passed: 0 failure(s), 0 warning(s) on 55 files. Last profile that met the validation criteria was 'production'.`

### validate_yaml Results for v0.8.4

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

### YAMLlint Results for v0.8.4

Commandline: `yamllint`.
Execute with `make yamllint`.

Output:

No output.

---

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
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.3

CMT v0.8.3 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
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
| :------------- | :-------------- | :-------------------------------------- |
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
| :--------------------- | :----------------- |
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
| :------- | :------------------ |
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
| :---------------------- | :------------------------------------------------------ |
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
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.2

CMT v0.8.2 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
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
| :------------- | :-------------- | :-------------------------------------- |
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
| :--------------------- | :----------------- |
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
| :------- | :------------------ |
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
| :---------------------- | :------------------------------------------------------ |
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
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.1

CMT v0.8.1 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
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
| :------------- | :-------------- | :-------------------------------------- |
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
| :--------------------- | :----------------- |
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
| :------- | :------------------ |
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
| :---------------------- | :------------------------------------------------------ |
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
| :--------------------------- | :----       |
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
| :------- | :---------- |
| [fixme](https://fixme) | `fixme` |
-->

### Distro packages for v0.8.0

CMT v0.8.0 does not include distro packages. It is just a git tag.
We aim for CMT v0.9.0 to be the first release with distro packages.

<!--
| Filename | sha512 hash |
| :------- | :---------- |
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
| :------------- | :-------------- | :-------------------------------------- |
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
| :--------------------- | :----------------- |
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
| :------- | :------------------ |
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
| :---------------------- | :------------------------------------------------------ |
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
| :--------------------------- | :----       |
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
