# Start backend
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command cd backend; .\venv\Scripts\activate; uvicorn main:app --host 0.0.0.0 --port 8000"

# Start frontend
Start-Process -NoNewWindow -FilePath "powershell.exe" -ArgumentList "-Command cd frontend; npm run dev"

Write-Host "Services started! Backend on :8000, Frontend on :5173"
