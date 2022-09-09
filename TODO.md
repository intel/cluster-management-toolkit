# TODO
## All
* When running either ikt or iku, check whether .ssh/id_ed25519.pub is in authorized_keys
  in .ikt/ansible/inventory.yaml; if not, add it

## iku
* Try to find other things we can simplify in the views
* Make themearrays treat lists as tuples; this would make it possible to remove special casing for views
* Add a passlist for all acceptable calls instead of using eval
* Maybe split all objgetters into a objgetters directory?
* Move field_templates and built-in views to views
* Modify generator_list; ideally every list element should be typed;
  this way we'd be able to use, for instance:
  [(kind, api_family), address, address, ...]
  and have the (kind, api_family) tuple formatter by that kind of parser,
  while the addresses are formatter by the address formatter,
  without having to special case various types of lists.
  We might even want the list of types be possible to generate on the fly;
  currently it can only be specified manually.
  Note: this would need quite a bit of a rewrite, but it would probably be healthy
  and hopefully cut down on the amount of special cases.
* Audit and make a list of all necessary types
* Show if we're running in read-only mode in the status bar
* config map YAML-parser should handle single-line files (optionally unfolding)
* Make generic_infogetter consistent WRT to paths:
  ["literal", ["path"], [["alternate1", "alternate2"]]]

iktinv:
* Optionally limit rebuild-inventory to a subset of clusters

iktadm:
* Add command to import kube-config (requires cluster-name--unless unique) and a path
* Pass cluster_name to kubeadm init
* prepare_passwordless_ansible won't work on localhost; we're not passing the password,
  and the password might not be the same on the remote system and the local system anyway

logparser:
* Rewrite key_value; the parser is overly complex at the moment; it needs to be simplified
  and have fewer special cases
* Line too long shouldn't override severity
  | Ideally max line length should be a.) configurable, b.) trigger line splitting into remnants
* We cannot replace tabs with spaces in the logparser; we need to do it in the printers instead;
  this way we know the real line length (due to facility etc. we might not have the same starting point
  for every line, so expanding tabs into spaces won't work properly)

kubernetes_helper:
* Replace drain_node with cordon, post evictions (or delete if PodDisruptionBudget causes issues)
  for all non-DaemonSet pods
