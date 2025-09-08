@echo off
setlocal enabledelayedexpansion

echo 🐳 Docker Login Testing Workflow
echo =================================

echo 🚀 Step 1: Starting test services...
docker-compose --profile test up -d test-postgres redis

echo ⏳ Waiting for test database to be ready...
timeout /t 5 /nobreak > nul

echo 🚀 Step 2: Setting up test database and users...
cd /d "%~dp0\.."
python scripts/setup_test_users.py

if !errorlevel! neq 0 (
    echo ❌ Failed to setup test database
    goto :cleanup
)

echo 🚀 Step 3: Starting test backend service...
docker-compose --profile test up -d test-backend

echo ⏳ Waiting for test backend to be ready...
timeout /t 10 /nobreak > nul

echo 🚀 Step 4: Running login tests...
python tests/test_login.py

if !errorlevel! equ 0 (
    echo 🎉 All tests passed successfully!
) else (
    echo ❌ Tests failed!
    goto :cleanup
)

echo ✅ Testing workflow completed!
goto :end

:cleanup
echo 🧹 Cleaning up test environment...
docker-compose --profile test down
exit /b 1

:end
echo 🧹 Cleaning up test environment...
docker-compose --profile test down