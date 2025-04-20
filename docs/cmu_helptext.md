# ___`cmu`___ __`COMMAND`__ _`[OPTION]`_... _`[ARGUMENT]`_...

UI for managing Kubernetes clusters.

## Commands:
### `VIEW`
#### start in VIEW
  
### `VIEW` _[_NAMESPACE/_]_OBJECT_[_:_[_MEMBER_]]_
#### start in VIEW for _OBJECT_
  
Sometimes _OBJECT_ may need to be qualified by using _NAMESPACE_, but if there's only one unique match cmu will open that match. If an object has members (containers or configmaps), these can be opened using the _:MEMBER_ syntax. If there's only one member specifying _:_ is sufficient.
  
  
### `list-namespaces`
#### List valid namespaces and exit
  
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

### `list-views`
#### List view information and exit
  
  
### Global Options:

  __`--read-only`__
disable all commands that modify state  

  __`--disable-kubernetes`__
disable Kubernetes support  
This option disables Kubernetes support;
this is typically only useful if you use
cmu to manage an Ansible inventory

  __`--kube-config`__ __PATH__
_PATH_ to kubeconfig file to use  
Use _PATH_ as kubeconfig; by default
_/home/tao/.kube/config_ is used

  __`--namespace`__ __NAMESPACE__
only show objects in namespace _NAMESPACE_  

  __`--theme`__ __THEME__
_THEME_ to use  

  
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
  

If _VIEW_ is not specified cmu will show a list with all available views

_Note_: _cmt.yaml_ or a file in _cmt.yaml.d_ can be used to set a _VIEW_ to use
if no view is specified. To override this and open the selector instead,
simply use “cmu _selector_“.
