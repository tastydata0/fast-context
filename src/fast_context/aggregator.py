from contextlib import ExitStack, contextmanager
from typing import Any

from .types import Contextualizable


class ContextManagerAggregator:
    """
    Агрегатор контекстных менеджеров.
    Позволяет вызывать contextualize один раз, а он прокидывает аргументы
    во все зарегистрированные менеджеры (ContextVarsManager, loguru.logger и т.д.).
    """

    def __init__(self, *managers: Contextualizable):
        """
        :param managers: Список объектов, имеющих метод contextualize(**kwargs).
        """
        self.managers = managers

    @contextmanager
    def contextualize(self, **kwargs: Any):
        """
        Входит в контекст всех менеджеров одновременно, передавая им одни и те же аргументы.
        """
        # ExitStack — это "стек" для контекстных менеджеров.
        # Он гарантирует, что если мы вошли в 3 контекста, а в 4-м ошибка,
        # то первые 3 корректно закроются.
        with ExitStack() as stack:
            for mgr in self.managers:
                # Вызываем метод contextualize у каждого менеджера
                cm = mgr.contextualize(**kwargs)
                # Входим в контекст и регистрируем его в стеке для автоматического выхода
                stack.enter_context(cm)

            # Передаем управление внутрь блока with
            yield
