"""Windows PowerShell 5.1 regressions. Never register tasks or use the live port/database."""
import http.server
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
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
        command = source.split("& $Python -m waitress", 1)[1]
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

    def test_guards_and_exit_codes(self):
        git = self.write("git.ps1", """
if ($args -contains 'branch') { if (Test-Path wrongbranch) { 'dev' } else { 'main' } }
if ($args -contains 'status' -and (Test-Path dirty)) { ' M changed' }
if ($args -contains 'rev-parse') {
    if ($args -contains 'HEAD' -and (Test-Path behind)) { 'other' } else { 'same' }
}
exit 0
""")
        runtime = self.write("runtime.ps1", f"""
if ((Get-Location).Path -ne {ps_literal(self.project)}) {{ exit 71 }}
if ($env:DB_NAME -ne 'delisky_bi' -or $env:DJANGO_SETTINGS_MODULE -ne 'config.settings.production') {{ exit 72 }}
if ($args[0] -like '*verify_static_manifest.py' -and (Test-Path staticfail)) {{ exit 4 }}
if ($args -contains 'check' -and (Test-Path checkfail)) {{ exit 5 }}
if ($args -contains 'config.wsgi:application') {{
    if ($args[0] -ne '-m' -or $args[1] -ne 'waitress') {{ exit 73 }}
    'started' | Set-Content child-started
    if (Test-Path crash) {{ exit 17 }}
}}
exit 0
""")
        self.write("verify_static_manifest.py", "")
        source = (SCRIPTS / LAUNCHER).read_text().replace(
            r'Join-Path $Project ".venv\Scripts\python.exe"', ps_literal(runtime)
        ).replace(r'"C:\Program Files\Git\cmd\git.exe"', ps_literal(git))
        source = source.replace(
            '[Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()',
            '@(if (Test-Path occupied) { [Net.IPEndPoint]::new([Net.IPAddress]::Loopback,8080) })',
        )
        launcher = self.write(LAUNCHER, source)
        log = self.project / "logs/production-waitress.log"
        for marker, reason, exitcode in [
            ("wrongbranch", "PRODUCTION_BRANCH_GUARD_FAILED", 1),
            ("dirty", "PRODUCTION_WORKING_TREE_NOT_CLEAN", 1),
            ("behind", "PRODUCTION_HEAD_GUARD_FAILED", 1),
            ("staticfail", "PRODUCTION_STATIC_MANIFEST_GUARD_FAILED", 1),
            ("checkfail", "PRODUCTION_DJANGO_CHECK_FAILED", 1),
            ("occupied", "WAITRESS_PORT_IN_USE", 1),
            ("crash", "WAITRESS_EXIT_CODE=17", 17),
            ("zero", "WAITRESS_EXIT_CODE=0", 1),
        ]:
            with self.subTest(marker=marker):
                flag = self.project / marker
                flag.touch()
                result = powershell(launcher)
                flag.unlink()
                self.assertEqual(result.returncode, exitcode, result.stdout + result.stderr)
                self.assertIn(reason, result.stdout)
                self.assertIn("STOP_TIMESTAMP=", log.read_text(encoding="utf-8-sig"))
                started = self.project / "child-started"
                self.assertEqual(started.exists(), marker in ("crash", "zero"))
                started.unlink(missing_ok=True)

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
