# Prod ships ONLY the signed-off release branch.
# Flow: work on main -> deploy dev -> sign-off ->
#   git push origin main:release   (fast-forward promotion)
#   powershell -File deploy-prod-from-release.ps1 [-ProdFills]
# This keeps a dedicated single-branch clone beside the repo (../webapp-release) so
# prod builds never touch (or get blocked by) the working tree.
param([switch]$ProdFills)
$ErrorActionPreference = "Stop"
$clone = Join-Path (Split-Path $PSScriptRoot -Parent) "webapp-release"

if (-not (Test-Path $clone)) {
  git clone --branch release --single-branch https://github.com/NILTVdev/niltv-web.git $clone
}
git -C $clone fetch origin release --quiet
git -C $clone reset --hard origin/release --quiet
Write-Host ("release @ " + (git -C $clone rev-parse --short HEAD))

$deployArgs = @{ Env = "prod"; Yes = $true }
if ($ProdFills) { $deployArgs["ProdFills"] = $true }
& (Join-Path $clone "deploy.ps1") @deployArgs
