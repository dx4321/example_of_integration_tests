from typing import Optional, List

from bolid_jsonrpc import JsonRpcClientBase, tcp_json_rpc_client, JsonRpcHandshakeParam, auth_login


class Connection:
    ALL_CONNECTS: List[JsonRpcClientBase] = []

    def __init__(self, session: int):
        """
        :param session: - для пользователей от 3000 до 4000
        для сервисного подключения - 1 до 3000
        для админа c 3000
        """
        self.id_session: Optional[int] = None
        self.rpc: Optional[JsonRpcClientBase] = None
        self.name: Optional[str] = None
        self.session: Optional[int] = session
        self.token: Optional[str] = None

    async def start(self, port: int):
        """ Создать соединение """
        _connect = tcp_json_rpc_client('127.0.0.1',
                                       port,
                                       handshake=JsonRpcHandshakeParam(  # рукопожатие
                                           client_id=self.session,
                                           host='localhost',
                                           user_agent='internal', )
                                       )
        conn = await _connect.connect()
        self.rpc = _connect
        Connection.ALL_CONNECTS.append(_connect)
        return conn

    async def stop(self):
        """ Разрыв соединения """
        await self.rpc.stop()
        Connection.ALL_CONNECTS.remove(self.rpc)

    # вспомогательные методы обертки над rpc
    async def login(self, user_name: str, user_password: str):
        self.name = user_name
        self.token = await auth_login(
            self.rpc,
            user_name,
            user_password,
        )  # После логина внутреннее состояние объекта rpc изменится
        return self.token

    async def restore(self):
        # авторизация(токен)
        await self.login("Auth.Session.restore", self.token)
        # whoami получить userName
        await self.rpc("Auth.User.whoami")
