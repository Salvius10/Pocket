# Windows stand-in for `make`: ./make.ps1 <target>   (same targets as the Makefile)
param([Parameter(Mandatory = $true, Position = 0)][string]$Target, [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest)
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $PSScriptRoot
try { uv run python scripts/tasks.py $Target @Rest; exit $LASTEXITCODE } finally { Pop-Location }
