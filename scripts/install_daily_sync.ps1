# Register a limited, current-user task at 00:00 UTC; never stores passwords.
$ErrorActionPreference = 'Stop'
$syncRoot = Split-Path -Parent $PSScriptRoot
$syncPython = Join-Path $syncRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $syncPython)) { throw 'Create the project virtual environment first.' }
$syncName = 'RemitVista-CMSDaily'
$syncExisting = Get-ScheduledTask -TaskName $syncName -ErrorAction SilentlyContinue
if ($syncExisting -and ($syncExisting.Actions.Execute -ne $syncPython)) { throw 'Existing task has another owner/configuration; preserving it.' }
$syncAction = New-ScheduledTaskAction -Execute $syncPython -Argument '-m services.worker.daily_sync_worker --once' -WorkingDirectory $syncRoot
$syncTrigger = New-ScheduledTaskTrigger -Daily -At '00:00'
$syncTrigger.StartBoundary = [DateTime]::UtcNow.Date.AddDays(1).ToString("yyyy-MM-dd'T'00:00:00'Z'")
$syncUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$syncPrincipal = New-ScheduledTaskPrincipal -UserId $syncUser -LogonType Interactive -RunLevel Limited
$syncSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $syncName -Action $syncAction -Trigger $syncTrigger -Principal $syncPrincipal -Settings $syncSettings -Description 'Public CMS policy metadata refresh; requires the user to be logged in.' -Force | Out-Null
Get-ScheduledTask -TaskName $syncName | Select-Object TaskName, State
