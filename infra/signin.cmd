@echo off
rem Signs this laptop in to Google Cloud and Firebase. Each step opens a browser: choose the Google
rem account that owns the billing account. This file creates and deploys nothing.
rem Run it by double-clicking, or from a terminal. It needs a real console (firebase asks one question).
set "PATH=%USERPROFILE%\dev\google-cloud-sdk\bin;%USERPROFILE%\dev\firebase-tools\node_modules\.bin;%PATH%"

echo Step 1 of 2: Google Cloud sign-in
call gcloud auth login
if errorlevel 1 goto failed

echo.
echo Step 2 of 2: Firebase sign-in (use the same Google account)
call firebase login
if errorlevel 1 goto failed

echo.
echo Signed in to both. Go back to Claude and say "signed in".
pause
exit /b 0

:failed
echo.
echo Sign-in did not finish. Nothing was changed. You can run this file again.
pause
exit /b 1
