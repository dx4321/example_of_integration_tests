import asyncio
import logging
import os
from distutils.file_util import copy_file
from json import JSONDecodeError
from pathlib import *
from typing import Optional, List

import pytest

from common import Config, read_json_config, write_json_config, get_environ, write_file, Connection, Group
from src.connections_test import ConnectionEventHandler


class Controller:
    def __init__(self, config: Config):
        """
        Выполняет развертывание и запуск приложения

        конструктор инициализирует конфиг теста
        deploy	Копирование конфига и файла БД
        path_config до настройки конфига
        run запуск программы
        """
        self.proc: Optional[asyncio.subprocess.Process] = None
        self.logger = None
        self.tasks_read_task = None
        self.timer = 1
        self.config = config

    def _copy_artifacts(self, to_folder_path: str):
        """
        Копировать артефакты
        """
        check_file = Path(to_folder_path).is_dir()  # проверить существует ли папка

        if not check_file:  # если ее нет, создать
            os.mkdir(to_folder_path)

        copy_file(str(self.config.service.execute), to_folder_path)  # добавить исполняемый файл в work_dir
        copy_file(str(self.config.service.db), to_folder_path)  # добавить файл базы данных в work_dir

        # патч до конфига который нужно перенести
        copy_file(str(self.config.service.config), to_folder_path)  # добавить конфигурацию приложения в work_dir

    def path_config(self):
        app_cfg = read_json_config(str(self.config.service.config))
        app_cfg['log']['dir'] = 'log'
        log_systems = app_cfg["log"]["systems"]
        for key in log_systems.keys():
            log_systems[key] = {"file": True, "level": "trace"}

        # Нужно перепатчить конфиг на дб воркдира
        app_cfg["core"]["db_path"] = str(Path.cwd().joinpath(self.config.work_dir, self.config.service.db.name))
        app_cfg["rpc"]["port"] = str(self.config.service.port)
        write_json_config(
            str(self.config.work_dir.joinpath(self.config.service.config.name)),
            app_cfg
        )

    def deploy(self):
        """ Функция, которая будет разворачивать рабочее окружение """

        try:
            self._copy_artifacts(str(self.config.work_dir))
        except Exception as e:
            raise e

    async def start(self):
        """ Запустить процесс """

        current_path = Path.cwd()
        current_dir = current_path.joinpath(self.config.work_dir)  # сформировать с кур дир через патч
        path_to_w_log = Path(current_dir, "log")
        self.proc = await asyncio.create_subprocess_exec(
            self.config.service.execute,
            self.config.service.param_key, self.config.service.config.name,
            cwd=str(current_dir),  # work dir з конфига
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        tasks = \
            [asyncio.create_task(read_task(str(path_to_w_log.joinpath("log_stdout.txt")), self.proc.stdout)),
             asyncio.create_task(read_task(str(path_to_w_log.joinpath("log_stderr.txt")), self.proc.stderr))]

        self.tasks_read_task = asyncio.gather(
            *tasks,
        )

    async def stop(self):
        await asyncio.sleep(self.timer)
        if self.proc.returncode is not None:
            return
        else:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=self.timer)
            except asyncio.TimeoutError:
                self.proc.kill()


async def read_task(file_name: str, stream: asyncio.StreamReader):
    while True:
        data = await stream.readline()
        if not data:
            return
        else:
            line = str(data.decode(encoding="CP866")).replace("\n", "")
            write_file(file_name, line)


@pytest.fixture
async def main():
    def _out_tests_for_exception(exception_str):
        pytest.exit(returncode=-1, reason=f"{exception_str}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    config_from_json: Optional[dict] = None
    path_jsonrpc_config: str = get_environ("JSONRPC_ITEST_CONFIG")  # получить конфиг из среды окружения

    try:
        config_from_json = read_json_config(path_jsonrpc_config)  # получить конфиг из файла config.json
    except TypeError as none_type:
        _ex_message = none_type
        _out_tests_for_exception(_ex_message)
    except FileNotFoundError as file_not_found:
        _ex_message = file_not_found
        _out_tests_for_exception(_ex_message)
    except JSONDecodeError as _ex_message:
        _ex_message = _ex_message
        _out_tests_for_exception(_ex_message)
    except Exception as none_type:
        _ex_message = none_type
        _out_tests_for_exception(_ex_message)
    config = Config(**config_from_json)  # распарсить словарь в модель Pydantic
    controller = Controller(config)

    try:
        controller.deploy()  # развернуть приложение
    except Exception as e:
        _ex_message = e
        _out_tests_for_exception(_ex_message)

    controller.path_config()  # пропатчить конфиг
    await controller.start()
    await asyncio.sleep(3)

    # передать управление тестам
    yield config

    await controller.stop()


@pytest.fixture
async def close_all_connect():
    """ Закрыть все соединения """
    yield

    for connect in Connection.ALL_CONNECTS:
        await connect.stop()

    Connection.ALL_CONNECTS.clear()


@pytest.fixture
async def administrator_connect(main, close_all_connect):
    """ Cоздает соединение администратора (Connection) """
    config = main
    admin = Connection(session=3000)
    await admin.start(config.service.port)
    await admin.login(config.data.default_user.name, config.data.default_user.password)
    yield admin, config


# создает сервисное соединение(Connection) - service_connect
# с настройкой appconfig.core.trasted
@pytest.fixture
async def service_connect(main):
    """ Cоздает сервисное соединение (Connection) """
    config = main
    path = Path.cwd() / config.work_dir / config.service.config.name
    _core_trusted = read_json_config(str(path))["core"]["trasted"][0]
    service_conn = Connection(session=_core_trusted)
    await service_conn.start(config.service.port)
    yield service_conn


@pytest.fixture
async def create_users(administrator_connect):
    """ Создать пользователей из конфига под админом """
    admin_connect, config = administrator_connect

    # Создает пользователей из config.data.users, с помощью "админского" соединения
    for user in config.data.users:
        await admin_connect.rpc('Auth.User.add', user.name, user.password)  # Добавляем пользователей
        await admin_connect.rpc("Auth.User.Role.set", user.name, user.role)  # добавляем роли
    yield admin_connect, config


@pytest.fixture
async def create_two_users(administrator_connect):
    """
    Соединение администратора создает пользователей(data.users), без проверки (два)
    """
    connection_admin, config = administrator_connect
    connection_admin: Connection
    config: Config

    two_users = config.data.users[:2]

    for user in two_users:
        await connection_admin.rpc('Auth.User.add', user.name, user.password)  # Добавляем пользователей
        await connection_admin.rpc("Auth.User.Role.set", user.name, user.role)  # добавляем роли
    yield connection_admin, config


@pytest.fixture
async def down_notify(create_users, close_all_connect):
    """ Дропнуть по группе оператора 1 .rpc("Auth.Connections.dropGroup", group_id) """
    admin_connect, config = create_users
    admin_connect: Optional[Connection]
    config: Optional[Config]

    #   Сделать 5 подключения пользователя с ролью operator.
    group_count_conn_5 = 5
    group = [Group(config.data.users[0], config.service.port)]
    start_user_sessions = 3001
    await group[0].create(group_count_conn_5, start_user_sessions)

    #   Сделать подключение 2-го пользователя
    operator_2_conn = Connection(session=(start_user_sessions + group_count_conn_5 + 1))
    await operator_2_conn.start(config.service.port)
    await operator_2_conn.login(config.data.users[1].name, config.data.users[1].password)

    #   Для оператора 1 - создать ивент хэндлер.
    operator1_evt = ConnectionEventHandler()
    operator1_evt.set_count_for_notification(4)

    #   Для админа создать ивент хэндлер
    admin_evt = ConnectionEventHandler()
    admin_evt.set_count_for_notification(4)

    #   Для оператора 2 - создать ивент хэндлер.
    operator2_evt = ConnectionEventHandler()

    #   Подписаться оператором 1 на уведомления
    for_register_trap = [[operator1_evt.on_down, {"Auth.Connections.Event.Down": List[int]}]]

    # привязать колбеки к Auth.Connections.Event.Up, к group[0].connection[0].rpc
    [group[0].connection[0].rpc.register_notification_trap(*reg) for reg in for_register_trap]

    #   Подписаться админом на уведомления
    for_register_trap = [[admin_evt.on_down, {"Auth.Connections.Event.Down": List[int]}]]
    [admin_connect.rpc.register_notification_trap(*reg) for reg in for_register_trap]

    #   Подписаться оператором 2 на уведомления
    for_register_trap = [[operator2_evt.on_down, {"Auth.Connections.Event.Down": List[int]}]]
    [operator_2_conn.rpc.register_notification_trap(*reg) for reg in for_register_trap]

    # Для сессии user[0] оператора1 - Подписаться на уведомления.
    await group[0].connection[0].rpc("Auth.Connections.watch", True)

    # Для админа подписаться на уведомления
    await admin_connect.rpc("Auth.Connections.watch", True)

    # Для оператора2 подписаться на уведомления
    await operator_2_conn.rpc("Auth.Connections.watch", True)

    yield group, operator1_evt, admin_evt, operator2_evt, config, admin_connect
