# Библиотека для проброса метаданных (контекста) между микросервисами с FastAPI & httpx.

## Примеры

### Отправка запросов с передачей контекста в хедеры

```python
from fast_context import ContextVarsManager, ContextManagerAggregator
import httpx

# Менеджер, хранит контекст в ContextVars
manager = ContextVarsManager()

# Стандартный! httpx клиент. Можно обратиться к внутреннему клиенту библиотеки openai
http_client = httpx.AsyncClient()

# Агрегатор, объединяет несколько менеджеров в один. Вызов with ctx.contextualize() вызывает contextualize у всех переданных сюда менеджеров. Это утилита, чтобы не стакать друг над другом похожие with ...contexualize()
ctx = ContextManagerAggregator(manager, logger)

# Патчим httpx клиент, чтобы он передавал контекст в хедеры, добавляя префикс "x-app-"
manager.inject_to_client(http_client, prefix="x-app-")

with ctx.contextualize(request_id="123"):
    with ctx.contextualize(user_id="user1"):
        response = await http_client.get("http://localhost:8000/")

    with ctx.contextualize(some_id="some4"):
        response = await http_client.get("http://localhost:8000/")

response = await http_client.get("http://localhost:8000/")
```

### Получение хедеров в FastAPI и проброс в контекст

```python
import httpx
import uvicorn
from fastapi import FastAPI
from loguru import logger

from fast_context import ContextManagerAggregator, ContextVarsManager, HeaderToContextMiddleware

# 1. Setup (один раз при старте)
ctx_manager = ContextVarsManager()
ctx = ContextManagerAggregator(logger, ctx_manager)  # Объединяем логгер и наш менеджер

# Настраиваем http клиент
http_client = httpx.AsyncClient()
ctx_manager.inject_to_client(http_client, prefix="X-Out-")

app = FastAPI()

# 2. Добавляем Middleware
app.add_middleware(
    HeaderToContextMiddleware,
    context_manager=ctx,  # Сюда можно передать и просто ctx_manager, и composite
    header_prefix="X-App-",  # Хедеры вида X-App-User-Id будут обработаны
)


@app.get("/")
async def proxy_endpoint():
    # Представим, что нам пришел запрос с хедером:
    # X-App-Trace-Id: abc-123

    # 1. Middleware нашла хедер, обрезала 'X-App-', сделала 'trace_id'.
    # 2. Loguru получил .contextualize(trace_id="abc-123") -> это попадет в логи.
    logger.info("Processing request inside endpoint")

    # 3. Httpx клиент получил 'trace_id'.
    # Он добавит префикс 'X-Out-' (как мы настроили выше) и отправит хедер:
    # X-Out-Trace-Id: abc-123
    resp = await http_client.get(
        "https://webhook.site/..."
    )


if __name__ == "__main__":
    uvicorn.run(app, port=8000)
```
