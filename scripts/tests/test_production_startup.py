"""Isolated launcher regression: no Django, database or Scheduler side effects."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

@unittest.skipUnless(os.name == "nt", "Windows PowerShell launcher")
class LauncherTests(unittest.TestCase):
    def run_launcher(self, waitress_exit=0):
        with tempfile.TemporaryDirectory(prefix="delisky startup ", dir=os.environ.get("DELISKY_TEST_TEMP")) as directory:
            project = Path(directory) / "project with spaces"
            scripts = project / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "verify_static_manifest.py").touch()
            git = scripts / "git.ps1"
            git.write_text('''param([Parameter(ValueFromRemainingArguments=$true)]$Arguments)
if ($Arguments -contains 'branch') { 'main' }
elseif ($Arguments -contains 'rev-parse') { 'same-sha' }
exit 0
''')
            mock = scripts / "runtime.ps1"
            mock.write_text(f'''if ((Get-Location).Path -ne '{project}') {{ exit 71 }}
if ($env:DB_NAME -ne 'delisky_bi') {{ exit 72 }}
if ($env:DJANGO_SETTINGS_MODULE -ne 'config.settings.production') {{ exit 73 }}
if ($args -contains 'config.wsgi:application') {{ exit {waitress_exit} }}
exit 0
''')
            source = (ROOT / "scripts/start_production_waitress.ps1").read_text()
            source = source.replace('Join-Path $Project ".venv\\Scripts\\waitress-serve.exe"', f'"{mock}"')
            source = source.replace('Join-Path $Project ".venv\\Scripts\\python.exe"', f'"{mock}"')
            source = source.replace('"C:\\Program Files\\Git\\cmd\\git.exe"', f'"{git}"')
            launcher = scripts / "start_production_waitress.ps1"
            launcher.write_text(source)
            env = dict(os.environ, DB_NAME="delisky_bi_dev", DJANGO_SETTINGS_MODULE="config.settings.development")
            result = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(launcher)], cwd=os.environ["SystemRoot"], env=env, text=True, capture_output=True)
            log = (project / "logs/production-waitress.log").read_text(encoding="utf-8-sig")
            return result, log

    def test_foreign_cwd_and_inherited_dev_are_corrected(self):
        result, log = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DB_SAFETY=PASS", log)
        self.assertIn("WAITRESS_EXIT_CODE=0", log)

    def test_task_configuration_rejects_drift(self):
        source = (ROOT / "scripts/install_waitress_task.ps1").read_text(encoding="utf-8-sig")
        function = source[source.index("function Test-TaskConfiguration"):source.index("function Test-IsAdministrator")]
        script = function + """
$PowerShell='powershell.exe'; $LauncherArguments='expected'; $Project='project'
$task=[pscustomobject]@{
 Actions=@([pscustomobject]@{Execute=$PowerShell;Arguments=$LauncherArguments;WorkingDirectory=$Project})
 Principal=[pscustomobject]@{UserId='SYSTEM';LogonType='ServiceAccount'}
 Triggers=@([pscustomobject]@{CimClass=[pscustomobject]@{CimClassName='MSFT_TaskBootTrigger'};Delay='PT30S'})
 Settings=[pscustomobject]@{Enabled=$true;StartWhenAvailable=$true;MultipleInstances='IgnoreNew';RestartCount=3;RestartInterval='PT1M';ExecutionTimeLimit='PT0S';DisallowStartIfOnBatteries=$false;StopIfGoingOnBatteries=$false}
}
if (-not (Test-TaskConfiguration $task)) { exit 1 }
foreach ($field in @('Enabled','StartWhenAvailable','MultipleInstances','RestartCount','RestartInterval','ExecutionTimeLimit','DisallowStartIfOnBatteries','StopIfGoingOnBatteries')) {
 $old=$task.Settings.$field
 $task.Settings.$field=if ($old -is [bool]) { -not $old } elseif ($old -is [int]) { 99 } else { 'invalid' }
 if (Test-TaskConfiguration $task) { throw "Accepted drift: $field" }
 $task.Settings.$field=$old
}
$task.Principal.UserId='other'
if (Test-TaskConfiguration $task) { exit 2 }
exit 0
"""
        result = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_waitress_failure_reaches_scheduler(self):
        result, log = self.run_launcher(17)
        self.assertEqual(result.returncode, 17, result.stdout + result.stderr)
        self.assertIn("WAITRESS_EXIT_CODE=17", log)

if __name__ == "__main__":
    unittest.main()
