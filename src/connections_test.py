import asyncio
from typing import List, Optional

import pytest
from bolid_jsonrpc import JsonRpcMethodCallError

from common import Connection, AuthConnectionsInfo, Group, ErrorCodes, Config


async def test_get_list(create_users):
    administrator_connect, config = create_users

    # создать по 1 соединению по данным config.data.users (операторские соединения - массив Connection)
    users_connects = []

    for client_session, user in enumerate(config.data.users):
        _conn = Connection(session=(3001 + int(client_session)))
        await _conn.start(config.service.port)
        token = await _conn.login(user.name, user.password)
        assert len(token) > 0, "токен не должен быть пустым"
        assert await _conn.rpc("Auth.User.whoami") == user.name
        users_connects.append(_conn)

    # admin_connect: запрос Auth.Connections.List - получает все N соединений.
    auth_data_list: list = [AuthConnectionsInfo(**info) for info in
                            await administrator_connect.rpc("Auth.Connections.list")]
    # сравнить имена
    name_in_auth = [name.user.name for name in auth_data_list]
    for user in config.data.users:
        assert user.name in name_in_auth, "Все пользователи должны быть в списке присоединенных"

    # создаем список операторских соединений
    operator_connects = []

    for user in config.data.users:
        if user.role == "operator":
            for user_con in users_connects:
                if user_con.name == user.name:
                    operator_connects.append(user_con)

    # Операторские соединения по очереди запрашивают Auth.Connections.List
    for connect in operator_connects:

        # получает в ответ одно соединение(массив с одним элементом rslt),
        rslt = AuthConnectionsInfo(**(await connect.rpc("Auth.Connections.list"))[0])
        assert rslt.this is True
        assert rslt.user.name == connect.name, "должны совпадать"

    # создать еще одно соединение с данными config.data.users[0]
    new_con = Connection(session=(3001 + len(users_connects)))
    await new_con.start(config.service.port)
    await new_con.login(
        config.data.users[0].name, config.data.users[0].password
    )
    users_connects.append(new_con)

    # Запросить list,
    two_el = [AuthConnectionsInfo(**info) for info in await new_con.rpc("Auth.Connections.list")]

    # получить два элемента
    assert len(two_el) == 2, "количество элементов листа должно быть 2"
    for info in two_el:

        # имена должны соответствовать
        assert info.user.name == config.data.users[0].name, "имена должны соответствовать"

    assert ((True is two_el[0].this and False is two_el[1].this) or
            (False is two_el[0].this and True is two_el[1].this)), "один из элементов должен содержать поле " \
                                                                   "this == True"


async def test_drop_by_id(create_users, close_all_connect):
    """
    test_drop_by_id
    """

    def _converter_to__auth_connections_info(list_vals: List[dict]):
        return [AuthConnectionsInfo(**info) for info in list_vals]

    admin_connect, config = create_users

    # создать по 1 соединению по данным config.data.users (операторские соединения), поместить в массив connection
    # создать список операторских соединений
    connection = []

    for client_session, user in enumerate(config.data.users):
        if user.role == "operator":
            _conn = Connection(session=(3001 + client_session))
            await _conn.start(config.service.port)
            await _conn.login(user.name, user.password)
            connection.append(_conn)

    # admin_connect: запрос Auth.Connections.list - получает все N соединений(account).
    all_n_connect: list = _converter_to__auth_connections_info(await admin_connect.rpc("Auth.Connections.list"))
    admin_uid = [inf for inf in all_n_connect if inf.user.name == "admin"][0].uid

    # запомнить uid админского соединения
    # connection[0]: запрос (Auth.Connections.list) - сохранить свой uid
    con_0_uid = _converter_to__auth_connections_info(await connection[0].rpc("Auth.Connections.list"))[0].uid

    # сonnection[0]:  Auth.Connection.dropById(uid) - результат False
    assert await connection[0].rpc("Auth.Connections.dropById", con_0_uid) is False

    # connection[0] (Auth.Session.whoami) - результат connection[0].name
    assert await connection[0].rpc(f"Auth.User.whoami") == connection[0].name

    # admin_connect: Auth.Connection.dropById(uid) - результат True
    assert await admin_connect.rpc(f"Auth.Connections.dropById", con_0_uid) is True

    # connection[0] (Auth.User.whoami) - сбой ACCESS_DENIED
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connection[0].rpc("Auth.User.whoami")
    assert ex.value.code == ErrorCodes.ACCESS_DENIED.value, "ждем Access Denied"

    # conection[1] (Auth.Session.dropById(админский id)) - сбой ACCESS_DENIED
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await connection[1].rpc("Auth.Connections.dropById", admin_uid)
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "получаем 5-ю ошибку " \
                                                             "Item not found"


async def test_drop_by_group(create_users, close_all_connect):
    admin_connect, config = create_users

    # Создать две группы соединений(Group)
    group_count_conn_1 = 5
    group_count_conn_2 = 3
    group = [
        Group(config.data.users[0], config.service.port),
        Group(config.data.users[1], config.service.port)
    ]
    start_user_sessions = 3001
    await group[0].create(group_count_conn_1, start_user_sessions)
    await group[1].create(group_count_conn_2, start_user_sessions + group_count_conn_1)

    # получить список соединений, через админа
    list_session_info = [AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")]
    for_test_5_id_users = [x.user.name for x in list_session_info if x.user.name == group[0].user.name]
    for_test_3_id_users = [x.user.name for x in list_session_info if x.user.name == group[1].user.name]
    assert len(for_test_5_id_users) == group_count_conn_1, "сверить что 5 элементов списка в группе (извлечь его " \
                                                           "groupId)"
    assert len(for_test_3_id_users) == group_count_conn_2, "сверить что 3 элементов списка в группе (извлечь его " \
                                                           "groupId)"
    group[0].set_id([x.group_id for x in list_session_info if x.user.name == group[0].user.name][0])
    group[1].set_id([x.group_id for x in list_session_info if x.user.name == group[1].user.name][0])

    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc('Auth.Connections.dropByGroup', group[1].id)
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "проверить что выходит ошибка ITEM_NOT_FOUND"

    # admin_connect запрос: Auth.Connections.dropByGroup(group[1].id) - вернет 3
    assert await admin_connect.rpc("Auth.Connections.dropByGroup", group[1].id) == 3, "вернет 3"
    list_session_info = [AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")]

    # admin_connect перезапросить список Auth.Connections.list -  вернет 6 соединений(админское и пять операторских)
    assert len(list_session_info) == 6, "должен вернуть 6 соединений"
    checker_admin_len_con = [info_admin for info_admin in list_session_info
                             if info_admin.user.name == admin_connect.name]
    assert len(checker_admin_len_con) == 1, "проверить что 1 соединение администратора"
    checker_operators_len_con = [operators_info for operators_info in list_session_info
                                 if operators_info.user.name != admin_connect.name]
    assert len(checker_operators_len_con) == 5, "проверить что 5 операторских"


async def test_drop_by_user(create_users, close_all_connect):

    # Создать две группы как в прошлом тесте
    #         5: config.data.user[0],
    #         3: config.data.user[1]
    admin_connect: Optional[Connection]
    config: Optional[Config]
    admin_connect, config = create_users

    # Создать две группы соединений(Group)
    group_count_conn_1 = 5
    group_count_conn_2 = 3
    group = [
        Group(config.data.users[0], config.service.port),
        Group(config.data.users[1], config.service.port)
    ]
    start_user_sessions = 3001
    await group[0].create(group_count_conn_1, start_user_sessions)
    await group[1].create(group_count_conn_2, start_user_sessions + group_count_conn_1)

    #           Создать отдельное соединение с данными config.data.user[0] - op_conn
    op_conn = Connection(session=(start_user_sessions + group_count_conn_1 + group_count_conn_2))
    await op_conn.start(config.service.port)
    await op_conn.login(config.data.users[0].name, config.data.users[0].password)

    #           Выгрузить список через admin_connect - результат 9
    list_session_info = [AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")]
    assert len(list_session_info) == 10, "Выгрузить список через admin_connect - результат 10"

    #           Попытаться грохнуть чужое соединение(без полномочий)
    list_session_info = [AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")]
    group[0].set_id([x.group_id for x in list_session_info if x.user.name == group[0].user.name][0])
    group[1].set_id([x.group_id for x in list_session_info if x.user.name == group[1].user.name][0])

    # group[0].connection[0].rpc('Auth.Connections.dropByUser', config.data.defaultUser.name) - ошибка ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc('Auth.Connections.dropByUser', config.data.default_user.name)
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "ITEM_NOT_FOUND"

    # # group[0].connection[0].rpc('Auth.Connections.dropByName', config.data.defaultUser) - ошибка ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc('Auth.Connections.dropByUser',
                                         config.data.users[1].name)
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "ITEM_NOT_FOUND"

    # op_conn Запрос ('Auth.Connections.dropByName', config.data.user[0]) - результат 5
    assert await op_conn.rpc("Auth.Connections.dropByUser", config.data.users[0].name)

    # ЗАРЕПОРТИТЬ - test_drop_by_user строка 250, попытка сделать запрос Auth.Connections.dropByUser с параметром user1
    # возвращает ошибку с 0 кодом и пустым сообщением.
    users_count = len([AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")])
    assert users_count == 5, "должно остаться 5 пользователей "

    #       Админское соединение Auth.Connections.dropByName(config.data.user[0].name) == 1
    assert await admin_connect.rpc("Auth.Connections.dropByUser", config.data.users[0].name) == 1

    #       Админское соединение перезапросить список соединений
    list_session_info = [AuthConnectionsInfo(**info) for info in await admin_connect.rpc("Auth.Connections.list")]

    # Должен остаться админ(с признаком this == True)
    assert [au_info for au_info in list_session_info if au_info.user.name == admin_connect.name][0].this is True

    # И 3 операторских соединения с именем config.data.user[1]
    assert len([operator_info for operator_info in list_session_info
                if operator_info.user.role == "operator"]) == 3, "Проверить что осталось 3 " \
                                                                 "операторских события "


class ConnectionEventHandler:
    def __init__(self):
        self.count: Optional[int] = None
        self.evt = asyncio.Event()
        self.elements_up_data: List[AuthConnectionsInfo] = []
        self.elements_down_data: List = []

    def clear(self):
        self.elements_up_data.clear()
        self.elements_down_data.clear()
        self.evt.clear()
        self.count = None

    def set_count_for_notification(self, count: int):
        self.count = count

    def on_up(self, _: str, data: AuthConnectionsInfo):
        self.elements_up_data.append(data)
        if self.count:
            if self.count == len(self.elements_up_data):
                self.evt.set()

    def on_down(self, _: str, data: int):
        self.elements_down_data.append(data)
        if self.count:
            if self.count == len(self.elements_down_data):
                self.evt.set()

    async def wait_down(self, timeout: int):
        await asyncio.wait_for(self.evt.wait(), timeout)

    async def wait_up(self, timeout: int):
        """ Вызвать clear() до вызова метода """
        await asyncio.wait_for(self.evt.wait(), timeout)


async def test_up_notify(create_users, close_all_connect):
    admin_connect, config = create_users
    admin_connect: Optional[Connection]
    config: Optional[Config]

    # Класс ConnectionEventHandler отслеживающий уведомления
    # (аналогичный, который использовали для Auth.Session.Up|Down)
    #     Auth.Connections.Event.Up
    #     Auth.Connections.Event.Down
    #             Вместо asyncio.Event использовать asyncio.Queue
    admin_evt = ConnectionEventHandler()  # "Создать экземпляр ConnectionEventHandler(admin_evt)

    # adm_subscribe = await admin_connect.rpc("Auth.Connections.watch", 1)
    # # подписаться на уведомления(админское соединение)"
    for_register_trap = [[admin_evt.on_up, {"Auth.Connections.Event.Up": AuthConnectionsInfo}]]
    [admin_connect.rpc.register_notification_trap(*reg) for reg in for_register_trap]
    adm_subscribe = await admin_connect.rpc("Auth.Connections.watch", True)
    assert adm_subscribe is True, "Админское соединение Auth.Connections.watch(true)"

    # Создать группу соединений(5) по c данными data.user[0]
    group_count_conn_5 = 5
    admin_evt.set_count_for_notification(group_count_conn_5)
    group = [Group(config.data.users[0], config.service.port)]
    start_user_sessions = 3001
    await group[0].create(group_count_conn_5, start_user_sessions)

    #               проверить, что в очереди admin_evt.up 5 элементов
    #               имя data.user[0].name
    await admin_evt.wait_up(3)
    assert len(admin_evt.elements_up_data) == group_count_conn_5, "проверить, что в очереди admin_evt.up 5 элементов"
    assert config.data.users[0].name == admin_evt.elements_up_data[-1].user.name, "имя data.user[0].name"
    admin_evt.clear()
    admin_evt.set_count_for_notification(2)

    # создать ConnectionEventHandle operator_evt,
    operator_evt = ConnectionEventHandler()
    operator_evt.set_count_for_notification(1)
    for_register_trap = [[operator_evt.on_up, {"Auth.Connections.Event.Up": AuthConnectionsInfo}]]

    # привязать колбеки к Auth.Connections.Event.Up, к group[0].connection[0].rpc
    [group[0].connection[0].rpc.register_notification_trap(*reg) for reg in for_register_trap]
    operator_subscribe = await group[0].connection[0].rpc("Auth.Connections.watch", True)
    assert operator_subscribe is True, "group[0].connection[0]: Auth.Connections.watch(true)"

    #  создать соединение с данными (data.user[0])
    new_conn_user_0 = Connection(session=(start_user_sessions + group_count_conn_5))
    await new_conn_user_0.start(config.service.port)
    await new_conn_user_0.login(config.data.users[0].name, config.data.users[0].password)

    # создать соединение с данными (data.user[1])
    new_conn_user_1 = Connection(session=(start_user_sessions + group_count_conn_5 + 1))
    await new_conn_user_1.start(config.service.port)
    await new_conn_user_1.login(config.data.users[1].name, config.data.users[1].password)

    # Проверить что
    #         operator_evt(1 элемент в очереди, имя data.user[0].name)
    #         admin_evt(2 элемента, [data.user[0].name, data.user[1].name])
    await operator_evt.wait_up(3)
    assert len(operator_evt.elements_up_data) == 1, "operator_evt(1 элемент в очереди, имя data.user[0].name)"
    assert operator_evt.elements_up_data[-1].user.name == config.data.users[0].name
    await admin_evt.wait_up(3)
    assert len(admin_evt.elements_up_data) == 2, "2 элемента"
    assert admin_evt.elements_up_data[0].user.name == config.data.users[0].name, "admin_evt == data.user[0].name"
    assert admin_evt.elements_up_data[1].user.name == config.data.users[1].name, "admin_evt == data.user[1].name"
    operator_evt.clear()
    operator_evt.set_count_for_notification(1)
    admin_evt.clear()
    admin_evt.set_count_for_notification(0)

    admin_off_subscribe = await admin_connect.rpc("Auth.Connections.watch", False)
    assert admin_off_subscribe is True, "проверить что мы отписались от уведомлений, " \
                                        "должно вернуться True (изменение применилось)"

    # Создать соединение с данными data.user[0]
    new_conn_user_3 = Connection(session=(start_user_sessions + group_count_conn_5 + 2))
    await new_conn_user_3.start(config.service.port)
    await new_conn_user_3.login(config.data.users[0].name, config.data.users[0].password)

    # проверить что в очереди
    #         operator_evt(1 элемент в очереди, имя data.user[0].name)
    #         admin_evt  пустая
    await operator_evt.wait_up(3)
    assert len(operator_evt.elements_up_data) == 1, "operator_evt(1 элемент в очереди, имя data.user[0].name)"
    assert len(admin_evt.elements_up_data) == 0, "admin_evt  пустая"


async def test_down_notify_by_user(down_notify):
    group, operator1_evt, admin_evt, operator2_evt, _, _ = down_notify

    operator_1_id_name_5 = group[0].user.name

    # Дропнуть по имени оператора 1 .rpc("Auth.Connections.dropByUser", "user_name")
    await group[0].connection[0].rpc("Auth.Connections.dropByUser", operator_1_id_name_5)

    await operator1_evt.wait_down(4)
    assert len(operator1_evt.elements_down_data) == 4, "Проверить что у оператора 1 - пришло 4 уведомления"

    # проверки - что Для админа прилетают уведомления Event.down
    await admin_evt.wait_down(4)
    assert len(admin_evt.elements_down_data) == 4, "Проверить что админу пришло 4 события Event.Down"

    # проверка, что для юзера 2 не прилетают уведомления Event.down
    await asyncio.sleep(2)
    assert len(operator2_evt.elements_down_data) == 0, "проверить что второму пользователю не пришли уведомления " \
                                                       "после действий первого пользователя"


async def test_down_notify_by_group(down_notify):
    group, operator1_evt, admin_evt, operator2_evt, _, _ = down_notify

    operator_1_group_id: int = [
        info for info in
        [AuthConnectionsInfo(**obj) for obj in await group[0].connection[3].rpc("Auth.Connections.list")]
        if info.this is True
    ][0].group_id

    # Отключить сессию 0 оператора 1 .stop
    await group[0].connection[4].stop()

    # Дропнуть по группе оператора 1 .rpc("Auth.Connections.dropGroup", group_id)
    await group[0].connection[0].rpc("Auth.Connections.dropByGroup", operator_1_group_id)

    await operator1_evt.wait_down(4)
    assert len(operator1_evt.elements_down_data) == 4, "Проверить что у оператора 1 - пришло 4 уведомления"

    # проверки - что Для админа прилетают уведомления Event.down
    await admin_evt.wait_down(4)
    assert len(admin_evt.elements_down_data) == 4, "Проверить что админу пришло 4 события Event.Down"

    # проверка, что для юзера 2 не прилетают уведомления Event.down
    await asyncio.sleep(2)
    assert len(operator2_evt.elements_down_data) == 0, "Проверить что второму пользователю не пришли уведомления " \
                                                       "после действий первого пользователя"


async def test_down_notify_logout(down_notify):
    group, operator1_evt, admin_evt, operator2_evt, _, _ = down_notify

    # От логиниться всем соединениям кроме 0 - группы оператора 1 logout
    operator1_evt.set_count_for_notification(0)

    # От логиниться от всех соединений
    test = await group[0].connection[1].rpc("Auth.Session.logout")
    assert test is True

    # проверки - что Для админа прилетают уведомления Event.down
    await admin_evt.wait_down(4)
    assert len(admin_evt.elements_down_data) == 4, "Проверить что админу пришло 4 события Event.Down"

    # проверка, что для юзера 2 не прилетают уведомления Event.down
    await asyncio.sleep(2)
    assert len(operator2_evt.elements_down_data) == 0, "проверить что второму пользователю не пришли уведомления " \
                                                       "после действий первого пользователя"
    assert len(operator1_evt.elements_down_data) == 0, "Проверить что у оператора 1 - пришло 1 уведомления"
    # погасить свое и проверить что пришел false


async def test_down_notify_stop(down_notify):
    group, operator1_evt, admin_evt, operator2_evt, _, _ = down_notify

    # Отключить сессию 0 оператора 1 .stop
    i = 4
    while i > 0:
        await group[0].connection[i].stop()
        i -= 1

    await operator1_evt.wait_down(4)
    assert len(operator1_evt.elements_down_data) == 4, "Проверить что у оператора 1 - пришло 4 уведомления"

    # проверки - что Для админа прилетают уведомления Event.down
    await admin_evt.wait_down(4)
    assert len(admin_evt.elements_down_data) == 4, "Проверить что админу пришло 4 события Event.Down"

    # проверка, что для юзера 2 не прилетают уведомления Event.down
    await asyncio.sleep(2)
    assert len(operator2_evt.elements_down_data) == 0, "проверить что второму пользователю не пришли уведомления " \
                                                       "после действий первого пользователя"


async def test_down_notify_by_id(down_notify):
    group, operator1_evt, admin_evt, operator2_evt, config, admin_connect = down_notify

    # на входе: 1 админское соединение, 5 пользовательских в группе оператора 1
    async def get_current_uid_session(connection: Connection):
        return [
            info for info in
            [AuthConnectionsInfo(**obj) for obj in await connection.rpc("Auth.Connections.list")]
            if info.this is True
        ][0].uid

    async def get_drop_a_non_existent_connection(admin_conn: Connection):
        all_list_uid = [info.uid for info in
                        [AuthConnectionsInfo(**obj) for obj in await admin_conn.rpc("Auth.Connections.list")]]
        return sorted(all_list_uid)[0] - 1

    # Указать для оператора 1, что ждем 1 уведомление
    operator1_evt.set_count_for_notification(3)

    # Создать еще одну админскую (2-ю сессию)
    admin2_conn = Connection(session=3056)
    await admin2_conn.start(config.service.port)
    await admin2_conn.login(config.data.default_user.name, config.data.default_user.password)

    # дропнуть ее другим админом - + 1 (для админа1)
    drop_admin2 = await admin_connect.rpc("Auth.Connections.dropById", await get_current_uid_session(admin2_conn))
    assert drop_admin2 is True, "Проверить что ок"

    # дропнуть юзером -> админа - ошибка ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc("Auth.Connections.dropById", await get_current_uid_session(admin_connect))
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "проверить что выходит ошибка ITEM_NOT_FOUND"

    # админом дропнуть юзера по id [4] -> True
    drop_user_conn = await admin_connect.rpc("Auth.Connections.dropById",
                                             await get_current_uid_session(group[0].connection[4]))
    assert drop_user_conn is True, "проверить что результат ок"

    # админом дропнуть юзера по id [3] -> True
    drop_user_conn = await admin_connect.rpc("Auth.Connections.dropById",
                                             await get_current_uid_session(group[0].connection[3]))
    assert drop_user_conn is True, "проверить что результат ок"

    # Юзером дропнуть не существующего пользователя -> ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc(
            "Auth.Connections.dropById", await get_drop_a_non_existent_connection(admin_connect))
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "проверить что выходит ошибка ITEM_NOT_FOUND"

    # Админом дропнуть не существующего пользователя -> ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await admin_connect.rpc(
            "Auth.Connections.dropById", await get_drop_a_non_existent_connection(admin_connect))
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "проверить что выходит ошибка ITEM_NOT_FOUND"

    # создать 2-ий коннект оператора 2
    operator_2_2_conn = Connection(session=3060)
    await operator_2_2_conn.start(config.service.port)
    await operator_2_2_conn.login(config.data.users[1].name, config.data.users[1].password)

    # дропнуть юзером другого 2-ий коннект оператора 2 (operator_2_2_conn) -> ITEM_NOT_FOUND
    with pytest.raises(JsonRpcMethodCallError) as ex:
        await group[0].connection[0].rpc("Auth.Connections.dropById", await get_current_uid_session(operator_2_2_conn))
    assert ex.value.code == ErrorCodes.ITEM_NOT_FOUND.value, "проверить что выходит ошибка ITEM_NOT_FOUND"

    # в группе соединений оператора 1 [0] : соединением - сбросить соединение 2
    req = await group[0].connection[0].rpc("Auth.Connections.dropById",
                                           await get_current_uid_session(group[0].connection[1]))
    assert req is True, "проверить что ок"

    await operator1_evt.wait_down(4)
    assert len(operator1_evt.elements_down_data) == 3, "Проверить что у оператора 1 - пришло 4 уведомления"

    # проверки - что Для админа прилетают уведомления Event.down
    await admin_evt.wait_down(4)
    assert len(admin_evt.elements_down_data) == 4, "Проверить что админу пришло 4 события Event.Down"

    # проверка, что для юзера 2 не прилетают уведомления Event.down
    await asyncio.sleep(2)
    assert len(operator2_evt.elements_down_data) == 0, "проверить что второму пользователю не пришли уведомления " \
                                                       "после действий первого пользователя"

    # погасить свое и проверить что пришел false
    await group[0].connection[0].rpc("Auth.Connections.dropById", await get_current_uid_session(group[0].connection[0]))
