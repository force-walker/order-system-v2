$ErrorActionPreference = 'Stop'

$Root = Join-Path $HOME '.openclaw\workspace\order_system_v2'
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$PythonBin = Join-Path $Root '.venv\Scripts\python.exe'
$HostDatabaseUrl = 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/order_system_v2'

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

    throw 'docker / docker compose が見つかりません。Docker Desktop を確認してください。'
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

Write-Host "==> move to project root: $Root"
if (-not (Test-Path $Root)) {
    throw "プロジェクトルートが見つかりません: $Root"
}
Set-Location $Root

if (-not (Get-Command docker -ErrorAction SilentlyContinue) -and -not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    throw 'docker / docker compose が見つかりません。'
}

if (-not (Get-Command powershell -ErrorAction SilentlyContinue)) {
    throw 'powershell が見つかりません。'
}

Write-Host '==> start containers (db/redis)'
Invoke-Compose -Args @('up', '-d', 'db', 'redis')
Invoke-Compose -Args @('ps')

Write-Host '==> stop api container (host uvicorn will use 8000)'
try {
    Invoke-Compose -Args @('stop', 'api')
} catch {
    Write-Host 'api container stop skipped'
}

Write-Host '==> verify external python venv'
if (-not (Test-Path $PythonBin)) {
    throw "python が見つかりません: $PythonBin"
}

Write-Host '==> start backend (host uvicorn)'
$backendCmd = @"
Set-Location '$Backend'
`$env:DATABASE_URL = '$HostDatabaseUrl'
`$env:PYTHONPATH = '.'
& '$PythonBin' -m alembic upgrade head
if (`$LASTEXITCODE -ne 0) { Read-Host 'alembic failed'; exit `$LASTEXITCODE }
& '$PythonBin' -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Read-Host 'Press Enter to close'
"@
Start-Process powershell -ArgumentList '-NoExit', '-Command', $backendCmd | Out-Null

Write-Host '==> ensure frontend dependencies (npm ci when node_modules absent)'
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw 'npm が見つかりません。Node.js をインストールしてください。'
}
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
    Push-Location $Frontend
    npm ci
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        throw 'npm ci に失敗しました。'
    }
    Pop-Location
}

Write-Host '==> start frontend'
$frontendCmd = @"
Set-Location '$Frontend'
npm run dev -- --host 0.0.0.0 --port 5173
Read-Host 'Press Enter to close'
"@
Start-Process powershell -ArgumentList '-NoExit', '-Command', $frontendCmd | Out-Null

Write-Host ''
Write-Host 'Started'
Write-Host 'Frontend: http://localhost:5173'
Write-Host 'Backend : http://localhost:8000'
Write-Host 'Docs    : http://localhost:8000/docs'
