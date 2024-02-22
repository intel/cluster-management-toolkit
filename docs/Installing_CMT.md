# Installing CMT

If you haven't already cloned the CMT repository, first do so:

`git clone https://github.com/intel/cluster-management-toolkit.git`

## .netrc

`cmtadm` and some of the _Ansible_ playbooks perform calls
to GitHub APIs. If you are behind a proxy or end up doing a lot
of API requests you might run into GitHub's daily rate limit,
which will cause requests to fail.

If you haven't done so already you should always consider adding
a _Personal Accesss Token_ for GitHub to your `.netrc` file.

See instructions here: [Using a GitHub PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

## Without proxy

```
$ cd cluster-management-toolkit
$ ./cmt-install
```

## With proxy

```
$ cd cluster-management-toolkit
$ ./cmt-install --pip-proxy PROXY
```

Running `cmt-install` creates necessary symlinks, directories, etc.,
and installs the packages necessary to run __CMT__. Note that `cmt-install`
does not perform any cluster setup; all changes take place on your
local computer.

If you only want to use the curses-based user-interface __cmu__ you can
continue here: [CMU](CMU.md#cmu).

To create a cluster step by step, check [Setup a control plane](Setup_a_control_plane.md#setting-up-a-control-plane).

To create a cluster using a template file (_recommended_),
check [Creating a cluster using a template file](Creating_a_cluster_using_a_template_file.md#creating-a-cluster-using-a-template-file).
