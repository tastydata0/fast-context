from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .utils import Contextualizable


class HeaderToContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        context_manager: Contextualizable,
        header_prefix: str = "X-App-",
    ):
        """
        :param context_manager: Объект с методом contextualize (Manager или CompositeContext).
        :param header_prefix: Префикс хедеров, которые нужно ловить (например, 'X-App-').
        """
        super().__init__(app)
        self.context_manager = context_manager
        # Приводим к нижнему регистру для надежного сравнения,
        # так как хедеры в ASGI приходят в lowercase.
        self.header_prefix = header_prefix.lower()

    async def dispatch(self, request: Request, call_next):
        context_data = {}

        # Проходимся по всем хедерам запроса
        for key, value in request.headers.items():
            # key в request.headers всегда lowercase
            if key.startswith(self.header_prefix):
                # 1. Отрезаем префикс (x-app-user-id -> user-id)
                clean_key = key[len(self.header_prefix) :]

                # 2. Превращаем kebab-case в snake_case (user-id -> user_id)
                # Это нужно, чтобы в коде переменные назывались по-питоньи.
                snake_key = clean_key.replace("-", "_")

                # 3. Сохраняем
                context_data[snake_key] = value

        # Если ничего не нашли — просто вызываем дальше,
        # но лучше все равно зайти в контекст (пустой), чтобы гарантировать изоляцию,
        # если менеджер имеет какую-то логику инициализации.
        with self.context_manager.contextualize(**context_data):
            response = await call_next(request)

        return response
