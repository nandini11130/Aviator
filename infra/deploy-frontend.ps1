<#
.SYNOPSIS
  Builds the Next.js frontend as a static export and deploys it to Firebase
  Hosting.

.PREREQUISITES
  - Node.js 18+
  - firebase-tools installed: npm install -g firebase-tools
  - firebase login
  - Copy .firebaserc.example to .firebaserc and set your project id.

.USAGE
  ./infra/deploy-frontend.ps1
#>
$ErrorActionPreference = "Stop"
$root = "$PSScriptRoot/.."

Push-Location "$root/frontend"
try {
  if (-not (Test-Path ".env.local")) {
    Write-Warning ".env.local not found - copy .env.local.example and set NEXT_PUBLIC_API_BASE_URL to your Cloud Run URL."
  }
  npm install
  npm run build
}
finally {
  Pop-Location
}

Push-Location $root
try {
  if (-not (Test-Path ".firebaserc")) {
    Write-Warning ".firebaserc not found - copy .firebaserc.example and set your Firebase project id."
  }
  firebase deploy --only hosting
}
finally {
  Pop-Location
}
