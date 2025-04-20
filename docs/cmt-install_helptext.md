# ___`cmt-install`___ _`[OPTION]`_...

Setup Cluster Management Toolkit for Kubernetes.

## Global Options:
  __`--no-dependencies`__
Do not install dependencies  

  __`--no-fallback`__
Do not fallback to Python packages from PIP  
If a distribution package cannot be found
cmt-install will, by default, install packages
using PIP.
This option can be used to disable that behaviour.

  __`--pip-proxy`__ __PROXY__
Proxy to use for PIP  
HTTPS proxy to use if fallback packages
are installed from PIP. Format:
_[user:passwd@]proxy:port_

  __`--verbose`__
Be more verbose  

  __`-Y`__
Do not ask for confirmation  

  
### `help|--help`
#### Display this help and exit
  
  __`--format`__ __FORMAT__
  Output the help as _FORMAT_ instead  
  Valid formats are:
  _default_, _markdown_

### `version|--version`
#### Output version information and exit
  
