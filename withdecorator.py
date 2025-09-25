"""
A function decorator that transforms the function such that when it is called
it is called inside a with statement where the value of the context manager is
passed via the function's first argument. Decorator is correctly type-annotated
so the type checker sees the decorated function as a function without the first
argument.

See example below.
"""

import functools
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Concatenate, assert_type


def with_context[**ContextManagerArgs, **WrappedArgs, T, RetT](
    context_manager: Callable[ContextManagerArgs, AbstractContextManager[T]],
    *cm_args: ContextManagerArgs.args,
    **cm_kwargs: ContextManagerArgs.kwargs,
) -> Callable[
    [Callable[Concatenate[T, WrappedArgs], RetT]],
    Callable[WrappedArgs, RetT],
]:
    """
    Wraps a function such that it is called inside a `with` statement with
    the return value of `context_manager(*cm_args, **cm_kwargs)`.

    I.e. given a function that decorated with this function:

    ```python
    @with_context(context_manager, cm_arg1)
    def foobar(x, y, z):
        ...

    # Calling:
    foobar(a, b)

    # Is equivalent to calling the undecorated function like so:
    with context_manager(cm_arg1) as val:
        foobar(val, a, b)
    ```
    """

    def decorator(
        f: Callable[Concatenate[T, WrappedArgs], RetT],
    ) -> Callable[WrappedArgs, RetT]:
        @functools.wraps(f)
        def f_with_context(
            *wrapped_args: WrappedArgs.args,
            **wrapped_kwargs: WrappedArgs.kwargs,
        ) -> RetT:
            with context_manager(*cm_args, **cm_kwargs) as context:
                return f(context, *wrapped_args, **wrapped_kwargs)

        return f_with_context

    return decorator


@contextmanager
def my_context_manager(x: int, y: int) -> Generator[int]:
    print("Entering my_context_manager")
    yield x + y
    print("Exiting my_context_manager")


@with_context(my_context_manager, 100, 200)
def test(value1: int, value2: Any) -> int:
    """Docstring."""
    print(f"{value1 = !r}, {value2 = !r}")
    return 0


def main() -> None:
    x = test("a")
    assert_type(x, int)

    assert test.__name__ == "test"
    assert test.__doc__ == "Docstring."

    try:
        test(12, "a")  # type: ignore
    except TypeError as err:
        # Fails because the decorator removes the first argument
        assert err.args[0] == "test() takes 2 positional arguments but 3 were given"


if __name__ == "__main__":
    main()
