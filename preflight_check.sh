#!/bin/bash
# preflight_check.sh
# Run this before deploying. Catches the mistakes that are easy to make
# and annoying to debug on a live server instead of locally.
#
# Usage: ./preflight_check.sh

set -uo pipefail
FAILED=0

pass() { echo "✅ $1"; }
fail() { echo "❌ $1"; FAILED=1; }
warn() { echo "⚠️  $1"; }

echo "=== IPL Live Score — Pre-deploy check ==="
echo ""

# 1. All tests pass
echo "Running test suite..."
if python3 -m unittest discover -p "test_*.py" > /tmp/preflight_tests.log 2>&1; then
    pass "All unit tests pass"
else
    fail "Tests are failing — fix these before deploying:"
    tail -20 /tmp/preflight_tests.log
fi

# 2. All files compile
echo ""
echo "Checking syntax..."
if python3 -m py_compile *.py 2>/tmp/preflight_compile.log; then
    pass "All Python files compile"
else
    fail "Syntax errors found:"
    cat /tmp/preflight_compile.log
fi

# 3. No placeholder API key committed
echo ""
if grep -rq "PUT_YOUR_API_KEY_HERE" config.py 2>/dev/null; then
    warn "config.py still has the placeholder key — that's fine, it means you're using the CRICKET_API_KEY env var correctly (don't hardcode a real key in config.py)"
fi
if grep -rE "^[A-Za-z0-9_-]{20,}$" .env 2>/dev/null | grep -qv "^#"; then
    fail ".env file exists with what looks like a real key in it — make sure .env is in .gitignore and was never committed"
fi

# 4. .gitignore covers the sensitive/generated stuff
echo ""
for pattern in ".env" "*.db" "__pycache__"; do
    if grep -q -- "$pattern" .gitignore 2>/dev/null; then
        pass ".gitignore excludes $pattern"
    else
        fail ".gitignore is missing '$pattern' — add it before pushing"
    fi
done

# 5. Required deployment files exist
echo ""
for f in Procfile requirements.txt api.py frontend/index.html; do
    if [ -f "$f" ]; then
        pass "$f exists"
    else
        fail "$f is missing"
    fi
done

# 6. requirements.txt has what api.py needs
echo ""
if grep -q "fastapi" requirements.txt && grep -q "uvicorn" requirements.txt; then
    pass "requirements.txt includes fastapi + uvicorn"
else
    fail "requirements.txt is missing fastapi or uvicorn"
fi

# 7. No CRICKET_API_KEY hardcoded anywhere outside config.py's default fallback
echo ""
if grep -rn "CRICKET_API_KEY" --include="*.py" . | grep -v "config.py" | grep -vq "os.environ"; then
    warn "Double check no file other than config.py references a raw API key"
else
    pass "API key only referenced via config.py / env vars"
fi

echo ""
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
    echo "✅ All checks passed — ready to deploy."
else
    echo "❌ Fix the ❌ items above before deploying."
    exit 1
fi
