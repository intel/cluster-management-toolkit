# Cluster Management Toolkit for Kubernetes

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/8263/badge)](https://www.bestpractices.dev/projects/8263)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/intel/cluster-management-toolkit/badge)](https://securityscorecards.dev/viewer/?uri=github.com/intel/cluster-management-toolkit)
[![Known Vulnerabilities](https://snyk.io/test/github/intel/cluster-management-toolkit/badge.svg)](https://snyk.io/test/github/intel/cluster-management-toolkit)
![GitHub last commit (branch)](https://img.shields.io/github/last-commit/intel/cluster-management-toolkit/main)
![GitHub commits since tagged version](https://img.shields.io/github/commits-since/intel/cluster-management-toolkit/v0.8.5/main)

![CMT Logo](docs/images/cmt_logo.png 'CMT Logo')

----

__Cluster Management Toolkit for Kubernetes__ (CMT) is a set of tools intended
to simplify installation and maintenance of _Kubernetes_ clusters. It provides
tools to setup clusters and manage nodes, either by specifying the configuration
directly on the command line, or through template files. The _curses_-based
user interface (_cmu_) presents the various Kubernetes objects (such as
Pods, Deployments, ConfigMaps, Namespaces, etc.) in a way that tries to obviate
all object relations.

Installation and management is done through a combination of _Ansible_ playbooks,
_Python_ scripts, a _curses_-based user interface, as well as calls to _kubectl_
or _kubeadm_ whenever necessary.

Usage documentation for CMT is available [here](docs/README.md).
