## Copyright 2013-2014 Ray Holder
## Modifications copyright (C) 2020 Jiachen Yao
##
## Licensed under the Apache License, Version 2.0 (the "License");
## you may not use this file except in compliance with the License.
## You may obtain a copy of the License at
##
## http://www.apache.org/licenses/LICENSE-2.0
##
## Unless required by applicable law or agreed to in writing, software
## distributed under the License is distributed on an "AS IS" BASIS,
## WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
## See the License for the specific language governing permissions and
## limitations under the License.

from __future__ import annotations

import random
import sys
import time
import traceback
from functools import wraps
from math import pow
from types import TracebackType
from typing import (
    Any,
    Callable,
    Optional,
    ParamSpec,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    cast,
)

MAX_WAIT = 1073741823
ExceptionInfo: TypeAlias = Union[
    tuple[Type[BaseException], BaseException, TracebackType], tuple[None, None, None]
]


def _reraise(
    tp: Type[BaseException],
    value: Optional[BaseException],
    tb: Optional[TracebackType],
) -> None:
    try:
        if value is None:
            value = tp()
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value
    finally:
        value = None
        tb = None


def _retry_if_exception_of_type(
    retryable_types: tuple[type],
) -> Callable[[Optional[BaseException]], bool]:
    def _retry_if_exception_these_types(exception: Optional[BaseException]) -> bool:
        return isinstance(exception, retryable_types)

    return _retry_if_exception_these_types


def _current_time_ms() -> int:
    return int(round(time.time() * 1000))


Params = ParamSpec("Params")
ReturnType = TypeVar("ReturnType")


def retry(  # type: ignore[misc]
    _f: Optional[Callable[Params, ReturnType]] = None, **dkwds: Any
) -> Callable[[Callable[Params, ReturnType]], Callable[Params, ReturnType]] | Callable[
    Params, ReturnType
]:
    """Decorator function that instantiates the Retry object."""

    def decorator(f: Callable[Params, ReturnType]) -> Callable[Params, ReturnType]:
        @wraps(f)
        def wrapper(*args: Params.args, **kwds: Params.kwargs) -> ReturnType:
            return Retry(**dkwds).call(f, *args, **kwds)  # type: ignore[misc]

        return wrapper

    if _f is None:
        return decorator
    else:
        return decorator(_f)


class Retry:
    def __init__(
        self,
        stop: Optional[str] = None,
        wait: Optional[str] = None,
        stop_max_attempt_number: Optional[int] = None,
        stop_max_delay: Optional[int] = None,
        wait_fixed: Optional[int] = None,
        wait_random_min: Optional[int] = None,
        wait_random_max: Optional[int] = None,
        wait_incrementing_start: Optional[int] = None,
        wait_incrementing_increment: Optional[int] = None,
        wait_incrementing_max: Optional[int] = None,
        wait_exponential_multiplier: Optional[int] = None,
        wait_exponential_max: Optional[int] = None,
        retry_on_exception: Optional[
            Callable[[Optional[BaseException]], bool] | tuple[type]
        ] = None,
        retry_on_result: Optional[Callable[[ExceptionInfo | ReturnType], bool]] = None,
        wrap_exception: bool = False,
        stop_func: Optional[Callable[[int, int], bool]] = None,
        wait_func: Optional[Callable[[int, int], float]] = None,
        wait_jitter_max: Optional[int] = None,
        before_attempts: Optional[Callable[[int], None]] = None,
        after_attempts: Optional[Callable[[int], None]] = None,
    ):
        self._stop_max_attempt_number = (
            5 if stop_max_attempt_number is None else stop_max_attempt_number
        )
        self._stop_max_delay = 100 if stop_max_delay is None else stop_max_delay
        self._wait_fixed = 1000 if wait_fixed is None else wait_fixed
        self._wait_random_min = 0 if wait_random_min is None else wait_random_min
        self._wait_random_max = 1000 if wait_random_max is None else wait_random_max
        self._wait_incrementing_start = (
            0 if wait_incrementing_start is None else wait_incrementing_start
        )
        self._wait_incrementing_increment = (
            100 if wait_incrementing_increment is None else wait_incrementing_increment
        )
        self._wait_exponential_multiplier = (
            1 if wait_exponential_multiplier is None else wait_exponential_multiplier
        )
        self._wait_exponential_max = (
            MAX_WAIT if wait_exponential_max is None else wait_exponential_max
        )
        self._wait_incrementing_max = (
            MAX_WAIT if wait_incrementing_max is None else wait_incrementing_max
        )
        self._wait_jitter_max = 0 if wait_jitter_max is None else wait_jitter_max
        self._before_attempts = before_attempts
        self._after_attempts = after_attempts

        # stop behavior
        stop_funcs = []
        if stop_max_attempt_number is not None:
            stop_funcs.append(self.stop_after_attempt)

        if stop_max_delay is not None:
            stop_funcs.append(self.stop_after_delay)

        if stop_func is not None:
            self.stop = stop_func
        elif stop is None:
            self.stop = lambda attempts, delay: any(
                f(attempts, delay) for f in stop_funcs
            )
        else:
            self.stop = getattr(self, stop)

        def _wait_function(a: int, b: int, /) -> int:
            return 0

        # wait behavior
        wait_funcs = [_wait_function]
        if wait_fixed is not None:
            wait_funcs.append(self.fixed_sleep)

        if wait_random_min is not None or wait_random_max is not None:
            wait_funcs.append(self.random_sleep)

        if (
            wait_incrementing_start is not None
            or wait_incrementing_increment is not None
        ):
            wait_funcs.append(self.incrementing_sleep)

        if wait_exponential_multiplier is not None or wait_exponential_max is not None:
            wait_funcs.append(self.exponential_sleep)

        if wait_func is not None:
            self.wait = wait_func
        elif wait is None:
            self.wait = lambda attempts, delay: max(
                f(attempts, delay) for f in wait_funcs
            )
        else:
            self.wait = getattr(self, wait)

        # retry on exception filter
        if retry_on_exception is None:
            self._retry_on_exception = self.always_reject
        else:
            # this allows for providing a tuple of exception types that should be allowed to retry
            # on, and avoids having to create a callback that does the same thing
            if isinstance(retry_on_exception, (tuple)):
                retry_on_exception = _retry_if_exception_of_type(retry_on_exception)
            self._retry_on_exception = retry_on_exception

        # retry on result filter
        if retry_on_result is None:
            self._retry_on_result = self.never_reject
        else:
            self._retry_on_result = retry_on_result

        self._wrap_exception = wrap_exception

    def stop_after_attempt(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> bool:
        """Stop after the previous attempt >= stop_max_attempt_number."""
        return previous_attempt_number >= self._stop_max_attempt_number

    def stop_after_delay(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> bool:
        """Stop after the time from the first attempt >= stop_max_delay."""
        return delay_since_first_attempt_ms >= self._stop_max_delay

    def fixed_sleep(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> int:
        return self._wait_fixed

    def random_sleep(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> int:
        return random.randint(self._wait_random_min, self._wait_random_max)

    def incrementing_sleep(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> int:
        result = self._wait_incrementing_start + (
            self._wait_incrementing_increment * (previous_attempt_number - 1)
        )
        result = min(result, self._wait_incrementing_max)
        return result if result > 0 else 0

    def exponential_sleep(
        self, previous_attempt_number: int, delay_since_first_attempt_ms: int
    ) -> int:
        result = self._wait_exponential_multiplier * int(
            pow(2, previous_attempt_number)
        )
        result = min(result, self._wait_exponential_max)
        return result if result > 0 else 0

    @staticmethod
    def never_reject(result: ExceptionInfo | ReturnType, /) -> bool:
        return False

    @staticmethod
    def always_reject(result: Optional[BaseException], /) -> bool:
        return True

    def should_reject(self, attempt: Attempt) -> bool:
        return (
            self._retry_on_exception(attempt.exception_info[1])
            if attempt.exception_info
            else self._retry_on_result(attempt.returned_value)
        )

    def call(
        self,
        f: Callable[Params, ReturnType],
        *args: Params.args,
        **kwds: Params.kwargs,
    ) -> ReturnType:
        start_time_ms = _current_time_ms()
        attempt_number = 1
        while True:
            if self._before_attempts:
                self._before_attempts(attempt_number)

            try:
                attempt = Attempt(f(*args, **kwds), attempt_number, False)
            except BaseException:
                tb = sys.exc_info()
                attempt = Attempt(tb, attempt_number, True)

            if not self.should_reject(attempt):
                return attempt.get(self._wrap_exception)

            if self._after_attempts:
                self._after_attempts(attempt_number)

            delay_since_first_attempt_ms = _current_time_ms() - start_time_ms
            if self.stop(attempt_number, delay_since_first_attempt_ms):
                if not self._wrap_exception and attempt.exception_info:
                    # attempt.get() with an exception should cause raise, but raise just in case
                    raise attempt.get()
                else:
                    raise RetryError(attempt)
            else:
                sleep_ms = self.wait(attempt_number, delay_since_first_attempt_ms)
                if self._wait_jitter_max:
                    jitter = random.random() * self._wait_jitter_max
                    sleep_ms = sleep_ms + max(0, jitter)
                time.sleep(sleep_ms / 1000.0)

            attempt_number = attempt_number + 1


class Attempt:
    """
    An Attempt encapsulates a call to a target function that may end as a normal return value from
    the function or an Exception depending on what occurred during the execution.
    """

    def __init__(
        self,
        value: ReturnType | ExceptionInfo,
        attempt_number: int,
        has_exception: bool,
    ) -> None:
        self.exception_info, self.returned_value = None, None
        if has_exception:
            self.exception_info = cast(ExceptionInfo, value)
        else:
            self.returned_value = cast(ReturnType, value)
        self.attempt_number = attempt_number

    def get(self, wrap_exception: bool = False) -> ReturnType:
        """
        Return the return value of this Attempt instance or raise an Exception. If wrap_exception is
        true, this Attempt is wrapped inside of a RetryError before being raised.
        """
        if self.exception_info:
            if wrap_exception:
                raise RetryError(self)
            else:
                _reraise(*self.exception_info)

        return self.returned_value  # type: ignore

    def __repr__(self) -> str:
        if self.exception_info:
            return f'Attempts: {self.attempt_number}, Error:\n{"".join(traceback.format_tb(self.exception_info[2]))}'
        else:
            return f"Attempts: {self.attempt_number}, Value: {self.returned_value}"

    @property
    def value(self) -> Optional[ReturnType | ExceptionInfo]:
        # REMOVE: Left only to maintain public API
        return self.exception_info or self.returned_value

    @property
    def has_exception(self) -> bool:
        # REMOVE: Left only to maintain public API
        return bool(self.exception_info)


class RetryError(Exception):
    """A RetryError encapsulates the last Attempt instance right before giving up."""

    def __init__(self, last_attempt: Attempt) -> None:
        self.last_attempt = last_attempt

    def __str__(self) -> str:
        return f"RetryError[{self.last_attempt}]"
