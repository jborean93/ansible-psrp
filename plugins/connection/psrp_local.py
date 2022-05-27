# Copyright (c) 2022 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

DOCUMENTATION = """
author: jborean93
name: psrp_local
short_description: Run tasks on a local PowerShell process
description:
- Runs commands or put/fetch on a target via a local PSRP process.
- This is useful when running Ansible in WSL to target the local Windows host
  without having to set up WinRM.
requirements:
- pypsrp>=1.0.0 (Python library)
options:
  executable:
    description:
    - The PowerShell executable to invoke for local tasks.
    - The default is I(powershell) which is the Windows PowerShell executable
      on Windows hosts.
    - Can be set to I(pwsh) to target PowerShell 6+ or if using a non-Windows
      host.
    # default: powershell.exe
    default: pwsh
    type: str
    vars:
    - name: ansible_psrp_local_executable
  arguments:
    description:
    - The arguments to use when starting the C(executable).
    - This should not need to be changed in most circumstances.
    default: ['-NoProfile', '-NoLogo', '-ServerMode']
    type: list
    elements: str
    vars:
    - name: ansible_psrp_local_executable
"""

from ._psrp_base import PSRPBaseConnection, psrp


class Connection(PSRPBaseConnection):
    transport = "jborean93.psrp.psrp_local"

    def _get_connection_info(self) -> psrp.ConnectionInfo:
        return psrp.ProcessInfo(
            executable=self.get_option("executable"),
            arguments=self.get_option("arguments"),
        )
