import os
from pathlib import Path

# Set environment variables before any tests or project modules are imported
os.environ["ENV"] = "testing"
os.environ["DEBUG"] = "True"
os.environ["APP_NAME"] = "Test CLI Instance"

# Isolate cache writes for tests
os.environ["CACHE_DIR"] = str(Path("/tmp") / "beneat-test-cache")
