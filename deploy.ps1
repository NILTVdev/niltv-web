# Deploy the NILTV web build to Amplify Hosting (manual deploy, no git needed).
# Usage:
#   pwsh -File deploy.ps1                            # dev (sandbox), tree as-is
#   pwsh -File deploy.ps1 -Env prod -Yes             # prod: staged + env-transformed
#   pwsh -File deploy.ps1 -Env prod -Yes -ProdFills  # after the poster-fill
#                                                    # crops are copied to the prod bucket
#   pwsh -File deploy.ps1 -Env prod -Check           # CI: stage, generate, sweep, guards,
#                                                    # no upload (site-ci.yml runs this on PRs)
# (-Branch is accepted as an alias for -Env.) Runs under Windows PowerShell 5.1
# on a workstation and under PowerShell 7 on the Linux runners in CI.
#
# After a real deploy the script verifies the live site: build.json must carry
# this commit and the channels page its 63 marquee cards. A deploy that
# uploads but serves the wrong build fails here instead of going unnoticed.
#
# dev:  https://dev.dkdfgvugisb3v.amplifyapp.com     (dev content stack)
# prod: https://prod.dkdfgvugisb3v.amplifyapp.com    (prod content stack,
#        canonicals declare https://niltv.com)
#
# PROD PIPELINE: the tree stays dev-flavored; prod deploys stage a copy,
# regenerate watch/channel pages + sitemap/robots/llms against the PROD API,
# sweep every baked dev reference to the prod CDN + niltv.com, swap in the
# prod config.js, prune the dev-only pages (vote, athletes, partners), and
# guard that zero dev references ship.
param(
  [ValidateSet("dev","prod")][Alias("Branch")][string]$Env = "dev",
  [switch]$Yes,
  [switch]$ProdFills,
  [switch]$Check
)

$ErrorActionPreference = "Stop"
# Native exit codes are checked by hand below; PowerShell 7 must not turn
# them into terminating errors (robocopy returns 1 on a successful copy).
$PSNativeCommandUseErrorActionPreference = $false
$appId  = "dkdfgvugisb3v"
$branch = $Env
$region = "us-east-1"
# script-rooted so a release clone deploys ITS tree, not the working copy
$src    = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

# The OS-specific bits (tree copy, zip, curl, temp dir) live here; everything
# else is the same on both platforms.
$onWindows = ($env:OS -eq "Windows_NT")
$tmpDir  = if ($env:TEMP) { $env:TEMP } else { [IO.Path]::GetTempPath() }
$curl    = if ($onWindows) { "curl.exe" } else { "curl" }
$devNull = if ($onWindows) { "NUL" } else { "/dev/null" }
function Copy-Tree($from, $to) {
  if ($onWindows) { robocopy $from $to /E /NFL /NDL /NJH /NJS /NP | Out-Null }
  else {
    New-Item -ItemType Directory -Path $to -Force | Out-Null
    Copy-Item -Path (Join-Path $from "*") -Destination $to -Recurse -Force
  }
}
function New-Zip($zipPath, $dir, $items) {
  $present = @($items | Where-Object { Test-Path (Join-Path $dir $_) })
  if ($onWindows) { tar.exe -a -cf $zipPath -C $dir $present }
  else {
    Push-Location $dir
    try {
      zip -q -r -X $zipPath $present | Out-Null
      if ($LASTEXITCODE -ne 0) { throw "zip failed ($LASTEXITCODE)" }
    } finally { Pop-Location }
  }
}

$prodOrigin = "https://niltv.com"
$prodCdn    = "https://dr60jt51m7xh2.cloudfront.net"
# niltv-prod-web: the CDK-managed website client. SRP-only, no secret, no
# OAuth surface, user-existence errors hidden. Output WebClientId of the
# niltv-prod-foundation stack.
$prodPool   = "us-east-1_CUAGPsaru"
$prodClient = "866nashv1brjs96apc17r1gfa"

# PID-unique zip so two concurrent deploys can never clobber each other
# mid-upload
$zip = Join-Path $tmpDir "niltv-web-deploy-$Env-$PID.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }

# Shared page set. Prod additionally excludes vote/athletes/partners (dev-only).
# concepts/ is an ignored scratch dir: dev ships it only when present.
$pages = @("index.html","not-found.html","sitemap.xml","robots.txt","llms.txt","build.json","assets",
           "channels","featured","about","watch","legal","nilstar","competitions",
           "payouts","contact","favicon.ico","athlete-signup","payments")

if ($Env -eq "prod") {
  # ---- guards: a prod artifact must be reproducible from the RELEASE branch.
  # main -> dev is the working flow; prod ships only the signed-off release
  # branch, promoted with:  git push origin main:release   (fast-forward only).
  if (-not $Check) {
    $dirty = git -C $src status --porcelain
    if ($dirty) { Write-Error "prod deploy refused: uncommitted changes in the tree.`n$dirty"; exit 1 }
    git -C $src fetch origin release --quiet
    $head = git -C $src rev-parse HEAD; $remote = git -C $src rev-parse origin/release
    if ($head -ne $remote) { Write-Error "prod deploy refused: HEAD ($head) != origin/release ($remote).`nProd builds only from the signed-off release branch. After sign-off:`n  git push origin main:release ; git checkout release  (or run from the release clone)"; exit 1 }
    if (-not $Yes) { Write-Error "prod deploy needs the -Yes switch (deliberate-action gate)."; exit 1 }
  }
  $sha = git -C $src rev-parse --short HEAD

  # ---- stage a copy of the deployable tree ----
  # PID-unique so concurrent sessions can never clobber each other's stage
  $stage = Join-Path $tmpDir ("niltv-prod-stage-" + $PID)
  if (Test-Path $stage) { [IO.Directory]::Delete($stage, $true) }
  New-Item -ItemType Directory -Path $stage | Out-Null
  foreach ($it in ($pages + @("config.js"))) {
    $from = Join-Path $src $it
    if (-not (Test-Path $from)) { continue }  # sitemap/robots/llms are regenerated below
    if ((Get-Item $from).PSIsContainer) {
      Copy-Tree $from (Join-Path $stage $it)
    } else {
      Copy-Item $from (Join-Path $stage $it)
    }
  }
  # the generator needs the scripts (chrome template included) beside the pages
  Copy-Tree (Join-Path $src "scripts") (Join-Path $stage "scripts")

  # ---- regenerate against the PROD API, prod identity ----
  Write-Host "Generating pages from the PROD API..."
  $env:NILTV_ENV = "prod"; $env:NILTV_API = $prodCdn; $env:NILTV_ORIGIN = $prodOrigin
  $env:NILTV_BUILD_COMMIT = $sha; $env:NILTV_BUILD_BRANCH = "release"
  node (Join-Path $stage "scripts/build-pages.mjs")
  $gen = $LASTEXITCODE
  Remove-Item Env:NILTV_ENV, Env:NILTV_API, Env:NILTV_ORIGIN, Env:NILTV_BUILD_COMMIT, Env:NILTV_BUILD_BRANCH -ErrorAction SilentlyContinue
  if ($gen -ne 0) { Write-Error "prod page generation failed"; exit 1 }

  # ---- sweep every baked dev reference to the prod identity ----
  $fills = if ($ProdFills) { "on" } else { "off" }
  python (Join-Path $stage "scripts/deploy-sweep.py") $stage $prodOrigin $prodCdn --fills $fills
  if ($LASTEXITCODE -ne 0) { Write-Error "prod sweep failed its guard"; exit 1 }

  # ---- prod runtime config ----
  @"
// NILTV web - environment config (PROD, written by deploy.ps1 -Env prod).
window.NILTV_CONFIG = {
  apiBase: "$prodCdn",
  payoutsApi: "https://wf2ggl2nk4hmcppi5rz7rwekzu0ojpzb.lambda-url.us-east-1.on.aws/",
  applicationsApi: "https://api.niltv.com/api/applications/",
  cognito: {
    userPoolId: "$prodPool",
    clientId: "$prodClient",
  },
};
"@ | Out-File -FilePath (Join-Path $stage "config.js") -Encoding utf8

  # generator inputs never ship
  [IO.Directory]::Delete((Join-Path $stage "scripts"), $true)

  # ---- final guards on the artifact ----
  $chmq = (Select-String -Path (Join-Path $stage "channels/index.html") -Pattern 'class="chmq-card"' -AllMatches).Matches.Count
  if ($chmq -ne 63) { Write-Error "staged channels page has $chmq chmq cards (expected 63)"; exit 1 }
  $leak = Get-ChildItem $stage -Recurse -Include *.html,*.xml,*.txt,*.js | Select-String -Pattern "dkdfgvugisb3v|d1nm1d2txb83wa" -List
  if ($leak) { Write-Error "prod artifact still references the dev environment:`n$($leak.Path -join "`n")"; exit 1 }

  if ($Check) {
    [IO.Directory]::Delete($stage, $true)
    Write-Host "prod check passed (commit $sha): staged, generated, swept, 63 marquee cards, zero dev references. Nothing uploaded."
    exit 0
  }
  New-Zip $zip $stage ($pages + @("config.js"))
  Write-Host "Zipped $((Get-Item $zip).Length) bytes for 'prod' (commit $sha)"
} else {
  # ---- dev: the tree IS the artifact ----
  Write-Host "Generating pages from the API..."
  $sha = git -C $src rev-parse --short HEAD
  $env:NILTV_BUILD_COMMIT = $sha; $env:NILTV_BUILD_BRANCH = (git -C $src rev-parse --abbrev-ref HEAD)
  node (Join-Path $src "scripts/build-pages.mjs")
  $gen = $LASTEXITCODE
  Remove-Item Env:NILTV_BUILD_COMMIT, Env:NILTV_BUILD_BRANCH -ErrorAction SilentlyContinue
  if ($gen -ne 0) { Write-Error "page generation failed"; exit 1 }
  $chmq = (Select-String -Path (Join-Path $src "channels/index.html") -Pattern 'class="chmq-card"' -AllMatches).Matches.Count
  if ($chmq -ne 63) { Write-Error "channels/index.html has $chmq chmq-card imgs (expected 63) - stale copy, aborting"; exit 1 }
  if ($Check) { Write-Host "dev check passed (commit $sha): pages generated, 63 marquee cards. Athlete build skipped (private data)."; exit 0 }
  # athlete pages are generated from the PRIVATE data folder (never in git):
  # regenerate them so the dev artifact carries the current records + photos.
  # --require makes a missing private folder a hard failure.
  Write-Host "Building athlete pages from private data..."
  python (Join-Path $src "scripts/builders/build-athletes.py") --require
  if ($LASTEXITCODE -ne 0) { Write-Error "dev deploy refused: athlete pages could not be built. The private data folder is missing - set NILTV_PRIVATE_DATA or create ../private-data/niltv-web beside the repo (see DEVELOPING.md)."; exit 1 }
  # athlete-signup and payments ship to prod too (they are in $pages); the dev
  # tree just adds the dev-only pages here.
  $items = $pages + @("config.js","vote","athletes","partners")
  if (Test-Path (Join-Path $src "concepts")) { $items += "concepts" }   # drafts copied in from the private folder, never committed
  New-Zip $zip $src $items
  Write-Host "Zipped $((Get-Item $zip).Length) bytes for 'dev' (commit $sha)"
}

$depRaw = aws amplify create-deployment --region $region --app-id $appId --branch-name $branch --output json 2>&1
if ($LASTEXITCODE -ne 0) {
  if ("$depRaw" -match "job\(deployment\) (\d+) was not finished") {
    Write-Error ("create-deployment blocked by stuck PENDING job $($Matches[1]). Run:`n" +
      "  aws amplify stop-job --app-id $appId --branch-name $branch --job-id $($Matches[1]) --region $region`nthen redeploy.")
  } else { Write-Error "create-deployment failed: $depRaw" }
  exit 1
}
$dep = $depRaw | ConvertFrom-Json
if (-not $dep.zipUploadUrl) { Write-Error "create-deployment returned no upload url (job $($dep.jobId))"; exit 1 }
Write-Host "Created job $($dep.jobId) on branch '$branch', uploading..."

# a failed PUT strands a PENDING job that blocks ALL later deploys - retry,
# and on final failure stop our own job so the queue stays clean.
# curl, not Invoke-WebRequest: Invoke-WebRequest can return without error
# while the object never lands (Amplify then fails with MissingBuildArtifacts).
# curl reports the real HTTP status of the PUT.
$uploaded = $false
for ($try = 1; $try -le 3 -and -not $uploaded; $try++) {
  $code = & $curl -sS -o $devNull -w "%{http_code}" -X PUT -T $zip -H "Content-Type: application/zip" $dep.zipUploadUrl
  if ($code -eq "200") { $uploaded = $true }
  else {
    Write-Host "  upload attempt $try failed: HTTP $code"
    Start-Sleep -Seconds (3 * $try)
  }
}
if (-not $uploaded) {
  aws amplify stop-job --region $region --app-id $appId --branch-name $branch --job-id $dep.jobId | Out-Null
  Write-Error "upload failed 3x; job $($dep.jobId) stopped so the branch is not blocked. Retry the deploy."
  exit 1
}

aws amplify start-deployment --region $region --app-id $appId --branch-name $branch --job-id $dep.jobId | Out-Null

do {
    Start-Sleep -Seconds 4
    $status = (aws amplify get-job --region $region --app-id $appId --branch-name $branch --job-id $dep.jobId --output json | ConvertFrom-Json).job.summary.status
    Write-Host "  status: $status"
} while ($status -eq "PENDING" -or $status -eq "RUNNING")

Add-Content -Path (Join-Path $src "deploy-log.txt") -Value "$(Get-Date -Format s) env=$Env job=$($dep.jobId) sha=$sha status=$status"

if ($status -ne "SUCCEED") { Write-Error "Deployment finished with status $status"; exit 1 }
$site = "https://$branch.$appId.amplifyapp.com"
Write-Host "Deployed: $site"

# ---- verify the live site serves THIS build ----
# dev sits behind Amplify basic auth; the credentials live on the branch.
# NILTV_DEV_BASIC (base64 user:password) overrides the branch value, which
# may not unlock the site. A wrong credential must read as "unverified", not
# as a failed deploy.
$headers = @{}
$basic = if ($env:NILTV_DEV_BASIC) { $env:NILTV_DEV_BASIC } else {
  aws amplify get-branch --region $region --app-id $appId --branch-name $branch --query "branch.basicAuthCredentials" --output text }
if ($basic -and $basic -ne "None") { $headers["Authorization"] = "Basic $basic" }
$live = $null; $unauthorized = $false
for ($try = 1; $try -le 8; $try++) {
  try {
    $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $live = (Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri "$site/build.json?t=$stamp" -TimeoutSec 20).Content | ConvertFrom-Json
    if ($live.commit -eq $sha) { break }
    Write-Host "  live build is $($live.commit), waiting for $sha ($try/8)"
  } catch {
    if ($_.Exception.Message -match "\(401\)") { $unauthorized = $true; break }
    Write-Host "  build.json not readable yet ($try/8): $($_.Exception.Message)"
  }
  Start-Sleep -Seconds 10
}
if ($unauthorized) {
  Write-Warning "Deployed (job $($dep.jobId), commit $sha) but NOT verified: $site answers 401 with the stored basic-auth value. Set NILTV_DEV_BASIC to base64(user:password) that opens the dev site and rerun with -Check to verify."
  exit 0
}
if (-not $live -or $live.commit -ne $sha) { Write-Error "verify failed: $site/build.json does not carry commit $sha (live: $($live.commit))"; exit 1 }
$chan = (Invoke-WebRequest -UseBasicParsing -Headers $headers -Uri "$site/channels/" -TimeoutSec 20).Content
$liveCards = ([regex]::Matches($chan, 'class="chmq-card"')).Count
if ($liveCards -ne 63) { Write-Error "verify failed: live channels page has $liveCards marquee cards (expected 63)"; exit 1 }
Write-Host "Verified: $site serves commit $sha ($($live.env), built $($live.builtAt)), 63 marquee cards."
