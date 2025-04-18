# ___`cmt`___ __`COMMAND`__ _`[OPTION]`_... _`[ARGUMENT]`_...

Commandline tool for managing Kubernetes clusters

## Commands:
### cordon __NODE_,_..._|_ALL__
#### Cordon _NODE_,_..._
  
  
  __`--include-control-planes`__
  Include control planes when ALL is used  
### drain __NODE_,_..._|_ALL__
#### Drain _NODE_,_..._
  
  
  __`--delete-emptydir-data`__
  Delete emptydir data  

  Drain nodes even if this would cause __emptyDir__

  data to be deleted
  __`--delete-local-data`__
  This is an alias for “__--delete-emptydir-data__“  
  __`--disable-eviction`__
  Delete pods instead of using evict  

  This bypasses __PodDisruptionBudget__
  __`--ignore-daemonsets`__
  Ignore pods managed by daemonsets  

  By default drain will abort if there are

  such pods running on the node
  __`--include-control-planes`__
  Include control planes when ALL is used  
### force-drain __NODE_,_..._|_ALL__
#### Force-drain _NODE_,_..._
  
  

When a node is force-drained, pods belonging to daemonsets are ignored, and __emptyDir__ data is deleted
  
  
  __`--disable-eviction`__
  Delete pods instead of using evict  

  This bypasses __PodDisruptionBudget__
  __`--include-control-planes`__
  Include control planes when ALL is used  
### uncordon __NODE_,_..._|_ALL__
#### Uncordon _NODE_,_..._
  
  
  __`--include-control-planes`__
  Include control planes when ALL is used  
### taint __NODE_,_..._|_ALL_ _KEY_[=_VALUE_]:_EFFECT__
#### Add taint _KEY_[=_VALUE_] with _EFFECT_ to _NODE_,_..._
  
  

Valid values for _EFFECT_ are: _NoSchedule_, _PreferNoSchedule_, and _NoExecute_
  
  
  __`--include-control-planes`__
  Include control planes when ALL is used  
  __`--overwrite`__
  Allow taints to be overwritten  

  (by default conflicting taints are ignored)
### untaint __NODE_,_..._|_ALL_ _KEY_[=_VALUE_][:_EFFECT_]_
#### Remove taint _KEY_[:_VALUE_] with _EFFECT_ from _NODE_,_..._
  
  

If _EFFECT_ is not specified, all taints matching _KEY_[:_VALUE_] will be removed
  
  
  __`--include-control-planes`__
  Include control planes when ALL is used  
### prepare __HOST_,_..._|_PATH__
#### Prepare _HOST_,_..._ for use as cluster node(s)
  
  

_Note_: If possible _HOST_ should be a resolvable hostname; using an IP-address may cause issues
  
  
  __`--ignore-existing`__
  Ignore hosts that are already part of the cluster  
  __`--forks`__ __FORKS__
  Max number of parallel Ansible connections  

  This sets the max number of parallel connections

  when running Ansible playbooks

  (this overrides _cmt.yaml_; default: _5_)
  __`--from-file`__
  Treat the argument to prepare as a path  

  When using this option the HOST

  argument will be treated as a path to a file

  with hostnames instead of a list of hostnames
  __`--no-password`__
  Do not prompt for a password  

  Use this if the hosts you are preparing

  are already configured for login using an SSH key
  __`--save-ansible-logs`__
  Save logs from Ansible runs  

  The logs can be viewed using “cmu logs“
  __`--verbose`__
  Be more verbose  
  __`-Y`__
  Do not ask for confirmation  
### add-node|add-nodes __HOST_,_..._|_PATH__
#### Add _HOST_,_..._ as Kubernetes nodes to a cluster
  
  

_Note_: If possible _HOST_ should be a resolvable hostname; using an IP-address may cause issues
  
  
  __`--ca-cert-file`__ __PATH__
  Use _PATH_ as token CA certificate  
  __`--cri`__ __CRI__
  Use _CRI_ instead of the default CRI  

  Valid options for CRI

  (Container Runtime Interface) are:

  _containerd_, _cri-o_

  Default CRI: _containerd_

  _Note_: Kubernetes >= _1.26_ requires

  containerd >= _1.6_ or cri-o.

  If you intend to use DRA you should use cri-o.
  __`--forks`__ __FORKS__
  Max number of parallel Ansible connections  

  This sets the max number of parallel connections

  when running Ansible playbooks

  (this overrides _cmt.yaml_; default: _5_)
  __`--from-file`__
  Treat the argument to prepare as a path  

  When using this option the HOST

  argument will be treated as a path to a file

  with hostnames instead of a list of hostnames
  __`--ignore-existing`__
  Ignore hosts that are already part of the cluster  
  __`--ignore-non-existing`__
  Ignore hosts that are not part of the inventory  
  __`--kubernetes-distro`__ __DISTRO__
  The Kubernetes distro of the control plane  

  Depending on the Kubernetes distro in use a lot

  of things during node setup has to be done

  differently. If this option is not specified

  cmt will assume that _kubeadm_ is used.

  Supported options:

  _kubeadm_ (default)

  _rke2_ (default on SUSE)

  _Note_: currently _rke2_ is the only supported

  option on SUSE
  __`--save-ansible-logs`__
  Save logs from Ansible runs  

  The logs can be viewed using “cmu logs“
  __`--verbose`__
  Be more verbose  
  __`-Y`__
  Do not ask for confirmation  
### remove-node|remove-nodes __NODE_,_..._|_ALL__
#### Remove _NODE_,_..._ from a Kubernetes cluster
  
  
  __`--force`__
  Force teardown of non-nodes  

  Attempt to teardown Kubernetes nodes

  that are no longer part of the cluster
  __`--forks`__ __FORKS__
  Max number of parallel Ansible connections  

  This sets the max number of parallel connections

  when running Ansible playbooks

  (this overrides _cmt.yaml_; default: _5_)
  __`--kubernetes-distro`__ __DISTRO__
  The Kubernetes distro of the control plane  

  Depending on the Kubernetes distro in use a lot

  of things during node teardown has to be done

  differently. If this option is not specified

  cmt will assume that _kubeadm_ is used.

  Supported options:

  _kubeadm_ (default)

  _rke2_ (default on SUSE)

  _Note_: currently _rke2_ is the only supported

  option on SUSE
  __`--purge`__
  Purge hosts if teardown completes successfully  
  __`--save-ansible-logs`__
  Save logs from Ansible runs  

  The logs can be viewed using “cmu logs“
  __`--verbose`__
  Be more verbose  
  __`-Y`__
  Do not ask for confirmation  
### purge __HOST_,_...__
#### Purge configuration and packages from _HOST_
  
  

purge will run remove-node first if necessary
  
  
  __`--ignore-non-existing`__
  Ignore non-existing hosts  

  Silently ignore hosts that cannot be found

  in the inventory
  __`--forks`__ __FORKS__
  Max number of parallel Ansible connections  

  This sets the max number of parallel connections

  when running Ansible playbooks

  (this overrides _cmt.yaml_; default: _5_)
  __`--kubernetes-distro`__ __DISTRO__
  The Kubernetes distro of the control plane  

  Depending on the Kubernetes distro in use a lot

  of things during node teardown has to be done

  differently. If this option is not specified

  cmt will assume that _kubeadm_ is used.

  Supported options:

  _kubeadm_ (default)

  _rke2_ (default on SUSE)

  _Note_: currently _rke2_ is the only supported

  option on SUSE
  __`--save-ansible-logs`__
  Save logs from Ansible runs  

  The logs can be viewed using “cmu logs“
  __`--verbose`__
  Be more verbose  
### upgrade-node|upgrade-nodes __NODE_,_..._|_ALL__
#### Upgrade Kubernetes on _NODE_,_..._
  
  

This command upgrades Kubernetes on _NODE_,_..._ to the version on the control plane(s); run this on all nodes after running “cmtadm upgrade-control-plane“ _Note_: upgrade-node is currently not implemented for _rke2_
  
  
  __`--forks`__ __FORKS__
  Max number of parallel Ansible connections  

  This sets the max number of parallel connections

  when running Ansible playbooks

  (this overrides _cmt.yaml_; default: _5_)
  __`--save-ansible-logs`__
  Save logs from Ansible runs  

  The logs can be viewed using “cmu logs“
  __`--verbose`__
  Be more verbose  
### get-contexts|get-ctx
#### Get the list of available contexts
  
  
### use-context|use-ctx __NAME_|_INDEX__
#### Set current context
  
  

Set current context, either by specifying context _NAME_ or by specifying context _INDEX_
  
  
### api-resources
#### Display available API-resources
  
  
  __`--api-group`__ __API_GROUP__
  Limit output to _API_GROUP_  

  If the version part of _API_GROUP_ is omitted,

  all versions of the API-GROUP are included.

  To only show core APIs, use _""_.
  __`--color`__ __WHEN__
  WHEN should the output use ANSI-colors  

  Valid arguments are:

  _always_ (always color the output)

  _auto_ (color the output when outputting

  to a terminal)

  _never_ (never color the output)
  __`--has-data`__
  Only list APIs that have resources  

  This option will only list APIs that have data.

  _Note_: this can be very slow.
  __`--known`__ __FILTER__
  Limit output to _FILTER_  

  Valid values are:

  _unknown_/_not-known_, _updated_

  or a combination of:

  _known_, _list_/_not-list_ and _info_/_not-info_.

  _unknown_/_not-known_ limits the output to APIs that

  are unknown to CMT.

  _updated_ limits the output to APIs that are

  either unknown to CMT or have been updated.

  _known_ limits the output to APIs that are

  known by CMT; augment this with

  _list_/_not-list_ and _info_/_not-info_

  to limit the output based on whether CMT

  has __list__ and __info__ views available.
  __`--local`__ __true_|_false__
  Limit output to only local or upstream view-files  

  If _true_ only locally added view-files are

  considered when determining API-support level.

  If _false_ only upstream view-files are considered

  when determining API-support level.

  By default both local and upstream view-files

  are considered.
  __`--namespaced`__ __true_|_false__
  Limit output to namespaced or cluster-wide  

  If _true_ only namespaced resources will be listed.

  If _false_ only cluster-wide resources will be

  listed. By default all resources are listed.
  __`--no-header`__
  Do not output list headers  
  __`--format`__ __FORMAT__
  Format the output as FORMAT  

  Valid formats are:

  _table_ (table with information)

  _csv_ (comma-separated values)

  _ssv_ (space-separated values)

  _tsv_ (tab-separated values)

  _entry_ (used when adding API support to CMT)
  __`--sort-by`__ __SORTKEY__
  Sort the output by SORTKEY  

  Valid sortkeys are:

  _name_

  _apiversion_

  _namespaced_

  _kind_
  __`--verbs`__ __VERB_,_...__
  Limit output by supported verbs  
  __`--wide`__
  Wide output format  
  
  
### help __COMMAND__
#### Display help about _COMMAND_ and exit
  
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  

  Valid formats are:

  _default_, _markdown_
### help|--help
#### Display this help and exit
  
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  

  Valid formats are:

  _default_, _markdown_
### version|--version
#### Output version information and exit
  
  

You can use “__ALL__“ as a substitute for all resources in most cases;
for instance “cmt upgrade-node __ALL__“ will upgrade Kubernetes on all nodes

Note that “__ALL__“ excludes control planes; to include
control planes you need to use “__--include-control-planes__“ (where applicable)
