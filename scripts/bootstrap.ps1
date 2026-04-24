Write-Host "[bootstrap] Configurando entorno Python..."
python setup.py

Write-Host "[bootstrap] Instalando frontend..."
Push-Location frontend
npm install
Pop-Location

Write-Host "[bootstrap] Listo."

