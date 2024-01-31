# ___cmt___ __COMMAND__ _\[OPTION\]_... _\[ARGUMENT\]_...

Commandline tool for managing Kubernetes clusters

## Commands:
### cordon __NODE_,_..._|_ALL__
#### Cordon _NODE_,_..._
  
  
  __--include-control-planes__
  Include control planes when ALL is used  
### drain __NODE_,_..._|_ALL__
#### Drain _NODE_,_..._
  
  
  __--delete-emptydir-data__
  Delete emptydir data  
  __--delete-local-data__
  This is an alias for “__--delete-emptydir-data__“  
  __--disable-eviction__
  Delete pods instead of using evict  
  __--ignore-daemonsets__
  Ignore pods managed by daemonsets  
  __--include-control-planes__
  Include control planes when ALL is used  
### force-drain __NODE_,_..._|_ALL__
#### Force-drain _NODE_,_..._
  
  

When a node is force-drained, pods belonging to daemonsets are ignored, and __emptyDir__ data is deleted
  
  
  __--disable-eviction__
  Delete pods instead of using evict  
  __--include-control-planes__
  Include control planes when ALL is used  
### uncordon __NODE_,_..._|_ALL__
#### Uncordon _NODE_,_..._
  
  
  __--include-control-planes__
  Include control planes when ALL is used  
### taint __NODE_,_..._|_ALL_ _KEY_[=_VALUE_]:_EFFECT__
#### Add taint _KEY_[=_VALUE_] with _EFFECT_ to _NODE_,_..._
  
  

Valid values for _EFFECT_ are: _NoSchedule_, _PreferNoSchedule_, and _NoExecute_
  
  
  __--include-control-planes__
  Include control planes when ALL is used  
  __--overwrite__
  Allow taints to be overwritten  
### untaint __NODE_,_..._|_ALL_ _KEY_[=_VALUE_][:_EFFECT_]_
#### Remove taint _KEY_[:_VALUE_] with _EFFECT_ from _NODE_,_..._
  
  

If _EFFECT_ is not specified, all taints matching _KEY_[:_VALUE_] will be removed
  
  
  __--include-control-planes__
  Include control planes when ALL is used  
### prepare __HOST_,_..._|_PATH__
#### Prepare _HOST_,_..._ for use as cluster node(s)
  
  

_Note_: If possible _HOST_ should be a resolvable hostname; using an IP-address may cause issues
  
  
  __--ignore-existing__
  Ignore hosts that are already part of the cluster  
  __--forks__ __FORKS__
  Max number of parallel Ansible connections  
  __--from-file__
  Treat the argument to prepare as a path  
  __--no-password__
  Do not prompt for a password  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### add-node|add-nodes __HOST_,_..._|_PATH__
#### Add _HOST_,_..._ as Kubernetes nodes to a cluster
  
  

_Note_: If possible _HOST_ should be a resolvable hostname; using an IP-address may cause issues
  
  
  __--ca-cert-file__ __PATH__
  Use _PATH_ as token CA certificate  
  __--cri__ __CRI__
  Use _CRI_ instead of the default CRI  
  __--forks__ __FORKS__
  Max number of parallel Ansible connections  
  __--from-file__
  Treat the argument to prepare as a path  
  __--ignore-existing__
  Ignore hosts that are already part of the cluster  
  __--ignore-non-existing__
  Ignore hosts that are not part of the inventory  
  __--kubernetes-distro__ __DISTRO__
  The Kubernetes distro of the control plane  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### remove-node|remove-nodes __NODE_,_..._|_ALL__
#### Remove _NODE_,_..._ from a Kubernetes cluster
  
  
  __--force__
  Force teardown of non-nodes  
  __--forks__ __FORKS__
  Max number of parallel Ansible connections  
  __--kubernetes-distro__ __DISTRO__
  The Kubernetes distro of the control plane  
  __--purge__
  Purge hosts if teardown completes successfully  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
  __-Y__
  Do not ask for confirmation  
### purge __HOST_,_...__
#### Purge configuration and packages from _HOST_
  
  

purge will run remove-node first if necessary
  
  
  __--ignore-non-existing__
  Ignore non-existing hosts  
  __--forks__ __FORKS__
  Max number of parallel Ansible connections  
  __--kubernetes-distro__ __DISTRO__
  The Kubernetes distro of the control plane  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
### upgrade-node|upgrade-nodes __NODE_,_..._|_ALL__
#### Upgrade Kubernetes on _NODE_,_..._
  
  

This command upgrades Kubernetes on _NODE_,_..._ to the version on the control plane(s); run this on all nodes after running “cmtadm upgrade-control-plane“ _Note_: upgrade-node is currently not implemented for _rke2_
  
  
  __--forks__ __FORKS__
  Max number of parallel Ansible connections  
  __--save-ansible-logs__
  Save logs from Ansible runs  
  __--verbose__
  Be more verbose  
### get-contexts|get-ctx
#### Get the list of available contexts
  
  
### use-context|use-ctx __NAME_|_INDEX__
#### Set current context
  
  

Set current context, either by specifying context _NAME_ or by specifying context _INDEX_
  
  
### api-resources
#### Display available API-resources
  
  
  __--api-group__ __API_GROUP__
  Limit output to _API_GROUP_  
  __--color__ __WHEN__
  WHEN should the output use ANSI-colors  
  __--has-data__
  Only list APIs that have resources  
  __--known__ __FILTER__
  Limit output to _FILTER_  
  __--local__ __true_|_false__
  Limit output to only local or upstream view-files  
  __--namespaced__ __true_|_false__
  Limit output to namespaced or cluster-wide  
  __--no-header__
  Do not output list headers  
  __--format__ __FORMAT__
  Format the output as FORMAT  
  __--sort-by__ __SORTKEY__
  Sort the output by SORTKEY  
  __--verbs__ __VERB_,_...__
  Limit output by supported verbs  
  __--wide__
  Wide output format  
  
  
### help __COMMAND__
#### Display help about _COMMAND_ and exit
  
  
  __--format__ __FORMAT__
  Output the help as _FORMAT_ instead  
### help|--help
#### Display this help and exit
  
  
  __--format__ __FORMAT__
  Output the help as _FORMAT_ instead  
### version|--version
#### Output version information and exit
  
  

You can use “__ALL__“ as a substitute for all resources in most cases;
for instance “cmt upgrade-node __ALL__“ will upgrade Kubernetes on all nodes

Note that “__ALL__“ excludes control planes; to include
control planes you need to use “__--include-control-planes__“ (where applicable)
