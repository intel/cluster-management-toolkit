![CMT Logo](docs/images/cmt_logo.png)

# About

__Cluster Management Toolkit for Kubernetes__ (CMT) is a set of tools intended
to simplify installation and maintenance of _Kubernetes_ clusters. It provides
tools to setup clusters and manage nodes either by specifying the configuration
directly on the command line, or through template files. The _curses_-based
user interface (_cmu_) presents the various Kubernetes objects (such as
Pods, Deployments, ConfigMaps, Namespaces, etc.) in a way that tries to obviate
all object relations.

Installation and management is done through a combination of _Ansible_ playbooks,
_Python_ scripts, a _curses_-based user interface, as well as calls to _kubectl_
or _kubeadm_ whenever necessary.

Usage documentation for CMT is available [here](docs/README.md).
