"""브라우저 통합 테스트 실행기: python -m tools.run_browser_tests  (playwright, chromium 필요: pip install playwright; python -m playwright install chromium)"""
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-m", "browser", "tests/browser", "-q"]))
