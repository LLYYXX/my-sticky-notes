param(
    [string]$Python = "python",
    [string]$OutputDirectory = "release",
    [string]$Version = "",
    [string]$NsisPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools = Join-Path $Root ".build-tools"
$Publish = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory
} else {
    Join-Path $Root $OutputDirectory
}
$Stage = Join-Path $Root "build\package"
$Work = Join-Path $Root "build\pyinstaller"
$Spec = Join-Path $Root "build"
$TclRuntime = Join-Path $Root "build\tcl-runtime"
$VersionInfo = Join-Path $Work "windows-version-info.txt"
$Icon = Join-Path $Root "assets\icons\tray.ico"
$Assets = Join-Path $Root "assets"
$InstallerScript = Join-Path $Root "installer\MyStickyNotes.nsi"

if (-not $Version) {
    $VersionSource = Get-Content -LiteralPath (Join-Path $Root "sticky_notes\__init__.py") -Raw
    $VersionMatch = [regex]::Match($VersionSource, '__version__\s*=\s*["'']([^"'']+)["'']')
    if (-not $VersionMatch.Success) {
        throw "Unable to read the application version from sticky_notes\__init__.py."
    }
    $Version = $VersionMatch.Groups[1].Value
}

$NumericVersion = [regex]::Match($Version, '^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$')
if (-not $NumericVersion.Success) {
    throw "Version must use semantic versioning, for example 1.2.3."
}
$AppFileVersion = "{0}.{1}.{2}.0" -f @(
    $NumericVersion.Groups[1].Value,
    $NumericVersion.Groups[2].Value,
    $NumericVersion.Groups[3].Value
)

New-Item -ItemType Directory -Force -Path $Tools, $Publish, $Stage, $Work | Out-Null

# The publish directory is a single-product channel: keep only the current Setup.
$ExistingArtifacts = Get-ChildItem -LiteralPath $Publish -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -like "My Sticky Notes *.exe" -or
    $_.Name -like "My Sticky Notes *.zip" -or
    $_.Name -like "MyStickyNotes-*.exe" -or
    $_.Name -like "MyStickyNotes-*.zip" -or
    $_.Name -eq "SHA256SUMS.txt"
}
foreach ($Artifact in $ExistingArtifacts) {
    Remove-Item -LiteralPath $Artifact.FullName -Force
}
$LegacyPublicFolder = Join-Path $Publish "MyStickyNotes"
if (Test-Path -LiteralPath $LegacyPublicFolder) {
    Remove-Item -LiteralPath $LegacyPublicFolder -Recurse -Force
}

$BuildDependenciesReady = (
    (Test-Path -LiteralPath (Join-Path $Tools "PyInstaller\__init__.py")) -and
    (Test-Path -LiteralPath (Join-Path $Tools "PIL\__init__.py"))
)
if ($BuildDependenciesReady) {
    & $Python -c "import sys; sys.path.insert(0, sys.argv[1]); import PIL._imaging, PyInstaller" $Tools
    $BuildDependenciesReady = $LASTEXITCODE -eq 0
}
if (-not $BuildDependenciesReady) {
    & $Python -m pip install --disable-pip-version-check --ignore-requires-python --upgrade --force-reinstall --target $Tools -r (Join-Path $Root "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) { throw "Unable to install build dependencies." }
}

function Find-NsisCompiler {
    param([string]$ExplicitPath)

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) {
            throw "NSIS compiler was not found at: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $Command = Get-Command "makensis.exe" -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $CommonPaths = @(
        (Join-Path ${env:ProgramFiles(x86)} "NSIS\makensis.exe"),
        (Join-Path $env:ProgramFiles "NSIS\makensis.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
    if ($CommonPaths.Count -gt 0) {
        return $CommonPaths[0]
    }

    $Bundled = Get-ChildItem -LiteralPath $Tools -Recurse -Filter "makensis.exe" -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($Bundled) {
        return $Bundled.FullName
    }
    return $null
}

$MakeNsis = Find-NsisCompiler -ExplicitPath $NsisPath
if (-not $MakeNsis) {
    if (-not (Test-Path -LiteralPath (Join-Path $Tools "smol_nsis\__init__.py"))) {
        & $Python -m pip install --disable-pip-version-check --ignore-requires-python --target $Tools "smol-nsis==0.0.16"
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to install the NSIS compiler. Install NSIS and pass -NsisPath."
        }
    }
    $ExtractedNsis = @(& $Python (Join-Path $Root "scripts\extract_nsis.py") $Tools)
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to extract the NSIS compiler."
    }
    if ($ExtractedNsis.Count -eq 0) {
        throw "NSIS extraction did not return a compiler path."
    }
    $MakeNsis = $ExtractedNsis[-1].Trim()
}
if (-not $MakeNsis) {
    throw "NSIS was installed but makensis.exe could not be located."
}

$env:PYTHONPATH = "$Tools;$Root"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $Root "build\pyinstaller-config"
$PythonPrefix = (& $Python -c "import sys; print(sys.prefix)").Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to query the Python runtime." }
$CondaLibraryBin = Join-Path $PythonPrefix "Library\bin"
if (Test-Path -LiteralPath $CondaLibraryBin) {
    # PyInstaller does not automatically search Conda's OpenSSL DLL directory.
    $env:PATH = "$CondaLibraryBin;$env:PATH"
}
$PythonTclLibrary = (& $Python -c "import tkinter; print(tkinter.Tcl().eval('info library'))").Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to query the Tcl runtime." }
$PythonTclRoot = Split-Path -Parent $PythonTclLibrary
$PythonTkLibrary = Join-Path $PythonTclRoot "tk8.6"
if (
    -not (Test-Path -LiteralPath (Join-Path $PythonTclLibrary "init.tcl")) -or
    -not (Test-Path -LiteralPath (Join-Path $PythonTkLibrary "tk.tcl"))
) {
    throw "The selected Python runtime does not include Tcl/Tk."
}
if (Test-Path -LiteralPath $TclRuntime) {
    Remove-Item -LiteralPath $TclRuntime -Recurse -Force
}
# Tcl/Tk patch levels must match _tkinter.pyd, so never reuse another Python's cache.
New-Item -ItemType Directory -Force -Path $TclRuntime | Out-Null
Copy-Item -LiteralPath $PythonTclLibrary -Destination (Join-Path $TclRuntime "tcl8.6") -Recurse
Copy-Item -LiteralPath $PythonTkLibrary -Destination (Join-Path $TclRuntime "tk8.6") -Recurse
$env:TCL_LIBRARY = Join-Path $TclRuntime "tcl8.6"
$env:TK_LIBRARY = Join-Path $TclRuntime "tk8.6"

& $Python (Join-Path $Root "scripts\build_app_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Unable to build the application icon." }
& $Python (Join-Path $Root "scripts\build_light_icons.py")
if ($LASTEXITCODE -ne 0) { throw "Unable to build light note icons." }
& $Python (Join-Path $Root "scripts\build_settings_control_assets.py")
if ($LASTEXITCODE -ne 0) { throw "Unable to build Settings control assets." }
& $Python (Join-Path $Root "scripts\write_version_info.py") $Version $VersionInfo
if ($LASTEXITCODE -ne 0) { throw "Unable to generate Windows version metadata." }

$Common = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--icon", $Icon,
    "--version-file", $VersionInfo,
    "--add-data", "$Assets;assets",
    "--workpath", $Work,
    "--specpath", $Spec
)

$FolderBundle = Join-Path $Stage "MyStickyNotes"
& $Python -m PyInstaller @Common --distpath $Stage --onedir --name "MyStickyNotes" (Join-Path $Root "app.py")
if ($LASTEXITCODE -ne 0) { throw "Unable to build the folder bundle." }

$InstallerPath = Join-Path $Publish "My Sticky Notes Setup $Version.exe"
if (Test-Path -LiteralPath $InstallerPath) {
    Remove-Item -LiteralPath $InstallerPath -Force
}
$NsisArguments = @(
    "/V3",
    "/INPUTCHARSET", "UTF8",
    "/DAPP_VERSION=$Version",
    "/DAPP_FILE_VERSION=$AppFileVersion",
    "/DSOURCE_DIR=$FolderBundle",
    "/DOUTPUT_FILE=$InstallerPath",
    "/DAPP_ICON=$Icon",
    $InstallerScript
)
& $MakeNsis @NsisArguments
if ($LASTEXITCODE -ne 0) { throw "Unable to build the NSIS installer." }

$ChecksumsPath = Join-Path $Publish "SHA256SUMS.txt"
$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $InstallerPath
$ChecksumLine = "{0}  {1}" -f $Hash.Hash.ToLowerInvariant(), (Split-Path -Leaf $InstallerPath)
Set-Content -LiteralPath $ChecksumsPath -Value $ChecksumLine -Encoding ASCII

Write-Host "Built My Sticky Notes ${Version}:"
Write-Host $InstallerPath
Write-Host $ChecksumsPath
