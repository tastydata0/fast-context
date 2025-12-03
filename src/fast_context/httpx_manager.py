import contextvars
import functools
import inspect
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional

import httpx

from .exceptions import NoContextException


class ContextVarsManager:
    def __init__(self, var_name: str = "request_context"):
        self._context_var: contextvars.ContextVar[Dict[str, Any]] = (
            contextvars.ContextVar(var_name, default={})
        )

    def get_context(self) -> Dict[str, Any]:
        return self._context_var.get().copy()

    @contextmanager
    def contextualize(self, **kwargs: Any) -> Generator[None, None, None]:
        """Обновляет контекст новыми переменными на время выполнения блока with."""
        current_context = self._context_var.get()
        new_context = current_context.copy()

        for k, v in kwargs.items():
            new_context[k] = v

        token = self._context_var.set(new_context)

        try:
            yield
        finally:
            self._context_var.reset(token)

    def inject_to_client(
        self, client: httpx.AsyncClient, prefix: str = "X-App-"
    ) -> None:
        """
        Внедряет механизм проброса хедеров в переданный httpx клиент.

        :param client: Экземпляр httpx.AsyncClient, который нужно обучить контексту.
        :param prefix: Префикс для хедеров (например 'X-App-').
        """

        async def add_context_headers_hook(request: httpx.Request) -> None:
            context_data = self.get_context()

            for key, value in context_data.items():
                # Формируем имя хедера
                header_key = f"{prefix}{key.replace('_', '-')}"

                # Добавляем хедер, если его еще нет в запросе
                if header_key not in request.headers:
                    request.headers[header_key] = str(value)

        # Добавляем наш хук в список хуков клиента
        client.event_hooks["request"].append(add_context_headers_hook)

    def inject_kwargs(
        self,
        *keys_to_inject,
        aliases: Optional[dict[str, str]] = None,
        override: bool = False,
        raise_on_missing: bool = True,
    ):
        """
        Декоратор-фабрика.
        Внедряет в вызов функции именованные аргументы, переданные при вызове. Значение - содержимое контекста по этому ключу

        :param keys_to_inject: Позиционные аргументы - названия ключей для внедрения.
        :param override: Именованный аргумент. Если True, значения из декоратора
                        имеют приоритет над переданными при вызове именованными
                        аргументами. По умолчанию False.
        :param raise_on_missing: Если True, вызывает NoContextException если ключа
                                 нет в контексте. По умолчанию True.
        :param aliases: Под какими именами прокинуть аргументы вместо указанных ключей. from -> to
        :raises NoContextException: Если ключа нет в контексте, если raise_on_missing=True.
        """

        aliases = aliases or {}

        def actual_decorator(func):
            sig = inspect.signature(func)
            is_async = inspect.iscoroutinefunction(func)

            if is_async:
                # Версия для async def функций
                @functools.wraps(func)
                async def wrapper(*args, **kwargs):
                    context = self.get_context()

                    if raise_on_missing:
                        for key in keys_to_inject:
                            if key not in context:
                                raise NoContextException(
                                    f"Ключ {key} отсутствует в контексте ({context})"
                                )

                    defaults = {
                        key: context[key] for key in keys_to_inject if key in context
                    }
                    for alias_from, alias_to in aliases.items():
                        if alias_from in context:
                            if alias_from in defaults:
                                defaults[alias_to] = defaults[alias_from]
                                del defaults[alias_from]

                    if override:
                        final_kwargs = kwargs.copy()
                        final_kwargs.update(defaults)
                    else:
                        final_kwargs = defaults.copy()
                        final_kwargs.update(kwargs)

                    bound_positional_args = sig.bind_partial(*args).arguments
                    for name in bound_positional_args:
                        final_kwargs.pop(name, None)

                    return await func(*args, **final_kwargs)

            else:

                @functools.wraps(func)
                def wrapper(*args, **kwargs):
                    context = self.get_context()

                    if raise_on_missing:
                        for key in keys_to_inject:
                            if key not in context:
                                raise NoContextException(
                                    f"Ключ {key} отсутствует в контексте ({context})"
                                )

                    defaults = {
                        key: context[key] for key in keys_to_inject if key in context
                    }
                    for alias_from, alias_to in aliases.items():
                        if alias_from in context:
                            if alias_from in defaults:
                                defaults[alias_to] = defaults[alias_from]
                                del defaults[alias_from]

                    # 1. Формируем "кандидатский" набор kwargs,
                    #    учитывая флаг `override`.
                    if override:
                        # Начинаем с явных kwargs, но разрешаем `defaults` их перезаписать
                        final_kwargs = kwargs.copy()
                        final_kwargs.update(defaults)
                    else:
                        # Начинаем с `defaults`, но разрешаем явным kwargs их перезаписать
                        final_kwargs = defaults.copy()
                        final_kwargs.update(kwargs)

                    # 2. Проверяем реальность: позиционные аргументы имеют абсолютный приоритет.
                    #    Удаляем из наших кандидатов все, что уже было передано позиционно.
                    bound_positional_args = sig.bind_partial(*args).arguments
                    for name in bound_positional_args:
                        final_kwargs.pop(name, None)

                    # 3. Вызываем функцию с правильным набором аргументов.
                    return func(*args, **final_kwargs)

            return wrapper

        return actual_decorator
