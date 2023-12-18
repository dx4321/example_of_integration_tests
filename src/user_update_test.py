import random
from pathlib import Path
from typing import Optional, List

import pytest
from bolid_jsonrpc import JsonRpcMethodCallError

from common import Connection, Config, ErrorCodes, read_json_config


async def test_create_users(administrator_connect, close_all_connect):
    """ протестировать метод - Auth.User.create """

    # Использовать фикстуры create_admin, close_connections
    admin_connect, config = administrator_connect
    admin_connect: Optional[Connection]
    config: Optional[Config]

    # Создать пользователя data.users[0] с использованием метода "Auth.User.create"
    req_create = await admin_connect.rpc('Auth.User.create', config.data.users[0].name,
                                         config.data.users[0].password, "")
    assert req_create is True, "Должно придти что пользователь создан"

    # Создать соединение пользователя
    user1_conn = Connection(session=(3001 + 1))
    await user1_conn.start(config.service.port)
    req_token = await user1_conn.login(config.data.users[0].name, config.data.users[0].password)
    assert req_token != "", "Проверить что пришел токен, не пустая строка"

    # Тестируем некорректное создание пользователя
    # создать пользователя с логином до 5 символов и больше 30 символов и паролем от 5 до 30 символов
    login = "".join(["n" for _ in range(1, random.randint(0, 5))])
    password = "".join(["p" for _ in range(1, random.randint(4, 29))])

    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc('Auth.User.create', login, password, "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"

    # Тестируем некорректное создание пользователя
    # создать пользователя с логином от 5 до 30 символов и паролем до 5 и от 30 символов
    login = "".join(["n" for _ in range(1, random.randint(6, 31))])
    password = "".join(["p" for _ in range(1, random.randint(1, 5))])

    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc('Auth.User.create', login, password, "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"

    login = "".join(["n" for _ in range(1, random.randint(6, 31))])
    password = "".join(["p" for _ in range(1, random.randint(31, 100))])

    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc('Auth.User.create', login, password, "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"

    # создать пользователя с логином в котором есть - "@ - _ ."
    password_have_variants: List = "@ - _ .".split(" ")
    for var_password in password_have_variants:
        for_login = "".join([var_password for _ in range(1, random.randint(6, 31))])
        test_req = await admin_connect.rpc('Auth.User.create',
                                           for_login,
                                           config.data.users[0].password,
                                           "")
        assert test_req is True

    # role пустая строка
    test_req = await admin_connect.rpc('Auth.User.create',
                                       config.data.users[1].name,
                                       config.data.users[1].password,
                                       "")
    assert test_req is True, "Проверить что все ок"

    # role не в списке который возвращает метод Auth.User.Role.availableList
    role_list: List = await admin_connect.rpc("Auth.User.Role.availableList")

    new_role = "super_role" + str(random.randint(4, 400))
    if new_role not in role_list:
        with pytest.raises(JsonRpcMethodCallError) as ex:
            await admin_connect.rpc('Auth.User.create',
                                    "test_user_887",
                                    "test_user_887",
                                    new_role)
        assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"

    # role есть в списке Auth.User.Role.availableList
    role_in_role_list = await admin_connect.rpc('Auth.User.create',
                                                "test_user_888",
                                                "test_user_888",
                                                role_list[random.randint(0, (len(role_list) - 1))]
                                                )
    assert role_in_role_list is True, "пользователь должен создаться"

    # Попытаться создать дубликат пользователей -> должны получить false
    test_double_user = await admin_connect.rpc('Auth.User.create',
                                               config.data.users[0].name,
                                               config.data.users[0].password,
                                               "")
    assert test_double_user is False, "должны получить false"

    # Создать пользователя без логина, указать только пароль - получить ошибку INVALID_ARGUMENT
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc('Auth.User.create', "", config.data.users[0].password, "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"

    # Создать пользователя без пароля, указать только логин - получить ошибку INVALID_ARGUMENT
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc('Auth.User.create', config.data.users[0].name, "", "")
    assert ex.value.code == ErrorCodes.INVALID_ARGUMENT.value, "проверить что выходит ошибка INVALID_ARGUMENT"


async def test_get_default_role(administrator_connect, close_all_connect):
    """ Протестировать метод - Auth.User.Role.getDefault """

    # с помощью админского соединения сделать запрос .rpc("Auth.User.Role.getDefault") -> должно вернуть строку
    admin_connect, config = administrator_connect
    admin_connect: Optional[Connection]
    config: Optional[Config]
    test_default_role = await admin_connect.rpc("Auth.User.Role.getDefault")
    assert isinstance(test_default_role, str) and len(test_default_role) >= 0, "должен вернуть строку, больше нуля"

    # Значение роли хранится в конфигурации приложения auth_service. core.role.default - необходимо
    path = Path.cwd() / config.work_dir / config.service.config.name
    default_role_by_config = read_json_config(str(path))["core"]["role"]["default"]

    # Сравнить с тем что вернет метод
    assert default_role_by_config == test_default_role, "роли должны совпадать"
