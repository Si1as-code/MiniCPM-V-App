# 同步 MiniCPM-V app/ 到 AutoDL 云端的配置
#
# 用法（本地 PowerShell）:
#   .\sync.ps1                     # 同步 app/ 目录
#   .\sync.ps1 -WhatIf             # 预览会同步哪些文件（不实际传输）
#
# 前提: 填写下面的连接信息

# ====== 请修改为你的 AutoDL SSH 信息 ======
$AutoDL_Host = "connect.bjb2.seetacloud.com"
$AutoDL_Port = "22720"
$AutoDL_User = "root"
$AutoDL_RemotePath = "/root/autodl-tmp/MiniCPM-V"
# =============================================

$SSH_Target = "${AutoDL_User}@${AutoDL_Host}"
$LocalAppDir = "$PSScriptRoot\app"
$RsyncAvailable = $false

# 检查 rsync 是否可用（Git Bash 自带 rsync）
try {
    $null = rsync --version 2>$null
    $RsyncAvailable = $true
} catch {
    $RsyncAvailable = $false
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " MiniCPM-V 代码同步工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  本地: $LocalAppDir" -ForegroundColor Gray
Write-Host "  远端: ${SSH_Target}:${AutoDL_RemotePath}/app" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path $LocalAppDir)) {
    Write-Host "  错误: 本地 app/ 目录不存在" -ForegroundColor Red
    exit 1
}

if ($RsyncAvailable) {
    # 使用 rsync（增量同步，速度快，只传差异）
    Write-Host "  使用 rsync 同步..." -ForegroundColor Green
    $rsyncArgs = @(
        "-avz",
        "--delete",           # 删除远端多余的文件
        "--exclude", ".__pycache__",
        "--exclude", "*.pyc",
        "-e", "ssh -p $AutoDL_Port"
    )
    if ($WhatIf) {
        $rsyncArgs += "--dry-run"
        Write-Host "  [预览模式] 不会实际传输文件" -ForegroundColor Yellow
    }

    rsync @rsyncArgs "$LocalAppDir/" "${SSH_Target}:${AutoDL_RemotePath}/app/"
} else {
    # 回退到 scp（全量覆盖，简单但不增量）
    Write-Host "  rsync 不可用，使用 scp 同步..." -ForegroundColor Yellow
    Write-Host "  (提示: 安装 Git for Windows 可获得 rsync，同步更快)" -ForegroundColor Gray
    Write-Host ""

    scp -r -P $AutoDL_Port "$LocalAppDir" "${SSH_Target}:${AutoDL_RemotePath}/"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 同步完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  在云端运行测试:" -ForegroundColor Gray
Write-Host "    cd /root/autodl-tmp/MiniCPM-V/app" -ForegroundColor White
Write-Host "    python test_inference.py" -ForegroundColor White
Write-Host ""
