$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path "docs/disabled_workflows" | Out-Null
$keep = @("weekly-production.yml", "weekly-production.yaml", "aq26-hostinger-ssh-preflight.yml", "aq26-hostinger-ssh-preflight.yaml")
Get-ChildItem ".github/workflows" -File -Include *.yml,*.yaml | ForEach-Object {
  if ($keep -contains $_.Name) {
    Write-Host "KEEP $($_.FullName)"
  } else {
    $dest = Join-Path "docs/disabled_workflows" ($_.Name + ".txt")
    Write-Host "DISABLE $($_.FullName) -> $dest"
    git mv $_.FullName $dest 2>$null
    if ($LASTEXITCODE -ne 0) { Move-Item -Force $_.FullName $dest }
  }
}
