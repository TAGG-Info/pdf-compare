@echo off
setlocal enableextensions
REM ============================================================
REM  Installation LOCALE de pdf-compare (deploiement depuis serveur)
REM  - Ce script peut etre lance directement depuis un partage reseau.
REM  - Il copie le projet sur le poste, puis l'installe en local.
REM  - Le poste devient autonome : plus aucune dependance au serveur.
REM  Prerequis : Python 3.9+ deja installe sur le poste.
REM ============================================================

echo.
echo ========================================
echo   Installation de pdf-compare v1.1.0
echo ========================================
echo.

REM --- Dossier source = emplacement de CE script (gere UNC et lecteur mappe)
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

REM --- Dossiers de destination LOCAUX (profil utilisateur, pas de droits admin requis)
set "DEST=%LOCALAPPDATA%\pdf-compare"
set "APP=%DEST%\app"
set "VENV=%DEST%\venv"

echo Source : %SRC%
echo Cible  : %DEST%
echo.

REM --- [1/5] Verifier Python
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERREUR] Python n'est pas installe ou pas dans le PATH
        echo.
        echo Veuillez installer Python 3.9 ou superieur depuis :
        echo https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    set "PYTHON_CMD=py"
) else (
    set "PYTHON_CMD=python"
)
echo [1/5] Python detecte
%PYTHON_CMD% --version

REM --- Verifier la version minimale requise (Python 3.9+)
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if errorlevel 1 (
    echo [ERREUR] Python 3.9 ou superieur est requis ^(voir version ci-dessus^).
    echo Veuillez mettre a jour Python : https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo.

REM --- [2/5] Copier le projet en local (exclut .git, venv, caches...)
echo [2/5] Copie du projet vers le poste...
robocopy "%SRC%" "%APP%" /E /NFL /NDL /NJH /NJS /NP /XD ".git" "venv" ".venv" "__pycache__" "build" "dist" ".vscode" /XF "*.pyc" >nul
set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
    echo [ERREUR] Echec de la copie des fichiers ^(robocopy code %RC%^)
    pause
    exit /b 1
)
echo [OK] Fichiers copies dans %APP%
echo.

REM --- [3/5] Creer un environnement Python local dedie
echo [3/5] Creation de l'environnement Python local...
if not exist "%VENV%\Scripts\python.exe" (
    %PYTHON_CMD% -m venv "%VENV%"
    if errorlevel 1 (
        echo [ERREUR] Echec de la creation de l'environnement virtuel
        pause
        exit /b 1
    )
)
echo [OK] Environnement pret
echo.

REM --- [4/5] Installer dependances + pdf-compare (installation REELLE, sans mode -e)
echo [4/5] Installation des dependances et de pdf-compare...
echo Cela peut prendre quelques minutes...
echo.
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
"%VENV%\Scripts\python.exe" -m pip install -r "%APP%\requirements.txt"
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation des dependances
    pause
    exit /b 1
)
"%VENV%\Scripts\python.exe" -m pip install "%APP%"
if errorlevel 1 (
    echo [ERREUR] Echec de l'installation de pdf-compare
    pause
    exit /b 1
)
echo.
echo [OK] Installation terminee
echo.

REM --- [5/5] Rendre 'pdf-compare' disponible (PATH utilisateur, sans droits admin)
echo [5/5] Ajout de pdf-compare au PATH utilisateur...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d='%VENV%\Scripts'; $p=[Environment]::GetEnvironmentVariable('Path','User'); if(-not $p){$p=''}; if($p.Split(';') -notcontains $d){[Environment]::SetEnvironmentVariable('Path',(($p.TrimEnd(';')+';'+$d).Trim(';')),'User'); '[OK] PATH utilisateur mis a jour'} else {'[OK] PATH deja configure'}"
echo.

REM --- Verification
echo Verification de l'installation...
"%VENV%\Scripts\pdf-compare.exe" --version
echo.

echo ========================================
echo   Installation terminee avec succes !
echo ========================================
echo.
echo IMPORTANT : ouvrez un NOUVEAU terminal pour que la
echo commande 'pdf-compare' soit reconnue (rafraichissement du PATH).
echo.
echo Utilisation :
echo   pdf-compare fichier1.pdf fichier2.pdf
echo.
echo pdf-compare est installe localement dans :
echo   %DEST%
echo Le poste est desormais autonome (independant du serveur).
echo.
pause
endlocal
