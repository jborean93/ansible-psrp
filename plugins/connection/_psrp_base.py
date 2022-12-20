# Copyright (c) 2022 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

import base64
import io
import re
import typing as t

from ansible.errors import AnsibleError
from ansible.plugins.connection import ConnectionBase
from ansible.utils.display import Display


HAS_PSRP = True
PSRP_IMP_ERR = None
try:
    import psrp
    import psrpcore.types
except ImportError as err:
    HAS_PSRP = False
    PSRP_IMP_ERR = err

display = Display()


_COMMAND_PATTERN = re.compile(
    "-EncodedCommand ((?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)$"
)


class PSHost(psrp.PSHost):
    def __init__(
        self,
        ui: t.Optional[psrp.PSHostUI] = None,
    ) -> None:
        super().__init__(ui)
        self.exit_code: int = 0

    def set_should_exit(
        self,
        exit_code: int,
    ) -> None:
        self.exit_code = exit_code


class PSHostUI(psrp.PSHostUI):
    def __init__(
        self,
        raw_ui: t.Optional[psrp.PSHostRawUI] = None,
    ):
        super().__init__(raw_ui)
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def write(
        self,
        value: str,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        self.stdout.write(value)

    def write_debug_line(
        self,
        line: str,
    ) -> None:
        self.stdout.write(f"DEBUG: {line}\n")

    def write_error_line(
        self,
        line: str,
    ) -> None:
        self.stderr.write(line + "\n")

    def write_line(
        self,
        line: t.Optional[str] = None,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        self.stdout.write((line or "") + "\n")

    def write_verbose_line(
        self,
        line: str,
    ) -> None:
        self.stdout.write(f"VERBOSE: {line}\n")

    def write_warning_line(
        self,
        line: str,
    ) -> None:
        self.stdout.write(f"WARNING: {line}\n")

    def write_progress(
        self,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        pass


class PSRPBaseConnection(ConnectionBase):
    module_implementation_preferences = (".ps1", ".exe", "")
    allow_executable = False
    has_pipelining = True

    def __init__(
        self,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        self.always_pipeline_modules = True
        self.has_native_async = True
        self._shell_type = "powershell"
        self._ps_host_ui = PSHostUI()
        self._ps_host = PSHost(ui=self._ps_host_ui)
        self._runspace: t.Optional[psrp.SyncRunspacePool] = None
        self._connected = False

        super().__init__(*args, **kwargs)

    def exec_command(
        self,
        cmd: str,
        in_data: t.Optional[bytes] = None,
        sudoable: bool = True,
    ) -> t.Tuple[int, bytes, bytes]:
        input_data: t.Optional[str] = in_data.decode() if in_data else None

        runspace = self._get_runspace()
        ps = psrp.SyncPowerShell(runspace)

        if b64cmd := _COMMAND_PATTERN.search(cmd):
            script = base64.b64decode(b64cmd[1]).decode("utf-16-le")
            display.vvv(f"PSRP: EXEC {script}")
            ps.add_script(script)

            if input_data and input_data.startswith("#!"):
                # ANSIBALLZ wrapper, we need to get the interpreter and execute
                # that as the script - note this won't work as basic.py relies
                # on packages not available on Windows, once fixed we can enable
                # this path
                # script = "$input | &'%s' -" % interpreter
                # in_data = to_text(in_data)
                interpreter = input_data.splitlines()[0][2:]
                raise AnsibleError(
                    f"cannot run the interpreter '{interpreter}' on the "
                    f"{self.transport} connection plugin"
                )

        else:
            script = f"{cmd}\nexit $LASTEXITCODE"
            display.vvv(f"PSRP: EXEC {script}")
            ps.add_script(script)

        output = ps.invoke(input_data=[input_data])

        stdout: t.List[str] = []
        stderr: t.List[str] = []
        rc = self._ps_host.exit_code or (1 if ps.had_errors else 0)

        for out in output:
            stdout.append(str(out))

        if host_stdout := self._ps_host_ui.stdout.getvalue():
            stdout.append(host_stdout)

        for err in ps.streams.error:
            stderr.append(str(err))

        if host_stderr := self._ps_host_ui.stderr.getvalue():
            stderr.append(host_stderr)

        # Reset for the next invocation
        self._ps_host.exit_code = 0
        self._ps_host_ui.stdout = io.StringIO()
        self._ps_host_ui.stderr = io.StringIO()

        stdout_str = "\n".join(stdout)
        stderr_str = "\n".join(stderr)
        display.vvvvv("PSRP RC: %d" % rc)
        display.vvvvv("PSRP STDOUT: %s" % stdout_str)
        display.vvvvv("PSRP STDERR: %s" % stderr_str)

        return rc, stdout_str.encode(), stderr_str.encode()

    def put_file(
        self,
        in_path: str,
        out_path: str,
    ) -> None:
        runspace = self._get_runspace()
        psrp.copy_file(runspace, in_path, out_path)

    def fetch_file(
        self,
        in_path: str,
        out_path: str,
    ) -> None:
        runspace = self._get_runspace()
        psrp.fetch_file(runspace, in_path, out_path)

    def close(self) -> None:
        if not self._connected:
            return

        runspace = self._get_runspace()
        if runspace.state == psrpcore.types.RunspacePoolState.Opened:
            runspace.close()

        self._runspace = None
        self._connected = False

    def reset(self) -> None:
        if not self._connected:
            return

        self.close()
        self._get_runspace()

    def _connect(self) -> None:
        return None  # Work is done in _get_runspace as needed

    def _get_runspace(self) -> psrp.SyncRunspacePool:
        if not HAS_PSRP:
            raise AnsibleError(
                f"pypsrp or dependencies are not installed: {PSRP_IMP_ERR}"
            )

        if not self._runspace:
            self._runspace = psrp.SyncRunspacePool(
                self._get_connection_info(),
                host=self._ps_host,
            )
            display.vvv(f"ESTABLISHING {self.transport} CONNECTION")
            self._runspace.open()
            self._connected = True

        return self._runspace

    def _get_connection_info(self) -> psrp.ConnectionInfo:
        """Implemented by sub classes to generated the connection info."""
        raise NotImplementedError()
