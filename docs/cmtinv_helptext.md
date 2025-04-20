# ___`cmtinv`___ __`COMMAND`__ _`[OPTION]`_... _`[ARGUMENT]`_...

Query or modify the host inventory.

## Commands:
### `add-group|add-groups` __GROUP_,_...__
#### Add _GROUP_,_..._ to inventory
  
  __`--vars`__ __KEY_:_VALUE_,_...__
  Set these group variables  

### `add-host|add-hosts` __HOST_,_...__
#### Add _HOST_,_..._ to inventory
  
  __`--groups`__ __GROUP_,_...__
  Add the hosts to these groups  

  __`--vars`__ __KEY_:_VALUE_,_...__
  Set these host variables  

### `add-host|add-hosts` __HOST_,_..._ _GROUP_,_...__
#### Add _HOST_,_..._ to _GROUP_,_..._
  
### `inventory|inv` _[_GROUP_,_..._]_
#### Show inventory, optionally limited to _GROUP_,_..._
  
  __`--color`__ __WHEN__
  WHEN should the output use ANSI-colors  
  Valid arguments are:
  _always_ (always color the output)
  _auto_ (color the output when outputting
  to a terminal)
  _never_ (never color the output)

  __`--include-vars`__
  Show variables  

### `list-hosts`
#### List all hosts
  
  __`--color`__ __WHEN__
  WHEN should the output use ANSI-colors  
  Valid arguments are:
  _always_ (always color the output)
  _auto_ (color the output when outputting
  to a terminal)
  _never_ (never color the output)

  __`--format`__ __FORMAT__
  Format the output as FORMAT  
  Valid formats are:
  _default_ (inventory in tree format)
  _csv_ (comma-separated values)
  _ssv_ (space-separated values)
  _tsv_ (tab-separated values)

  __`--include-vars`__
  Show host variables  

### `list-groups`
#### List all groups
  
  __`--color`__ __WHEN__
  WHEN should the output use ANSI-colors  
  Valid arguments are:
  _always_ (always color the output)
  _auto_ (color the output when outputting
  to a terminal)
  _never_ (never color the output)

  __`--format`__ __FORMAT__
  Format the output as FORMAT  
  Valid formats are:
  _default_ (inventory in tree format)
  _csv_ (comma-separated values)
  _ssv_ (space-separated values)
  _tsv_ (tab-separated values)

  __`--include-vars`__
  Show group variables  

### `ping` _[_GROUP/HOST_,_..._]_
#### Ansible ping _GROUP_,_..._ or _HOST_,_..._ (Default: “_all_“)
  
### `rebuild-inventory`
#### Create inventory for an existing Kubernetes cluster
  
In cases where the cluster has not been created using CMT this command can be used to build a barebones inventory. _Note_: This requires a running cluster.
  
  __`--force`__
  Allow an __existing__ inventory to be overwritten  

### `remove-group|remove-groups` __GROUP_,_...__
#### Remove _GROUP_,_..._ from inventory
  
_Note_: Removing the group “_all_“ is not permitted
  
  __`--force`__
  Allow removal of __non-empty__ groups  

### `remove-host|remove-hosts` __HOST_,_..._ _all__
#### Remove _HOST_,_..._ from inventory
  
  __`--force`__
  Allow __complete__ removal of hosts from inventory  

### `remove-host|remove-hosts` __HOST_,_..._ _GROUP_,_...__
#### Remove _HOST_,_..._ from _GROUP_,_..._
  
### `list-playbooks`
#### List available playbooks
  
  __`--color`__ __WHEN__
  WHEN should the output use ANSI-colors  
  Valid arguments are:
  _always_ (always color the output)
  _auto_ (color the output when outputting
  to a terminal)
  _never_ (never color the output)

  __`--format`__ __FORMAT__
  Format the output as FORMAT  
  Valid formats are:
  _default_ (default format)
  _csv_ (comma-separated values)
  _ssv_ (space-separated values)
  _tsv_ (tab-separated values)

### `explain` __PLAYBOOK_ _
#### Explain what actions _PLAYBOOK_ will perform
  
### `run` __PLAYBOOK_ _HOST_,_..._|_GROUP_,_...__
#### Run playbook on _HOST_,_..._ or _GROUP_,_..._
  
  __`--verbose`__
  Be more verbose  

### `set-var|set-vars` __KEY_:_VALUE_,_...__
#### Set global _KEY_:_VALUE_,_..._
  
Setting global variables is equivalent to setting variables for the group “_all_“
  
### `set-group-var|set-group-vars` __KEY_:_VALUE_,_..._ _GROUP_,_...__
#### Set _KEY_:_VALUE_,_..._ for _GROUP_,_..._
  
### `set-host-var|set-host-vars` __KEY_:_VALUE_,_..._ _HOST_,_...__
#### Set _KEY_:_VALUE_,_..._ for _HOST_,_..._
  
### `unset-var|unset-vars` __KEY__
#### Unset global _KEY_
  
Unsetting global variables is equivalent to unsetting variables for the group “_all_“
  
### `unset-group-var|unset-group-vars` __KEY_ _GROUP_,_...__
#### Unset _KEY_ for _GROUP_,_..._
  
### `unset-host-var|unset-host-vars` __KEY_ _HOST_,_...__
#### Unset _KEY_ for _HOST_,_..._
  
  
### `help` __COMMAND__
#### Display help about _COMMAND_ and exit
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  
  Valid formats are:
  _default_, _markdown_

### `help|--help`
#### Display this help and exit
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  
  Valid formats are:
  _default_, _markdown_

### `version|--version`
#### Output version information and exit
  
