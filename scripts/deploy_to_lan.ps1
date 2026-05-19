param(
    [string]$ServerIp = "192.168.137.102",
    [string]$Mode = "smb",
    [string]$RemoteShare = "projects",
    [string]$RemotePath = "ashare-quant-tool",
    [string]$Username = "",
    [string]$Password = "",
    [string]$SshRemotePath = "/opt/ashare-quant-tool"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Copy-WithRobocopy {
    $shareRoot = "\\$ServerIp\$RemoteShare"
    $target = Join-Path $shareRoot $RemotePath

    if ($Username -and $Password) {
        $securePassword = ConvertTo-SecureString $Password -AsPlainText -Force
        $credential = New-Object System.Management.Automation.PSCredential($Username, $securePassword)
        New-PSDrive -Name "LANDEPLOY" -PSProvider FileSystem -Root $shareRoot -Credential $credential -ErrorAction Stop | Out-Null
        $target = Join-Path "LANDEPLOY:\" $RemotePath
    }

    New-Item -ItemType Directory -Force -Path $target | Out-Null
    robocopy $ProjectRoot $target /MIR /XD ".git" "__pycache__" ".pytest_cache" "dist" ".venv" /XF "*.pyc"

    if (Get-PSDrive -Name "LANDEPLOY" -ErrorAction SilentlyContinue) {
        Remove-PSDrive -Name "LANDEPLOY" -Force
    }
}

function Copy-WithScp {
    if (-not $Username) {
        throw "Mode=scp 时必须提供 -Username。"
    }
    $source = Join-Path $ProjectRoot "*"
    $destination = "$Username@${ServerIp}:$SshRemotePath"
    scp -r $source $destination
}

switch ($Mode.ToLower()) {
    "smb" { Copy-WithRobocopy }
    "scp" { Copy-WithScp }
    default { throw "不支持的模式: $Mode。可选值: smb, scp" }
}
