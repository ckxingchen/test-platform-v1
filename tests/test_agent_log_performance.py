import sys
import time

from agent.service.task_runner import LOG_FLUSH_LINES, LOG_FLUSH_SECONDS
from agent.utils.runtime import ProcessRunner


def test_log_batch_matches_platform_limit():
    assert LOG_FLUSH_LINES == 500
    assert LOG_FLUSH_SECONDS <= 0.25


def test_python_runner_output_is_unbuffered(tmp_path):
    runner = ProcessRunner()
    started = time.monotonic()
    runner.start(
        [sys.executable, "-c", "import time; print('ready'); time.sleep(1)"],
        tmp_path,
    )
    try:
        assert next(runner.iter_lines()).strip() == "ready"
        assert time.monotonic() - started < 0.7
    finally:
        runner.kill()
