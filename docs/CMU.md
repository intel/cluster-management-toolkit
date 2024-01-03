# CMU

`cmu` is the Curses-based UI for __CMT__.
It provides information in a way that is similar to the output from `kubectl get`,
`kubectl describe`, but better suitable for interactive use, including object relations.
It also provides logs with formatting, and the ability to run Ansible playbooks
on cluster nodes as well as hosts that are part of the Ansible inventory but not the cluster.

## Starting `cmu`

![View list](images/View_list.png)

Simply type `cmu` to open the list of available views
(in a complex cluster configuration using APIs that __CMT__ knows about this list can be fairly extensive).

To open cmu directly in a view for a specific API resource, use `cmu po`/`cmu pod`, `cmu ns`/`cmu namespace`, etc.
You can also shortcut into an object if you know its name; for instance `cmu ns kube-system` or even directly
into a container of a pod `cmu po etcd:` (or if the pod contains more than one container, `cmu po etcd:etcd`).
Object names will be matched by prefix. If the match is not unique the cursor will move to the first match,
but no object will be opened. Meaning that in a cluster will multiple nodes `cmu po kube-proxy` would move
to the first kube-proxy pod, but since each node has a pod named _kube-proxy_ it will not open that object.

To open the view list you can press `F2`. This will show views for all resources available when `cmu` was
started. If APIs have been added or removed after `cmu` started the menu can be refreshed using `F3`.

## Getting help

To show context specific help for a particular view,
press either `F1` or `[shift] + H`. `F12` will display the "About" box.

## Read-only mode

To disable all operations that modifies the cluster you can use `cmu --read-only`.
This will prevent you from, for instance, deleting or rescaling resources,
executing some playbooks, editing resources, etc.

## Cluster overview

![Cluster overview](images/Cluster_overview.png)

To get a quick overview of the health of your cluster, you can open the _Cluster Overview_,
either from the view list, or from the command line via `cmu co`.

In the Cluster overview you'll see a list of all nodes and pods highlighted based on their health.
You'll also get the CPU and memory usage of the control plane. From here you can navigate to the nodes or clusters.

## List view

![List view](images/List_view.png)

The list of objects for a particular API-resource can be seen in the list view.
Here you can filter, sort, search, and in some case tag and perform actions
(for instance scaling resources or deleting them).
As always `F1` or `[shift] + H` will show what commands are available.

Some list views that contain a lot of information may be too wide for if you have a monitor with low horizontal resolution.
To accomodate for this you can press `[Shift] + W` to cycle between different view configurations.

## Edit object

![Edit object](images/Edit_object.png)

If an object is mutable you can press `e` on a highlighted object in the list view to edit it.
This will open up an editor and let you edit the object. Upon exiting the editor the object will be validated,
and if the changes are acceptable the object will be updated by the API-server.

## View raw resource

![View object](images/View_object.png)

You can view the YAML representation of an object by pressing `Y` in the either the List view or the Info view.
Note that the screenshot also gives an example of the optional line-wrapping functionality that can be used when logs have extremely long lines.

## Info view

![Info view](images/Info_view.png)

The info for a particular object can be accessed by pressing `[Enter]` in the list view.
The information available in the info view is highly context specific; in some cases there is an abundance of information,
in other cases hardly anything is visible (sometimes because the view in question is a work in progress,
at other times because there's no useful way to visualise it apart from the raw YAML output).

## Log view

![Log view](images/Log_view.png)

Some resources, notably Pods, ConfigMaps, and Logs, have a log view.

## Ansible playbooks

![Ansible playbooks](images/Ansible_playbooks.png)

The Node view and the Inventory view allow you to run Ansible playbooks on selected hosts/nodes.
Based on the type of playbook they may be limited to either the Node view or the Inventory view.
Playbooks that potentially modify data will not be visible if `cmu` is running in read-only mode.

## Colours, Theming, and Colour Vision Deficiency

`cmu` makes heavy use of colours to highlight system status. To allow for terminals with limited colours `cmu` has support for theming.
The default theme aims to fit most users, but there is a theme in development that aims to assist people with colour vision deficiency.
This support is far from complete (it mainly affects the cluster overview for the time being, by displaying node and pod status with symbols
instead of just colour).

Add/edit `.cmt/cmt.yaml.d/Global.yaml` as follows to set a custom theme:

```
Global:
  theme: "cvd.yaml"
```
