"""Windows PowerShell 5.1 regressions. Never register tasks or use the live port/database."""
from datetime import datetime
import http.client
import http.server
import importlib.util
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
LAUNCHER = "start_production_waitress.ps1"
DEFINITION = "production_waitress_task_definition.ps1"
INSTALLER = "install_waitress_task.ps1"
UNINSTALLER = "uninstall_production_waitress_task.ps1"
HEALTH = "check_production_health.ps1"


def powershell(path, *args):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "RemoteSigned",
         "-File", str(path), *args],
        cwd=os.environ["SystemRoot"], capture_output=True, text=True,
        errors="replace", timeout=45,
        env=dict(os.environ, DB_NAME="delisky_bi_dev", DJANGO_SETTINGS_MODULE="config.settings.development"),
    )


def ps_literal(path):
    return "'" + str(path).replace("'", "''") + "'"


class SourceContract(unittest.TestCase):
    def test_launch_contract(self):
        source = (SCRIPTS / LAUNCHER).read_text()
        self.assertIn(r'Join-Path $Project ".venv\Scripts\python.exe"', source)
        self.assertNotIn("waitress-serve.exe", source)
        self.assertIn("$startInfo.FileName = $Python", source)
        self.assertIn("$startInfo.UseShellExecute = $false", source)
        for operation in ("Start-Process", "Start-Job", "Stop-Process", ".Kill("):
            self.assertNotIn(operation, source)
        self.assertIn("$maxRecoveryAttempts = 10", source)
        self.assertIn("$recoveryDelaySeconds = 15", source)
        self.assertIn("$stableRuntimeSeconds = 300", source)
        command = source.split("$startInfo.Arguments = @(", 1)[1].split(") -join", 1)[0]
        self.assertIn("'-m', 'waitress'", command)
        for arg in ('--listen=$Listen', '--threads=4', '--trusted-proxy=127.0.0.1',
                    '--trusted-proxy-headers=x-forwarded-proto', 'config.wsgi:application'):
            self.assertIn('"' + arg + '"', command)
        self.assertIn('[ValidateSet("127.0.0.1:8080")]', source)


@unittest.skipUnless(os.name == "nt", "Windows PowerShell launcher")
class WindowsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="delisky task ", dir=os.environ.get("DELISKY_TEST_TEMP"))
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()
        self.scripts = self.project / "scripts"
        self.scripts.mkdir()

    def write(self, name, content):
        path = self.scripts / name
        path.write_text(content, encoding="utf-8-sig")
        return path

    def make_launcher(self, *, short_stable_threshold=False, port=None):
        git = self.write("git.ps1", """
if ($args -contains 'branch') { if (Test-Path wrongbranch) { 'dev' } else { 'main' } }
if ($args -contains 'status' -and (Test-Path dirty)) { ' M changed' }
if ($args -contains 'rev-parse') {
    if ($args -contains 'HEAD' -and (Test-Path behind)) { 'other' } else { 'same' }
}
exit 0
""")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(self.project / ".venv")],
                       check=True, capture_output=True)
        self.write("verify_static_manifest.py", """
from pathlib import Path
raise SystemExit(4 if Path('staticfail').exists() else 0)
""")
        (self.project / "manage.py").write_text("""
from pathlib import Path
import os, sys
assert sys.argv[1:] == ['check', '--settings=config.settings.production']
assert os.environ['DB_NAME'] == 'delisky_bi'
assert os.environ['DJANGO_SETTINGS_MODULE'] == 'config.settings.production'
raise SystemExit(5 if Path('checkfail').exists() else 0)
""")
        # A native Python module exercises the actual CreateProcess / WaitForExit path.
        # It never imports Django, opens a socket or accesses the real task.
        (self.project / "waitress.py").write_text("""
from pathlib import Path
import os, sys, time
assert sys.argv[1:] == ['--listen=127.0.0.1:8080', '--threads=4', '--trusted-proxy=127.0.0.1',
                       '--trusted-proxy-headers=x-forwarded-proto', 'config.wsgi:application']
history = Path('child-started')
with history.open('a') as f:
    print(os.getpid(), file=f)
if Path('hardcrash').exists():
    Path('hardcrash').unlink()
    os.kill(os.getpid(), -1)
if Path('recover').exists():
    Path('occupied').touch()
if Path('stable').exists() and len(history.read_text().splitlines()) == 2:
    time.sleep(2.2)
raise SystemExit(17 if Path('crash').exists() else 0)
""")
        source = (SCRIPTS / LAUNCHER).read_text().replace(
            r'"C:\Program Files\Git\cmd\git.exe"', ps_literal(git)
        )
        if port is None:
            source = source.replace(
                '[Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()',
                '@(if (Test-Path occupied) { [Net.IPEndPoint]::new([Net.IPAddress]::Loopback,8080) })',
            )
        else:
            self.assertNotEqual(port, 8080)
            source = source.replace("8080", str(port))
        # Shorten time in the test copy only. Production policy has no environment overrides.
        for original, fixture in [('$recoveryDelaySeconds = 15', '$recoveryDelaySeconds = 1'),
                                  ('$maxRecoveryAttempts = 10', '$maxRecoveryAttempts = 2'),
                                  ('$stableRuntimeSeconds = 300', '$stableRuntimeSeconds = 2')]:
            self.assertIn(original, source)
            source = source.replace(original, fixture)
        return self.write(LAUNCHER, source)

    def test_guards_and_exit_codes(self):
        launcher = self.make_launcher()
        for marker, reason in [
            ("wrongbranch", "PRODUCTION_BRANCH_GUARD_FAILED"),
            ("dirty", "PRODUCTION_WORKING_TREE_NOT_CLEAN"),
            ("behind", "PRODUCTION_HEAD_GUARD_FAILED"),
            ("staticfail", "PRODUCTION_STATIC_MANIFEST_GUARD_FAILED"),
            ("checkfail", "PRODUCTION_DJANGO_CHECK_FAILED"),
            ("occupied", "WAITRESS_PORT_IN_USE"),
        ]:
            with self.subTest(marker=marker):
                flag = self.project / marker
                flag.touch()
                result = powershell(launcher)
                flag.unlink()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(reason, result.stdout)
                self.assertFalse((self.project / "child-started").exists())
                self.assertNotIn("RECOVERY_ATTEMPT=", result.stdout)

    def test_zero_and_nonzero_retries_are_delayed_and_bounded(self):
        launcher = self.make_launcher()
        for marker, code in [("zero", 0), ("crash", 17)]:
            with self.subTest(marker=marker):
                (self.project / marker).touch()
                result = powershell(launcher)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(result.stdout.count(f"WAITRESS_EXIT_CODE={code} WAITRESS_EXIT_UNEXPECTED=True"), 3)
                self.assertIn("RECOVERY_BUDGET_EXHAUSTED", result.stdout)
                self.assertEqual(re.findall(r"RECOVERY_ATTEMPT=(\d+) RECOVERY_DELAY_SECONDS=1", result.stdout), ["1", "2"])
                self.assertEqual(result.stdout.count("STATIC_MANIFEST_GUARD=PASS"), 1)
                self.assertEqual(result.stdout.count("DJANGO_CHECK=PASS"), 1)
                starts = re.findall(r"CHILD_START_TIMESTAMP=(\S+)", result.stdout)
                ends = re.findall(r"CHILD_EXIT_TIMESTAMP=(\S+)", result.stdout)
                self.assertEqual(len(starts), 3)
                self.assertEqual(len(ends), 3)
                for start, end in zip(starts[1:], ends):
                    gap = datetime.fromisoformat(start) - datetime.fromisoformat(end)
                    self.assertGreaterEqual(gap.total_seconds(), 0.9)
                log = (self.project / "logs/production-waitress.log").read_text(encoding="utf-8-sig")
                self.assertIn("STOP_TIMESTAMP=", log)

    def test_native_child_termination_recovers_then_port_collision_stops(self):
        launcher = self.make_launcher()
        (self.project / "hardcrash").touch()
        (self.project / "recover").touch()
        result = powershell(launcher)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("WAITRESS_EXIT_CODE=-1", result.stdout)
        self.assertIn("RECOVERY_START_ATTEMPT=1", result.stdout)
        self.assertIn("WAITRESS_PORT_IN_USE", result.stdout)
        pids = (self.project / "child-started").read_text().splitlines()
        self.assertEqual(len(pids), 2)
        self.assertNotEqual(*pids)
        self.assertEqual(result.stdout.count("SUPERVISOR_PID="), 1)

    @unittest.skipUnless(importlib.util.find_spec("waitress"), "project Waitress dependency required")
    def test_real_waitress_serves_http_again_after_child_crash(self):
        import waitress
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        launcher = self.make_launcher(port=port)
        (self.project / "waitress.py").unlink()
        shutil.copytree(Path(waitress.__file__).parent, self.project / ".venv/Lib/site-packages/waitress")
        config = self.project / "config"
        config.mkdir()
        (config / "__init__.py").touch()
        (config / "wsgi.py").write_text("""
import os, threading, time
from pathlib import Path
def controlled_crash():
    # Wait for the test to receive HTTP from this worker. Always bound its lifetime.
    stop = Path('end-' + str(os.getpid()))
    deadline = time.monotonic() + 10
    while not stop.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    os.kill(os.getpid(), -1)
threading.Thread(target=controlled_crash, daemon=True).start()
def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [str(os.getpid()).encode('ascii')]
""")
        with subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
                               "RemoteSigned", "-File", str(launcher)], cwd=self.project,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as supervisor:
            workers = []
            deadline = time.monotonic() + 40
            while supervisor.poll() is None and time.monotonic() < deadline:
                request = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                try:
                    request.request("GET", "/")
                    response = request.getresponse()
                    if response.status == 200:
                        worker = int(response.read())
                        if worker not in workers:
                            workers.append(worker)
                            (self.project / f"end-{worker}").touch()
                except (OSError, http.client.HTTPException):
                    pass  # A short outage while the previous child exits is expected.
                finally:
                    request.close()
                time.sleep(0.1)
            output = supervisor.communicate(timeout=15)[0].decode(errors="replace")
        self.assertEqual(len(workers), 3, output)
        self.assertEqual(output.count("WAITRESS_EXIT_CODE=-1"), 3, output)
        self.assertEqual(output.count("SUPERVISOR_PID="), 1)
        self.assertIn("RECOVERY_BUDGET_EXHAUSTED", output)
        self.assertEqual(supervisor.returncode, 1)

    def test_stable_runtime_restores_retry_budget(self):
        launcher = self.make_launcher(short_stable_threshold=True)
        (self.project / "stable").touch()
        result = powershell(launcher)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("RECOVERY_BUDGET_RESET=True"), 1)
        self.assertEqual(re.findall(r"RECOVERY_ATTEMPT=(\d+) RECOVERY_DELAY_SECONDS", result.stdout), ["1", "1", "2"])
        self.assertIn("RECOVERY_BUDGET_EXHAUSTED", result.stdout)

    def test_task_configuration_and_ownership(self):
        shutil.copy(SCRIPTS / DEFINITION, self.scripts)
        source = (SCRIPTS / INSTALLER).read_text()
        functions = source[source.index("function Get-AccountSid"):source.index("$task = Get-WaitressTask")]
        script = self.write("test-task.ps1", ". $PSScriptRoot/" + DEFINITION + "\n" + functions + """
$ErrorActionPreference='Stop'
$ExpectedSid='S-1-5-21-100-100-100-1001'
$task=[pscustomobject]@{
 Description=$TaskDescription
 Actions=@([pscustomobject]@{Execute=$PowerShell;Arguments=$LauncherArguments;WorkingDirectory=$Project})
 Principal=[pscustomobject]@{UserId=$ExpectedSid;LogonType='S4U';RunLevel='Limited'}
 Triggers=@([pscustomobject]@{Enabled=$true;CimClass=[pscustomobject]@{CimClassName='MSFT_TaskBootTrigger'};Delay='PT30S'})
 Settings=[pscustomobject]@{Enabled=$true;StartWhenAvailable=$true;MultipleInstances='IgnoreNew';RestartCount=10;RestartInterval='PT1M';ExecutionTimeLimit='PT0S';DisallowStartIfOnBatteries=$false;StopIfGoingOnBatteries=$false}
}
if (-not (Test-TaskConfiguration $task)) { throw 'Rejected correct task' }
foreach ($p in $task.Settings.psobject.Properties) {
 $old=$p.Value
 $p.Value=if ($old -is [bool]) { -not $old } else { 'invalid' }
 if (Test-TaskConfiguration $task) { throw "Accepted drift: $($p.Name)" }
 $p.Value=$old
}
$task.Principal.UserId='S-1-5-18'
if (Test-TaskConfiguration $task) { throw 'Accepted SYSTEM' }
$task.Description='unrelated task'
if (Test-ManagedWaitressTask $task -AllowLegacy) { throw 'Accepted collision' }
""")
        result = powershell(script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        removal = (SCRIPTS / UNINSTALLER).read_text()
        self.assertLess(removal.index("Test-ManagedWaitressTask"), removal.index("Unregister-ScheduledTask"))
        self.assertIn("Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName", removal)
        self.assertNotIn("Remove-Item", removal)
        self.assertIn("New-ScheduledTaskTrigger -AtStartup", source)
        self.assertIn("if (-not $task -or -not (Test-TaskConfiguration $task))", source)

    def test_health_script_only_observes_state(self):
        source = (SCRIPTS / HEALTH).read_text()
        self.assertIn("$request.Method = 'HEAD'", source)
        self.assertIn("--no-optional-locks", source)
        for operation in ("Start-ScheduledTask", "Stop-ScheduledTask", "Register-ScheduledTask",
                          "Stop-Process", "Start-Process", "Set-Content", "Remove-Item"):
            self.assertNotIn(operation, source)

    def test_health_http_contract(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_HEAD(self):
                valid = (self.headers.get("Host") == "app.delisky-dz.com"
                         and self.headers.get("X-Forwarded-Proto") == "https")
                self.send_response(302 if valid else 400)
                self.send_header("Location", self.path)
                self.end_headers()

            def log_message(self, *args):
                pass

        with http.server.HTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                source = (SCRIPTS / HEALTH).read_text()
                function = source[source.index("function Get-HttpResult"):source.index("function Get-GitValue")]
                url = f"http://127.0.0.1:{server.server_port}"
                script = self.write("http.ps1", "$ErrorActionPreference='Stop'\n" + function + f"""
$actual=Get-HttpResult '{url}/login/' -Origin
Write-Host "LOCAL=$actual"
if ($actual -ne 'PASS') {{ exit 1 }}
if ((Get-HttpResult '{url}/wrong' -Origin) -notlike 'FAIL*') {{ exit 2 }}
if ((Get-HttpResult '{url}/login/') -notlike 'FAIL*') {{ exit 3 }}
""")
                result = powershell(script)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            finally:
                server.shutdown()
                thread.join()


if __name__ == "__main__":
    unittest.main()
