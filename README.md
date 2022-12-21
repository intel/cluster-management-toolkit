# About

__Intel Kubernetes Toolkit__ (iKT) is a set of tools intended to simplify installation
and maintenance of _Kubernetes_ clusters.

Installation and management is done through a combination of _Ansible_ playbooks,
_Python_ scripts, a _curses_-based user interface, as well as calls to _kubectl_
or _kubeadm_ whenever necessary.

The command-line tools __ikt__ and __iktadm__ are __not__ intended to supplant
__kubectl__ / __kubeadm__. __iktadm__ is a userfriendly wrapper around __kubeadm__,
and __ikt__ (and its aliases) only supports a subset of the rich functionality
provided by __kubectl__, but again hopefully in a more userfriendly manner.

Since installation and maintenance tasks are performed using _Ansible_ all hosts
need to be added to the _iKT_ inventory before adding them as nodes;
the inventory view in `iku` allows for running playbooks even on hosts that are not
nodes in the cluster, so adding other infrastructure can also be useful.

_Note_: __iktadm__ runs some minor sanity checks during the prepare step.
It will check whether a control plane has been defined in the inventory;
if not it will ask if the system that `iktadm prepare` is executed on should be added
as a control plane. It will also check whether passwordless sudo is enabled
(this is necessary for most functionality) and, if necessary, create an _ssh_
hostkey and install that in `.ssh/authorized_keys` to allow the control plane
to ssh to itself when running playbooks.

## Installing iKT

Check out this repository and, while in the repository directory, type:

`./ikt-install`
_or_
`./ikt-install --pip-proxy PROXY` (if you need to use a proxy to install from PIP)

This will create symlinks, directories, etc. and install a few packages
necessary to run iKT; it will not install any components of the cluster.

## Using __iKT__ with a pre-existing cluster

If you already have a cluster, the first thing to do is to import your existing
nodes into the inventory. This can easily be achieved by doing:

`iktinv rebuild-inventory`

This only works if you have a `.kube/config` file; if that file contains
several clusters, all of them will be added to the inventory.

After this run:

`iktadm import-cluster`

This will run a subset of the prepare steps that are necessary to run playbooks
on the imported cluster(s).

## Pre-requisites

* One or several hosts running Debian, Ubuntu (at least 20.04 LTS) or another Debian-derivative
* The user must be allowed to sudo to root

Some things that might be relevant to customise in `~/.ikt/ikt.yaml.d/`
before installation starts are items in the sections _Network_, _Ansible_,
_Docker_, and _Containerd_; notably _http_proxy_, _https_proxy_, _no_proxy_.

## Setting up a new cluster using __iKT__

0. _OPTIONAL_: Add customisations to `~/.ikt/ikt.yaml.d/` to override the defaults in `~/.ikt/ikt.yaml`
1. `iktadm preflight-check`
2. `iktadm prepare CLUSTER_NAME [KUBERNETES_VERSION]`
   _or_
   `iktadm prepare --control-plane HOSTNAME CLUSTER_NAME [KUBERNETES_VERSION]`
3. Wait a short while...
4. `iktadm setup-control-plane [CNI] [POD_NETWORK_CIDR]`
5. Wait quite a while...
6. _OPTIONAL_: If you are planning to use the control plane as a worker node: `iktadm untaint-control-plane`

Step 1 will check for known potential issues that can cause setup to fail.

When specifying `--control-plane HOSTNAME` the specified host will be used as control plane.
If no control plane is specified _iktadm_ will check whether there is a controlplane defined
in `~/.ikt/ansible/inventory.yaml`; if not it will ask whether localhost should be used as control plane.

## Add nodes

1. `ikt prepare <host1>[,<host2>,...]`
2. Wait a short while...
3. `ikt add-nodes <host1>[,<host2>,...]`
11. Wait quite a while...

## Removing nodes (purging configuration)

1. `ikt force-drain <node1>[,<node2>,...]`
2. `ikt remove-nodes --purge <node1>[,<node2>,...]`

## CAVEATS

* The _HashKnownHosts_ setting in `/etc/ssh/ssh_config` seems to cause issues with paramiko
  and/or Ansible; until this has been debugged further it is recommended to disable this feature.
  While it can be a semi-useful security-by-obscurity feature on multiuser systems, you generally
  have bigger issues if someone else can access the system you use to set up your Kubernetes cluster.
