<# Switch Contoso Retail report between dark and light themes.
Usage: ./Switch-ContosoTheme.ps1 -Mode Light|Dark
Mechanism: swap theme JSON content, remap hardcoded visual colors via
pbir (bijective map, verified disjoint), one per-visual exception for
the GM target reference label, then validate. Round-trip is byte-identical.
#>
param([Parameter(Mandatory = $true)][ValidateSet("Light", "Dark")][string]$Mode)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$liveTheme = Join-Path $root "Contoso Retail.Report\StaticResources\RegisteredResources\ContosoExecutive-4f18b4d2.json"
$srcTheme = Join-Path $root ("themes\ContosoExecutive.{0}.json" -f $Mode.ToUpper())
$report = Join-Path $root "Contoso Retail.Report"
$gmLabel = "Contoso Retail.Report/Executive_overview.Page/cd368855f0cc75592aed.Visual.xAxisReferenceLine.id(0).dataLabelColor"
# dark -> light (verified bijective, disjoint, WCAG-checked; see .tmp/build_map.py)
$map = @(
  @("#0B1220", "#FFFFFF"), @("#111B2E", "#F3F4F6"), @("#0F172A", "#F9FAFB"),
  @("#26364D", "#E5E7EB"), @("#2B3950", "#DDE0E6"), @("#26364A", "#D1D5DB"),
  @("#111827", "#FEFEFE"), @("#F5F7FB", "#0F1626"), @("#F8FBFF", "#101828"),
  @("#F4F7FC", "#030712"), @("#E6EEF8", "#1F2A37"), @("#DCE6F2", "#243041"),
  @("#EAF2FF", "#1F2937"), @("#B7C2D4", "#4B5563"), @("#B7C5D9", "#374151"),
  @("#9AA9BD", "#52617A"), @("#7F8CA3", "#6B7280"), @("#FB7185", "#BE123C"),
  @("#FBBF24", "#D97706"), @("#34D399", "#047857"), @("#2DD4BF", "#0D9488")
)
Copy-Item $srcTheme $liveTheme -Force
# pbir color replace does not span textbox textRuns: length-preserving
# literal swap with exact-count assert (narrowest fallback, validated below).
function Swap-TextRuns([string]$fromTitle, [string]$toTitle, [string]$fromSub, [string]$toSub) {
  $n1 = 0; $n2 = 0
  $files = Get-ChildItem (Join-Path $root "Contoso Retail.Report\definition\pages") -Recurse -Filter visual.json
  foreach ($f in $files) {
    $t = Get-Content $f.FullName -Raw
    $c1 = ([regex]::Matches($t, $fromTitle)).Count; $c2 = ([regex]::Matches($t, $fromSub)).Count
    if ($c1 + $c2 -gt 0) {
      $t = $t -replace $fromTitle, $toTitle -replace $fromSub, $toSub
      Set-Content $f.FullName $t -NoNewline; $n1 += $c1; $n2 += $c2
    }
  }
  if ($n1 -ne 4 -or $n2 -ne 4) { throw "textRun count mismatch: title=$n1 subtitle=$n2" }
}
Push-Location $root
try {
  if ($Mode -eq "Light") {
    foreach ($pair in $map) {
      pbir color replace "Contoso Retail.Report" --from $pair[0] --to $pair[1] -f
      if ($LASTEXITCODE -ne 0) { throw "replace $($pair[0]) failed" }
    }
    Swap-TextRuns "#F8FBFF" "#101828" "#9AA9BD" "#52617A"
    pbir set $gmLabel --value "#92400E"
    if ($LASTEXITCODE -ne 0) { throw "gm label set failed" }
  } else {
    pbir set $gmLabel --value "#D97706"
    if ($LASTEXITCODE -ne 0) { throw "gm label revert failed" }
    Swap-TextRuns "#101828" "#F8FBFF" "#52617A" "#9AA9BD"
    foreach ($pair in $map) {
      pbir color replace "Contoso Retail.Report" --from $pair[1] --to $pair[0] -f
      if ($LASTEXITCODE -ne 0) { throw "replace $($pair[1]) failed" }
    }
  }
  pbir theme validate "Contoso Retail.Report"
  if ($LASTEXITCODE -ne 0) { throw "theme validate failed" }
  pbir validate "Contoso Retail.Report"
  if ($LASTEXITCODE -notin @(0, 1)) { throw "report validate crashed" }
} finally { Pop-Location }
Write-Output "Switched to $Mode."
