$ErrorActionPreference = 'Stop'

& .\.venv\Scripts\ruff.exe check .
& .\.venv\Scripts\ruff.exe format --check .
& .\.venv\Scripts\python.exe -m mypy apps packages scripts tests
& .\.venv\Scripts\python.exe -m pytest --cov=apps --cov=packages
& npm.cmd --prefix apps/web run build
& npm.cmd --prefix apps/web audit --audit-level=high

