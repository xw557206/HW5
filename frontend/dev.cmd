@echo off
cd /d "C:\hw5-frontend"
if "%PORT%"=="" set PORT=5173
"C:\Program Files\nodejs\node.exe" "C:\hw5-frontend\node_modules\vite\bin\vite.js" --port %PORT%
