import asyncio
from pathlib import Path
from typing import List

import pytest
from bolid_jsonrpc import JsonRpcMethodCallError
from pydantic import BaseModel

from common import ErrorCodes, read_json_config, User, Connection, Config

""" Проверка уведомлений авторизации """


class UserData(BaseModel):
    id: int
    name: str


class AuthSessionUp(BaseModel):
    status: str
    user: UserData
    role: str
    host: str
    userAgent: str
    session: int


class AuthSessionDown(BaseModel):
    reason: int
    sessions: list
    user: UserData


class SessionNotifyHandler:
    def __init__(self):
        self._down = None
        self._up = None
        self._evt = asyncio.Event()

    def clear(self):
        self._down = None
        self._up = None
        self._evt.clear()

    def on_up(self, _: str, data: AuthSessionUp):
        self._up = data
        self._evt.set()

    def on_down(self, _: str, data: AuthSessionDown):
        self._down = data
        self._evt.set()

    async def wait_down(self, timeout: int) -> AuthSessionDown:
        await asyncio.wait_for(self._evt.wait(), timeout)
        return self._down

    async def wait_up(self, timeout: int) -> AuthSessionUp:
        """ Вызвать clear() до вызова метода """
        await asyncio.wait_for(self._evt.wait(), timeout)
        return self._up


async def test_session_notify(create_two_users):
    """ Служебное соединение подключается к сервису с идентификатором описанном в конфиге приложения(сервиса)
        core.trasted - не совсем понял - уточню
    """

    async def create_connect(client_id: int, _user: User = None) -> Connection:

        # Создаем подключение с данными авторизации пользователя
        """ Создаем подключение """
        client_conn = Connection(session=int(client_id))
        connect = await client_conn.start(config.service.port)
        assert True or False is connect

        if _user:
            req_get_token = await client_conn.login(_user.name, _user.password)
            assert isinstance(req_get_token, str), "токен получен"

        return client_conn

    connection_admin, config = create_two_users
    connection_admin: Connection
    config: Config

    """
    Отправляет запрос
    Session.subscribe
    """
    path = Path(Path.cwd(), config.work_dir, config.service.config.name)
    _core_trusted: int = read_json_config(str(path))["core"]["trasted"][0]
    service_connect: Connection = await create_connect(_core_trusted)
    subscribe: bool = await service_connect.rpc("Session.subscribe", True)
    checker: SessionNotifyHandler = SessionNotifyHandler()

    for_register_trap = [
        [checker.on_up, {"Auth.Session.Up": AuthSessionUp}],
        [checker.on_down, {"Auth.Session.Down": AuthSessionDown}],
    ]

    [service_connect.rpc.register_notification_trap(*reg) for reg in for_register_trap]

    assert subscribe is True, "подписались"
    """ 
    Создаем подключение с авторизационными даными 1 пользователя (c1)
    проверить что в сервисном подключении, получено уведомление Auth.Session.Up
    проверить данные 
    """
    timeout = 10

    checker.clear()
    connect1 = await create_connect(3002, config.data.users[0])
    up_data = await checker.wait_up(timeout)
    assert config.data.users[0].name == up_data.user.name, "Имена совпадают"

    checker.clear()
    connect2 = await create_connect(3003, config.data.users[1])
    up_data2 = await checker.wait_up(timeout)

    # Проверить что имена совпадают
    assert config.data.users[1].name == up_data2.user.name, "Имена совпадают"

    """
    c1 отключение соединение

    проверить что в сервисном подключении, получено уведомление Auth.Session.Down
    проверить данные
    """

    checker.clear()
    await connect1.stop()
    down_data = await checker.wait_down(timeout)
    assert config.data.users[0].name == down_data.user.name, "Имена совпадают"

    """
    с2 Auth.Session.logout

    проверить результат
    проверить что в сервисном подключении, получено уведомление Auth.Session.Down
    проверить данные
    """
    await connect2.rpc("Auth.Session.logout")

    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connect2.rpc("Auth.User.whoami")
    assert ex.value.code == ErrorCodes.ACCESS_DENIED.value, "Access Denied, проверить что выходит ошибка " \
                                                            "JsonRpcMethodCallError " \
                                                            "по причине Access Denied "
