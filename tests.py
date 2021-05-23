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

import time
import pytest
import logging

from retrrry import RetryError
from retrrry import Retry
from retrrry import retry

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Stop Conditions

def test_never_stop():
    r = Retry()
    assert not r.stop(3, 6546)


def test_stop_after_attempt():
    r = Retry(stop_max_attempt_number=3)
    assert not r.stop(2, 6546)
    assert r.stop(3, 6546)
    assert r.stop(4, 6546)


def test_stop_after_delay():
    r = Retry(stop_max_delay=1000)
    assert not r.stop(2, 999)
    assert r.stop(2, 1000)
    assert r.stop(2, 1001)


def test_legacy_explicit_stop_type():
    Retry(stop="stop_after_attempt")


def test_stop_func():
    r = Retry(stop_func=lambda attempt, delay: attempt == delay)
    assert not r.stop(1, 3)
    assert not r.stop(100, 99)
    assert r.stop(101, 101)


# Wait Conditions


def test_no_sleep():
    r = Retry()
    assert 0 == r.wait(18, 9879)


def test_fixed_sleep():
    r = Retry(wait_fixed=1000)
    assert 1000 == r.wait(12, 6546)


def test_incrementing_sleep():
    r = Retry(wait_incrementing_start=500, wait_incrementing_increment=100)
    assert 500 == r.wait(1, 6546)
    assert 600 == r.wait(2, 6546)
    assert 700 == r.wait(3, 6546)


def test_random_sleep():
    r = Retry(wait_random_min=1000, wait_random_max=2000)
    times = set()
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))

    # this is kind of non-deterministic...
    assert len(times) > 1
    for t in times:
        assert t >= 1000
        assert t <= 2000


def test_random_sleep_without_min():
    r = Retry(wait_random_max=2000)
    times = set()
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))
    times.add(r.wait(1, 6546))

    # this is kind of non-deterministic...
    assert len(times) > 1
    for t in times:
        assert t >= 0
        assert t <= 2000


def test_exponential():
    r = Retry(wait_exponential_max=100000)
    assert r.wait(1, 0) == 2
    assert r.wait(2, 0) == 4
    assert r.wait(3, 0) == 8
    assert r.wait(4, 0) == 16
    assert r.wait(5, 0) == 32
    assert r.wait(6, 0) == 64


def test_exponential_with_max_wait():
    r = Retry(wait_exponential_max=40)
    assert r.wait(1, 0) == 2
    assert r.wait(2, 0) == 4
    assert r.wait(3, 0) == 8
    assert r.wait(4, 0) == 16
    assert r.wait(5, 0) == 32
    assert r.wait(6, 0) == 40
    assert r.wait(7, 0) == 40
    assert r.wait(50, 0) == 40


def test_exponential_with_max_wait_and_multiplier():
    r = Retry(wait_exponential_max=50000, wait_exponential_multiplier=1000)
    assert r.wait(1, 0) == 2000
    assert r.wait(2, 0) == 4000
    assert r.wait(3, 0) == 8000
    assert r.wait(4, 0) == 16000
    assert r.wait(5, 0) == 32000
    assert r.wait(6, 0) == 50000
    assert r.wait(7, 0) == 50000
    assert r.wait(50, 0) == 50000


def test_legacy_explicit_wait_type():
    Retry(wait="exponential_sleep")


def test_wait_func():
    r = Retry(wait_func=lambda attempt, delay: attempt * delay)
    assert r.wait(1, 5) == 5
    assert r.wait(2, 11) == 22
    assert r.wait(10, 100) == 1000


class NoneReturnUntilAfterCount:
    """
    This class holds counter state for invoking a method several times in a row.
    """

    def __init__(self, count):
        self.counter = 0
        self.count = count

    def go(self):
        """
        Return None until after count threshold has been crossed, then return True.
        """
        if self.counter < self.count:
            self.counter += 1
            return None
        return True


class OneReturnUntilAfterCount:
    """
    This class holds counter state for invoking a method several times in a row.
    """

    def __init__(self, count):
        self.counter = 0
        self.count = count

    def go(self):
        """
        Return None until after count threshold has been crossed, then return True.
        """
        if self.counter < self.count:
            self.counter += 1
            return 1
        return True


class NoIOErrorAfterCount:
    """
    This class holds counter state for invoking a method several times in a row.
    """

    def __init__(self, count):
        self.counter = 0
        self.count = count

    def go(self):
        """
        Raise an IOError until after count threshold has been crossed, then return True.
        """
        if self.counter < self.count:
            self.counter += 1
            raise IOError("Hi there, I'm an IOError")
        return True


class NoNameErrorAfterCount:
    """
    This class holds counter state for invoking a method several times in a row.
    """

    def __init__(self, count):
        self.counter = 0
        self.count = count

    def go(self):
        """
        Raise a NameError until after count threshold has been crossed, then return True.
        """
        if self.counter < self.count:
            self.counter += 1
            raise NameError("Hi there, I'm a NameError")
        return True


class CustomError(Exception):
    """
    This is a custom exception class. Note that For Python 2.x, we don't
    strictly need to extend BaseException, however, Python 3.x will complain.
    While this test suite won't run correctly under Python 3.x without
    extending from the Python exception hierarchy, the actual module code is
    backwards compatible Python 2.x and will allow for cases where exception
    classes don't extend from the hierarchy.
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class NoCustomErrorAfterCount:
    """
    This class holds counter state for invoking a method several times in a row.
    """

    def __init__(self, count):
        self.counter = 0
        self.count = count

    def go(self):
        """
        Raise a CustomError until after count threshold has been crossed, then return True.
        """
        if self.counter < self.count:
            self.counter += 1
            derived_message = "This is a Custom exception class"
            raise CustomError(derived_message)
        return True


def retry_if_result_none(result):
    return result is None


def retry_if_exception_of_type(retryable_types):
    def retry_if_exception_these_types(exception):
        logger.debug(f"Detected Exception of type: {str(type(exception))}")
        return isinstance(exception, retryable_types)

    return retry_if_exception_these_types


def current_time_ms():
    return int(round(time.time() * 1000))


@retry(wait_fixed=50, retry_on_result=retry_if_result_none)
def _retryable_test_with_wait(thing):
    return thing.go()


@retry(stop_max_attempt_number=3, retry_on_result=retry_if_result_none)
def _retryable_test_with_stop(thing):
    return thing.go()


@retry(stop_max_attempt_number=3, retry_on_result=lambda x: x == 1)
def _retryable_test_with_lambda(thing):
    return thing.go()


@retry(retry_on_exception=(IOError,))
def _retryable_test_with_exception_type_io(thing):
    return thing.go()


@retry(retry_on_exception=retry_if_exception_of_type(IOError), wrap_exception=True)
def _retryable_test_with_exception_type_io_wrap(thing):
    return thing.go()


@retry(stop_max_attempt_number=3, retry_on_exception=(IOError,))
def _retryable_test_with_exception_type_io_attempt_limit(thing):
    return thing.go()


@retry(stop_max_attempt_number=3, retry_on_exception=(IOError,), wrap_exception=True)
def _retryable_test_with_exception_type_io_attempt_limit_wrap(thing):
    return thing.go()


@retry
def _retryable_default(thing):
    return thing.go()


@retry()
def _retryable_default_f(thing):
    return thing.go()


@retry(retry_on_exception=retry_if_exception_of_type(CustomError))
def _retryable_test_with_exception_type_custom(thing):
    return thing.go()


@retry(retry_on_exception=retry_if_exception_of_type(CustomError), wrap_exception=True)
def _retryable_test_with_exception_type_custom_wrap(thing):
    return thing.go()


@retry(
    stop_max_attempt_number=3,
    retry_on_exception=retry_if_exception_of_type(CustomError),
)
def _retryable_test_with_exception_type_custom_attempt_limit(thing):
    return thing.go()


@retry(
    stop_max_attempt_number=3,
    retry_on_exception=retry_if_exception_of_type(CustomError),
    wrap_exception=True,
)
def _retryable_test_with_exception_type_custom_attempt_limit_wrap(thing):
    return thing.go()


# Test Decorator Wrapper


def test_with_wait():
    start = current_time_ms()
    result = _retryable_test_with_wait(NoneReturnUntilAfterCount(5))
    t = current_time_ms() - start
    assert t >= 250
    assert result


def test_with_stop_on_return_value():
    try:
        _retryable_test_with_stop(NoneReturnUntilAfterCount(5))
        pytest.xfail("Expected RetryError after 3 attempts")
    except RetryError as e:
        logger.debug(e)
        assert not e.last_attempt.has_exception
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.value is None


def test_with_stop_on_return_value_lambda():
    try:
        _retryable_test_with_lambda(OneReturnUntilAfterCount(5))
        pytest.xfail("Expected RetryError after 3 attempts")
    except RetryError as e:
        logger.debug(e)
        assert not e.last_attempt.has_exception
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.value == 1


def test_with_stop_on_exception():
    try:
        _retryable_test_with_stop(NoIOErrorAfterCount(5))
        pytest.xfail("Expected IOError")
    except IOError as e:
        logger.debug(e)
        assert isinstance(e, IOError)


def test_retry_if_exception_of_type():
    assert _retryable_test_with_exception_type_io(NoIOErrorAfterCount(5))

    try:
        _retryable_test_with_exception_type_io(NoNameErrorAfterCount(5))
        pytest.xfail("Expected NameError")
    except NameError as e:
        logger.debug(e)
        assert isinstance(e, NameError)

    try:
        _retryable_test_with_exception_type_io_attempt_limit_wrap(
            NoIOErrorAfterCount(5)
        )
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        logger.debug(e)
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.has_exception
        assert e.last_attempt.value[0] is not None
        assert isinstance(e.last_attempt.value[1], IOError)
        assert e.last_attempt.value[2] is not None

    assert _retryable_test_with_exception_type_custom(NoCustomErrorAfterCount(5))

    try:
        _retryable_test_with_exception_type_custom(NoNameErrorAfterCount(5))
        pytest.xfail("Expected NameError")
    except NameError as e:
        logger.debug(e)
        assert isinstance(e, NameError)

    try:
        _retryable_test_with_exception_type_custom_attempt_limit_wrap(
            NoCustomErrorAfterCount(5)
        )
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        logger.debug(e)
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.has_exception
        assert e.last_attempt.value[0] is not None
        assert isinstance(e.last_attempt.value[1], CustomError)
        assert e.last_attempt.value[2] is not None


def test_wrapped_exception():

    # base exception cases
    assert _retryable_test_with_exception_type_io_wrap(NoIOErrorAfterCount(5))

    try:
        _retryable_test_with_exception_type_io_wrap(NoNameErrorAfterCount(5))
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        logger.debug(e)
        assert isinstance(e.last_attempt.value[1], NameError)

    try:
        _retryable_test_with_exception_type_io_attempt_limit_wrap(
            NoIOErrorAfterCount(5)
        )
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        logger.debug(e)
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.has_exception
        assert e.last_attempt.value[0] is not None
        assert isinstance(e.last_attempt.value[1], IOError)
        assert e.last_attempt.value[2] is not None

    # custom error cases
    assert _retryable_test_with_exception_type_custom_wrap(NoCustomErrorAfterCount(5))

    try:
        _retryable_test_with_exception_type_custom_wrap(NoNameErrorAfterCount(5))
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        logger.debug(e)
        assert e.last_attempt.value[0] is not None
        assert isinstance(e.last_attempt.value[1], NameError)
        assert e.last_attempt.value[2] is not None

    try:
        _retryable_test_with_exception_type_custom_attempt_limit_wrap(
            NoCustomErrorAfterCount(5)
        )
        pytest.xfail("Expected RetryError")
    except RetryError as e:
        assert 3 == e.last_attempt.attempt_number
        assert e.last_attempt.has_exception
        assert e.last_attempt.value[0] is not None
        assert isinstance(e.last_attempt.value[1], CustomError)
        assert e.last_attempt.value[2] is not None
        assert "This is a Custom exception class" in str(e.last_attempt.value[1])


def test_defaults():
    assert _retryable_default(NoNameErrorAfterCount(5))
    assert _retryable_default_f(NoNameErrorAfterCount(5))
    assert _retryable_default(NoCustomErrorAfterCount(5))
    assert _retryable_default_f(NoCustomErrorAfterCount(5))
