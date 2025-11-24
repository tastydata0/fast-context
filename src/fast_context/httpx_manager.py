import contextvars
from contextlib import contextmanager
from typing import Any, Dict, Generator

import httpx


class ContextVarsManager:
    def __init__(self, var_name: str = "request_context"):
        self._context_var: contextvars.ContextVar[Dict[str, str]] = (
            contextvars.ContextVar(var_name, default={})
        )

    def get_context(self) -> Dict[str, str]:
        return self._context_var.get().copy()

    @contextmanager
    def contextualize(self, **kwargs: Any) -> Generator[None, None, None]:
        """Обновляет контекст новыми переменными на время выполнения блока with."""
        current_context = self._context_var.get()
        new_context = current_context.copy()

        for k, v in kwargs.items():
            new_context[k] = str(v)

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
                    request.headers[header_key] = value

        # Добавляем наш хук в список хуков клиента
        client.event_hooks["request"].append(add_context_headers_hook)
