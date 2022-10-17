# TODO
## All
* When running either ikt or iku, check whether .ssh/id_ecdsa.pub is in authorized_keys
  in .ikt/ansible/inventory.yaml; if not, add it
* Rewrite command_parser to treat options passed before a command as global,
  and to allow options interspersed with arguments
* Add `--dry-run` support for more commands

## iku
* Try to find other things we can simplify in the views
* Make themearrays treat lists as tuples; this would make it possible to remove special casing for views
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
* Pass cluster_name to `kubeadm init` using ClusterConfiguration + clusterName
* prepare_passwordless_ansible won't work on localhost; we're not passing the password,
  and the password might not be the same on the remote system and the local system anyway
* Add `pre-upgrade-check` that checks whether relevant config files (notably containerd)
  are compatible with new settings. Also check whether the cluster currently uses
  any APIs that are deprecated, and any deployments that are known to be unsupported on
  newer versions of Kubernetes. Config-checks needs to check all nodes, not just
  the control plane.
* troubleshoot:
  * Check that the config-files as installed/created at install time by iktadm/ikt
    are in sync with what's on the machines in the cluster at present, and if not,
    warn about the difference.
    The differences *may* be intentional, so we cannot indiscriminately overwrite them,
    but the user should at least be aware of the differences (we could even show a diff
    if `--verbose` is passed) and provide a helpful message about what playbook to
    run to update the files.

logparser:
* Rewrite key_value; the parser is overly complex at the moment; it needs to be simplified
  and have fewer special cases
* Line too long shouldn't override severity
  | Ideally max line length should be a.) configurable, b.) trigger line splitting into remnants
* We cannot replace tabs with spaces in the logparser; we need to do it in the printers instead;
  this way we know the real line length (due to facility etc. we might not have the same starting point
  for every line, so expanding tabs into spaces won't work properly)

kubernetes_helper:
* Replace playbooks/drain_node.yaml with cordon_node() + post evictions (or delete if PodDisruptionBudget causes issues)
  for all non-DaemonSet pods
