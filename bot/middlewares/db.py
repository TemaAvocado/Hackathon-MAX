from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker
from maxo.routing.ctx import Ctx
from maxo.routing.interfaces.middleware import BaseMiddleware, NextMiddleware


# Открывает сессию на время обработки события и передаёт её в хендлер как session
class DbSessionMiddleware(BaseMiddleware[Any]):
    def __init__(self, session_maker: async_sessionmaker):
        self.session_maker = session_maker

    async def __call__(self, update: Any, ctx: Ctx, next: NextMiddleware[Any]):
        async with self.session_maker() as session:
            ctx["session"] = session
            return await next(ctx)