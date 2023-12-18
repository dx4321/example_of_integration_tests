from typing import List, Optional

__all__ = ["Group"]

from common import User, Connection


class Group:
    def __init__(self, user: User, port: int):
        self.id: Optional[int] = None
        self.user: User = user
        self.port = port
        self.connection: List[Connection] = []
        self.token: str = ""

    async def create(self, count_connects: int, session: int):
        """ Сессии не должны повторяться сессия админа - 3000, пользовательские с 3001 """
        for i in range(0, count_connects):
            connect = Connection(session=session + i)
            await connect.start(self.port)
            # первое соединение login
            if i == 0:
                self.token = await connect.login(self.user.name, self.user.password)
            # остальные по цепочке через restore
            else:
                self.token = await connect.rpc("Auth.Session.restore", self.token)
            self.connection.append(connect)

    def set_id(self, id: int):
        self.id = id
