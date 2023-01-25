# About

__Cluster Management Toolkit for Kubernetes__ (CMT) is a set of tools intended
to simplify installation and maintenance of _Kubernetes_ clusters.

Installation and management is done through a combination of _Ansible_ playbooks,
_Python_ scripts, a _curses_-based user interface, as well as calls to _kubectl_
or _kubeadm_ whenever necessary.

The command-line tools __cmt__ and __cmtadm__ are __not__ intended to supplant
__kubectl__ / __kubeadm__. __cmtadm__ is a userfriendly wrapper around __kubeadm__,
and __cmt__ (and its aliases) only supports a subset of the rich functionality
provided by __kubectl__, but again hopefully in a more userfriendly manner.

Since installation and maintenance tasks are performed using _Ansible_ all hosts
need to be added to the _CMT_ inventory before adding them as nodes;
the inventory view in `cmu` allows for running playbooks even on hosts that are not
nodes in the cluster, so adding other infrastructure can also be useful.

_Note_: __cmtadm__ runs some minor sanity checks during the prepare step.
It will check whether a control plane has been defined in the inventory;
if not it will ask if the system that `cmtadm prepare` is executed on should be added
as a control plane. It will also check whether passwordless sudo is enabled
(this is necessary for most functionality) and, if necessary, create an _ssh_
hostkey and install that in `.ssh/authorized_keys` to allow the control plane
to ssh to itself when running playbooks.

## Installing CMT

Check out this repository and, while in the repository directory, type:

`./cmt-install`
_or_
`./cmt-install --pip-proxy PROXY` (if you need to use a proxy to install from PIP)

This will create symlinks, directories, etc. and install a few packages
necessary to run CMT; it will not install any components of the cluster.

## Using __CMT__ with a pre-existing cluster

If you already have a cluster, the first thing to do is to import your existing
nodes into the inventory. This can easily be achieved by doing:

`cmtinv rebuild-inventory`

This only works if you have a `.kube/config` file; if that file contains
several clusters, all of them will be added to the inventory.

After this run:

`cmtadm import-cluster`

This will run a subset of the prepare steps that are necessary to run playbooks
on the imported cluster(s).

## Pre-requisites

* One or several hosts running Debian, Ubuntu (at least 20.04 LTS) or another Debian-derivative
* The user must be allowed to sudo to root

Some things that might be relevant to customise in `~/.cmt/cmt.yaml.d/`
before installation starts are items in the sections _Network_, _Ansible_,
_Docker_, and _Containerd_; notably _http_proxy_, _https_proxy_, _no_proxy_.

## Setting up a new cluster using __CMT__

0. _OPTIONAL_: Add customisations to `~/.cmt/cmt.yaml.d/` to override the defaults in `~/.cmt/cmt.yaml`
1. `cmtadm preflight-check HOSTNAME` # Where HOSTNAME is the host you intend to use as control plane
2. `cmtadm prepare CLUSTER_NAME [KUBERNETES_VERSION]`
   _or_
   `cmtadm prepare --control-plane HOSTNAME CLUSTER_NAME [KUBERNETES_VERSION]`
3. Wait a short while...
4. `cmtadm setup-control-plane [CNI] [POD_NETWORK_CIDR]`
5. Wait quite a while...
6. _OPTIONAL_: If you are planning to use the control plane as a worker node: `cmtadm untaint-control-plane`

Step 1 will check for known potential issues that can cause setup to fail.

When specifying `--control-plane HOSTNAME` the specified host will be used as control plane.
If no control plane is specified _cmtadm_ will check whether there is a controlplane defined
in `~/.cmt/ansible/inventory.yaml`; if not it will ask whether localhost should be used as control plane.

## Add nodes

1. `cmt prepare <host1>[,<host2>,...]`
2. Wait a short while...
3. `cmt add-nodes <host1>[,<host2>,...]`
11. Wait quite a while...

## Removing nodes (purging configuration)

1. `cmt force-drain <node1>[,<node2>,...]`
2. `cmt remove-nodes --purge <node1>[,<node2>,...]`

## CAVEATS

* The _HashKnownHosts_ setting in `/etc/ssh/ssh_config` seems to cause issues with paramiko
  and/or Ansible; until this has been debugged further it is recommended to disable this feature.
  While it can be a semi-useful security-by-obscurity feature on multiuser systems, you generally
  have bigger issues if someone else can access the system you use to set up your Kubernetes cluster.
