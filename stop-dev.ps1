param(
    [switch]$CleanNodeModules
)

$ErrorActionPreference = 'Stop'

$Root = Join-Path $HOME '.openclaw\workspace\order_system_v2'
$Frontend = Join-Path $Root 'frontend'

function Get-ComposeCommand {
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            docker compose version *> $null
            if ($LASTEXITCODE -eq 0) {
                return @('docker', 'compose')
            }
        } catch {}
    }

    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        return @('docker-compose')
    }

    throw 'docker / docker compose が見つかりません。'
}

function Invoke-Compose {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $compose = Get-ComposeCommand
    if ($compose.Length -eq 1) {
        & $compose[0] @Args
    } else {
        & $compose[0] $compose[1] @Args
    }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose コマンドが失敗しました: $($Args -join ' ')"
    }
}

if (-not (Test-Path $Root)) {
    throw "プロジェクトルートが見つかりません: $Root"
}
Set-Location $Root

Write-Host '==> stop docker compose services'
Invoke-Compose -Args @('down')

Write-Host '==> note'
Write-Host 'backend/frontend の PowerShell ウィンドウが残っていれば Ctrl+C で停止してください'

if ($CleanNodeModules) {
    Write-Host '==> remove frontend/node_modules'
    Remove-Item -Recurse -Force (Join-Path $Frontend 'node_modules') -ErrorAction SilentlyContinue
}

Write-Host 'stop complete'
