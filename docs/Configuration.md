# Configuration

_CMT_ is configured by editing files in `~/.cmt/cmt.yaml.d`.
To see some examples of what configurations are available you can refer to `~/.cmt/cmt.yaml`.

## Configuring a proxy

To use a proxy when the installer and the cluster connects to the Internet,
create a file named (for instance) `~/.cmt/cmt.yaml.d/Network.yaml` with the following content:

```
Network:
  https_proxy: "<proxy>"
  no_proxy: "<comma-separated list of addresses that shouldn't be proxied>"
```

Note that the proxy will _not_ be used for intra-cluster communication.
Also note that this proxy setting will __not__ be used by `cmt-install`,
since that program is typically responsible for creating the `~/.cmt` directory,
and thus the configuration directory cannot be relied upon to exist when running `cmt-install`.
To use a proxy with `cmt-install` you can specify the `--pip-proxy` option.
