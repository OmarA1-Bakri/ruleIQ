"""Unit tests for api.utils.retry."""

import pytest

from api.utils.retry import (
    RetryConfig,
    RetryExhaustedError,
    RetryManager,
    retry,
    retry_async,
    retry_sync,
)


class TestRetryManager:
    def test_calculate_delay_without_jitter_respects_cap(self):
        manager = RetryManager(
            RetryConfig(base_delay=2.0, max_delay=5.0, exponential_base=3.0, jitter=False)
        )

        assert manager.calculate_delay(1) == 2.0
        assert manager.calculate_delay(2) == 5.0

    def test_calculate_delay_with_jitter_uses_random_offset(self, monkeypatch: pytest.MonkeyPatch):
        manager = RetryManager(RetryConfig(base_delay=4.0, exponential_base=2.0, jitter=True))
        calls: list[tuple[float, float]] = []

        def fake_uniform(lower: float, upper: float) -> float:
            calls.append((lower, upper))
            return upper

        monkeypatch.setattr("api.utils.retry.random.uniform", fake_uniform)

        assert manager.calculate_delay(1) == 5.0
        assert calls == [(-1.0, 1.0)]

    def test_should_retry_only_for_configured_exceptions(self):
        manager = RetryManager(RetryConfig(max_attempts=3, exceptions=(ValueError,)))

        assert manager.should_retry(ValueError("retry"), 1) is True
        assert manager.should_retry(RuntimeError("stop"), 1) is False
        assert manager.should_retry(ValueError("done"), 3) is False

    def test_execute_sync_returns_immediately_on_success(self):
        manager = RetryManager(RetryConfig())

        def succeed() -> str:
            return "ok"

        assert manager.execute_sync(succeed) == "ok"

    def test_execute_sync_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        callback_calls: list[tuple[int, str, float]] = []
        sleep_delays: list[float] = []
        attempts = {"count": 0}

        def on_retry(attempt: int, error: Exception, delay: float) -> None:
            callback_calls.append((attempt, str(error), delay))

        manager = RetryManager(
            RetryConfig(max_attempts=3, base_delay=0.25, jitter=False, on_retry=on_retry)
        )
        monkeypatch.setattr("api.utils.retry.time.sleep", sleep_delays.append)

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError(f"fail-{attempts['count']}")
            return "done"

        assert manager.execute_sync(flaky) == "done"
        assert sleep_delays == [0.25, 0.5]
        assert callback_calls == [(1, "fail-1", 0.25), (2, "fail-2", 0.5)]

    def test_execute_sync_callback_errors_are_suppressed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        attempts = {"count": 0}

        def broken_callback(attempt: int, error: Exception, delay: float) -> None:
            raise RuntimeError("callback failed")

        manager = RetryManager(
            RetryConfig(max_attempts=2, base_delay=0.1, jitter=False, on_retry=broken_callback)
        )
        monkeypatch.setattr("api.utils.retry.time.sleep", lambda _: None)

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("first failure")
            return "ok"

        with caplog.at_level("WARNING"):
            assert manager.execute_sync(flaky) == "ok"

        assert "Retry callback failed: callback failed" in caplog.text

    def test_execute_sync_raises_original_non_retryable_exception(self):
        manager = RetryManager(RetryConfig(max_attempts=3, exceptions=(ValueError,)))

        with pytest.raises(RuntimeError, match="boom"):
            manager.execute_sync(lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    def test_execute_sync_raises_retry_exhausted(self, monkeypatch: pytest.MonkeyPatch):
        manager = RetryManager(RetryConfig(max_attempts=2, base_delay=0.1, jitter=False))
        monkeypatch.setattr("api.utils.retry.time.sleep", lambda _: None)

        with pytest.raises(RetryExhaustedError) as exc_info:
            manager.execute_sync(lambda: (_ for _ in ()).throw(ValueError("still failing")))

        assert exc_info.value.attempts == 2
        assert isinstance(exc_info.value.last_exception, ValueError)

    @pytest.mark.asyncio
    async def test_execute_async_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        callback_calls: list[tuple[int, str, float]] = []
        sleep_delays: list[float] = []
        attempts = {"count": 0}

        async def on_retry(attempt: int, error: Exception, delay: float) -> None:
            callback_calls.append((attempt, str(error), delay))

        async def fake_sleep(delay: float) -> None:
            sleep_delays.append(delay)

        manager = RetryManager(
            RetryConfig(max_attempts=3, base_delay=0.5, jitter=False, on_retry=on_retry)
        )
        monkeypatch.setattr("api.utils.retry.asyncio.sleep", fake_sleep)

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError(f"async-fail-{attempts['count']}")
            return "async-ok"

        assert await manager.execute_async(flaky) == "async-ok"
        assert sleep_delays == [0.5, 1.0]
        assert callback_calls == [(1, "async-fail-1", 0.5), (2, "async-fail-2", 1.0)]

    @pytest.mark.asyncio
    async def test_execute_async_callback_errors_are_suppressed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        attempts = {"count": 0}

        async def broken_callback(attempt: int, error: Exception, delay: float) -> None:
            raise RuntimeError("async callback failed")

        async def fake_sleep(delay: float) -> None:
            return None

        manager = RetryManager(
            RetryConfig(max_attempts=2, base_delay=0.2, jitter=False, on_retry=broken_callback)
        )
        monkeypatch.setattr("api.utils.retry.asyncio.sleep", fake_sleep)

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("async failure")
            return "ok"

        with caplog.at_level("WARNING"):
            assert await manager.execute_async(flaky) == "ok"

        assert "Retry callback failed: async callback failed" in caplog.text

    @pytest.mark.asyncio
    async def test_execute_async_raises_retry_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        manager = RetryManager(RetryConfig(max_attempts=2, base_delay=0.1, jitter=False))

        async def fake_sleep(delay: float) -> None:
            return None

        async def always_fail() -> str:
            raise ValueError("async fail")

        monkeypatch.setattr("api.utils.retry.asyncio.sleep", fake_sleep)

        with pytest.raises(RetryExhaustedError) as exc_info:
            await manager.execute_async(always_fail)

        assert exc_info.value.attempts == 2


class TestRetryDecorator:
    def test_retry_wraps_sync_function(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("api.utils.retry.time.sleep", lambda _: None)
        attempts = {"count": 0}

        @retry(max_attempts=2, base_delay=0.1, jitter=False)
        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("temporary")
            return "wrapped"

        assert flaky() == "wrapped"
        assert flaky.__name__ == "flaky"

    @pytest.mark.asyncio
    async def test_retry_wraps_async_function(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_sleep(delay: float) -> None:
            return None

        monkeypatch.setattr("api.utils.retry.asyncio.sleep", fake_sleep)
        attempts = {"count": 0}

        @retry(max_attempts=2, base_delay=0.1, jitter=False)
        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("temporary")
            return "wrapped-async"

        assert await flaky() == "wrapped-async"
        assert flaky.__name__ == "flaky"


class TestRetryHelpers:
    @pytest.mark.asyncio
    async def test_retry_async_helper_uses_manager(self, monkeypatch: pytest.MonkeyPatch):
        async def fake_sleep(delay: float) -> None:
            return None

        monkeypatch.setattr("api.utils.retry.asyncio.sleep", fake_sleep)
        attempts = {"count": 0}

        async def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("first")
            return "done"

        result = await retry_async(flaky, RetryConfig(max_attempts=2, base_delay=0.1, jitter=False))
        assert result == "done"

    def test_retry_sync_helper_uses_manager(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("api.utils.retry.time.sleep", lambda _: None)
        attempts = {"count": 0}

        def flaky() -> str:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ValueError("first")
            return "done"

        result = retry_sync(flaky, RetryConfig(max_attempts=2, base_delay=0.1, jitter=False))
        assert result == "done"
