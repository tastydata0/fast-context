from typing import Any, ContextManager, Protocol


# Протокол для типизации (говорит о том, что объект должен иметь метод contextualize)
class Contextualizable(Protocol):
    def contextualize(self, **kwargs: Any) -> ContextManager[None]: ...
