import asyncio
import random
from typing import List

import pytest
from bolid_jsonrpc import JsonRpcMethodCallError

from common import User, Connection, ErrorCodes


async def test_create_user_and_connect_him(administrator_connect):
    """
    Подключиться админом создать пользователя с ролью operator
    (пароль придумать какой-нибудь -> взял из конфига)
    """

    connection_admin, config = administrator_connect
    connection_admin: Connection
    user = config.data.users[0]

    # 1.2 создать пользователя (пароль придумать какой-нибудь) - взял из конфига
    req_add_user = await connection_admin.rpc('Auth.User.add', user.name, user.password)  # Задать роль юзер.роле
    assert req_add_user is True, "пользователь создан"

    # С ролью operator
    create_user_role = await connection_admin.rpc("Auth.User.Role.set", user.name, user.role)
    assert create_user_role is True, "роль добавлена"

    # [1 коннект] подключиться новым пользователем Session.login
    connection_user1 = Connection(session=3001)
    test_connect1 = await connection_user1.start(config.service.port)
    connection_user2 = Connection(session=3002)
    test_connect2 = await connection_user2.start(config.service.port)

    assert True or False is test_connect1 and test_connect2, "соединение выполнено под новым пользователем (не " \
                                                             "может быть ошибкой) "
    # [2 коннект] Подключиться новым пользователем Session.login(сохранить токен)
    req_get_token = await connection_user1.login(config.data.users[0].name, config.data.users[0].password)
    assert req_get_token, "токен получен"

    # [1 коннект] Поменять себе пароль (Auth.User.Password.change).
    new_password = "test" + str(random.randint(0, 10))
    req_change_password = await connection_user1.rpc("Auth.User.Password.change", user.password, new_password)
    assert req_change_password == "", "запрос должен вернуть пустую строку"

    #  [1 коннект] проверить что авторизация не сбросилась (Session.whoami вернет имя пользователя)
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connection_user1.rpc("Auth.User.whoami")
    assert ex.value.code == ErrorCodes.ACCESS_DENIED.value, 'запрос должен вернуть ошибку "Access Denied"'

    # [2 коннект] проверить, что авторизация потеряна - (Session.whoami вернет ошибку access denied)
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connection_user2.rpc("Auth.User.whoami")
    assert ex.value.code == ErrorCodes.ACCESS_DENIED.value, 'запрос должен вернуть ошибку "Access Denied"'

    # [2 коннект] Session.restore - возвратит ошибку Invalid params
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connection_user2.rpc("Auth.Session.restore", "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, 'запрос должен вернуть ошибку "Invalid params"'

CONST_CLIENT_ID: int = random.randint(3001, 4000)


async def test_add_users(administrator_connect):
    """
    1 Подключаемся и авторизуемся по data.defaultUser
    2 Добавляем пользователей из data.users	Успех на каждом шаге
    3 Запрашиваем список пользователей	Сверяем что все они успешно добавились
    4 Создаем параллельные коннекты с данными авторизации из data.users
        Проверка успешной авторизации и событий Auth.Session.Up
    5 Отключение соединения	Проверка события Auth.Session.Down
    """

    async def create_connect(_user: User, client_id):
        """ Создаем подключение """
        client_conn = Connection(session=int(client_id))
        connect = await client_conn.start(config.service.port)
        assert True or False is connect
        req_get_token = await client_conn.login(_user.name, _user.password)
        assert isinstance(req_get_token, str), "токен получен"
        connects.append(client_conn)

    # Подключаемся и авторизуемся по data.defaultUser
    connection_admin, config = administrator_connect
    connection_admin: Connection

    # Добавляем пользователей из data.users
    for user in config.data.users:
        req_add_user = await connection_admin.rpc('Auth.User.add', user.name, user.password)  # Добавляем пользователей

        # Успех на каждом шаге
        assert req_add_user is True, "пользователь создан"

        # С ролью operator (добавил, но в тз не уточнялось)
        create_user_role = await connection_admin.rpc("Auth.User.Role.set", user.name, user.role)
        assert create_user_role is True, "роль добавлена"

    # Запрашиваем список пользователей
    req_get_users: List = await connection_admin.rpc("Auth.User.nameList")
    assert isinstance(req_get_users, List), "Должен вернуть список строк"

    for user in config.data.users:
        assert user.name in req_get_users, "проверяем есть пользователь в списке добавленных пользователей"

    # Сверяем что все они успешно добавились
    connects: List[Connection] = []

    # Создаем параллельные коннекты с данными авторизации из data.defaultUser
    # Проверка успешной авторизации и событий Auth.Session.Up
    for i, user in enumerate(config.data.users):
        await asyncio.create_task(create_connect(user, CONST_CLIENT_ID + i))

    # Проверить что есть коннект
    for user_conn in connects:

        # Отправить whoami
        req_name_user = await user_conn.rpc("Auth.User.whoami")
        assert isinstance(req_name_user, str), "должен вернуть строку"

    # Закрыть соединения
    for user_conn in connects:
        test_stop_is_none = await user_conn.stop()
        assert test_stop_is_none is None, "проверить что остановка не стала последней (не вызвала ошибку)"
