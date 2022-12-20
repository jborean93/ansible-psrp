# Copyright (c) 2022 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = """
author: jborean93
name: psrp_winrm
short_description: Run tasks on a WinRM connected PowerShell process
description:
- Runs commands or put/fetch on a target via a WinRM PSRP connection.
requirements:
- pypsrp>=1.0.0 (Python library)
options:
  hostname:
    description:
    - The hostname or IP address of the remote host.
    default: inventory_hostname
    type: str
    vars:
    - name: inventory_hostname
    - name: ansible_host
    - name: ansible_psrp2_winrm_host
  remote_user:
    description:
    - The username to log in as.
    type: str
    vars:
    - name: ansible_user
    - name: ansible_psrp2_winrm_user
  remote_password:
    description:
    - The password for the C(remote_user).
    type: str
    vars:
    - name: ansible_password
    - name: ansible_psrp2_winrm_password
  port:
    description:
    - The WinRM port to connect to.
    - Defaults to C(5985) if I(use_tls) is not true else C(5986).
    type: int
    vars:
    - name: ansible_port
    - name: ansible_psrp2_winrm_port
  use_tls:
    description:
    - Connect over HTTPS and not HTTP
    - Will change the port to C(5986) if not set.
    default: false
    type: bool
    vars:
    - name: ansible_psrp2_use_tls
  path:
    description:
    - The URI path to connect to.
    default: wsman
    type: str
    vars:
    - name: ansible_psrp2_winrm_path
  auth:
    description:
    - The authentication protocol to use for authentication.
    default: negotiate
    type: str
    choices:
    - basic
    - certificate
    - negotiate
    - kerberos
    - ntlm
    - credssp
    vars:
    - name: ansible_psrp2_winrm_auth
  cert_validation:
    description:
    - Controls the certificate validation behaviour.
    - Set to C(ignore) to disable validation.
    default: validate
    type: str
    choices:
    - ignore
    - validate
    vars:
    - name: ansible_psrp2_winrm_cert_validation
"""

from ._psrp_base import PSRPBaseConnection, psrp


class Connection(PSRPBaseConnection):
    transport = "jborean93.psrp.psrp_wsman"

    def _get_connection_info(self) -> psrp.ConnectionInfo:
        hostname = self.get_option("hostname")
        remote_user = self.get_option("remote_user")
        remote_pass = self.get_option("remote_password")
        use_tls = self.get_option("use_tls")
        port = self.get_option("port")
        if port is None:
            port = 5986 if use_tls else 5985

        path = self.get_option("path")
        auth = self.get_option("auth")
        cert_validation = self.get_option("cert_validation")
        return psrp.WSManInfo(
            hostname,
            scheme="https" if use_tls else "http",
            port=port,
            path=path,
            verify=cert_validation != "ignore",
            auth=auth,
            username=remote_user,
            password=remote_pass,
        )
