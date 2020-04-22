# Retrrry

Decorate flaky functions with `@retry` to apply retrying logic.

Simplest way to use `Retrrry` is actually to copy the code in `retrrry.py` and use it in your
project, since there is no dependencies other than the standard library.

```python
@retry
def unreliable_func():
    import random
    if random.randint(0, 10) < 5:
        raise IOError('Fail')
    else:
        return 'Success'
```

## Configurations

- Specify stop condition (i.e. limit by number of attempts)
- Specify wait condition (i.e. exponential backoff sleeping between attempts)
- Specify certain Exceptions
- Specify expected returned result

## Installation

```sh
pip install retrrry
```

```python
from retrrry import retry
```

## Examples

The default behavior is to retry forever without waiting:

```python
@retry
def never_stop_never_wait():
    print('Retry forever, ignore Exceptions, no wait between retries')
```

Set the number of attempts before giving up:

```python
@retry(stop_max_attempt_number=7)
def stop_after_7_attempts():
    print('Stopping after 7 attempts')
```

Set a boundary for time for retry:

```python
@retry(stop_max_delay=10000)
def stop_after_10_s():
    print('Stopping after 10 seconds')
```

Set wait time between retries:

```python
@retry(wait_fixed=2000)
def wait_2_seconds():
    print('Wait 2 second between retries')
```

Inject some randomness:

```python
@retry(wait_random_min=1000, wait_random_max=2000)
def wait_1_to_2_seconds():
    print('Randomly wait 1 to 2 seconds between retries')
```

Use exponential backoff:

```python
@retry(wait_exponential_multiplier=1000, wait_exponential_max=10000)
def wait_exponential_1000():
    print(
        'Wait 2^i * 1000 milliseconds after ith retry, up to 10 seconds, then 10 seconds afterwards'
    )
```

Deal with specific exceptions:

```python
def retry_if_io_error(exception):
    return isinstance(exception, IOError)

@retry(retry_on_exception=retry_if_io_error)
def might_have_io_error():
    print('Retry if an IOError occurs, raise any other errors')

@retry(retry_on_exception=retry_if_io_error, wrap_exception=True)
def might_have_io_error_raise_retry_error():
    print('Retry if an IOError occurs, raise any other errors wrapped in RetryError')
```

Alter the behavior of retry based on a function return value:

```python
def retry_if_result_none(result):
    return result is None

@retry(retry_on_result=retry_if_result_none)
def might_return_none():
    print('Retry if return value is None')

# Or retry if result is equal to 1
@retry(retry_on_result=lambda x: x ==1)
def might_return_none():
    print('Retry if return value is 1')
```

Finally, we can always combine all of the configurations.
