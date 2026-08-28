param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9-]{2,60}$')]
    [string]$AppName,
    [string]$ResourceGroup = "rg-campuspulse-student",
    [string]$Location = "southeastasia"
)

$ErrorActionPreference = "Stop"
$planName = "plan-campuspulse-free"
$packagePath = Join-Path $env:TEMP "campuspulse-deploy.zip"
$stagingPath = Join-Path $env:TEMP "campuspulse-deploy"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI is required. Install it from https://aka.ms/installazurecliwindows"
}

if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingPath | Out-Null

$deploymentFiles = @(
    "app.py", "ai_service.py", "requirements.txt", "startup.sh",
    "data", "templates", "static"
)
foreach ($item in $deploymentFiles) {
    Copy-Item -LiteralPath $item -Destination $stagingPath -Recurse
}
Compress-Archive -Path (Join-Path $stagingPath "*") -DestinationPath $packagePath -Force

az group create --name $ResourceGroup --location $Location --tags `
    project=CampusPulseAI environment=student-assignment cost-tier=free | Out-Null

# F1 is the shared-compute free tier. The script never falls back to a paid SKU.
az appservice plan create --name $planName --resource-group $ResourceGroup `
    --location $Location --is-linux --sku F1 | Out-Null

az webapp create --name $AppName --resource-group $ResourceGroup --plan $planName `
    --runtime "PYTHON:3.12" | Out-Null

az webapp config appsettings set --name $AppName --resource-group $ResourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true | Out-Null
az webapp config set --name $AppName --resource-group $ResourceGroup `
    --startup-file "startup.sh" --always-on false | Out-Null
az webapp deploy --name $AppName --resource-group $ResourceGroup `
    --src-path $packagePath --type zip --clean true | Out-Null

Write-Output "Deployment complete: https://$AppName.azurewebsites.net"
Write-Output "Health endpoint:    https://$AppName.azurewebsites.net/health"

