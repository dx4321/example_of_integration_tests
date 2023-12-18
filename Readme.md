# Интеграционные тесты для aut сервиса

# Требования
python3 >=3.8

# Развертывание рабочего окружения
 1. Создать рабочее окружение в дирректории на выбор пользователя ~<WORK_DIR>~
 1. Получить архив с собраным приложением auth_service, развернуть архив в дирректорию ~<INSTALL_DIR>~
 1. Скопировать конфигурацию приложения       ~<PROJECT_ROOT>~/distro_config/distro_all/conf/auth/config.json> в <INSTALL_DIR>/etc/auth.json
 1. Создать директорию разветывания(для auth_service) ~<DEPLOY_DIR>~
 1. создать venv:
    ```
    python -m venv .venv
    ```
    1. активировать venv
        ```
        .venv\Scripts\activate
        ```
    1. если надо обновить pip
        ```
        pip install --upgrade pip [--proxy http://<<<LOGIN>>>:<<<PASSWORD>>>@proxy.bolid.ru:3128]
        ```
    1. установить зависимости
        ```
        pip install -r requirements.txt [--proxy http://<<<LOGIN>>>:<<<PASSWORD>>>@proxy.bolid.ru:3128]
        ```

1. создать конфиг(теста) в рабочей дирректоии
    1. Скопировать прототип конфига <PROJECT_ROOT>\ITest\config.json <WORK_DIR>
    1. Указать поля конфига в блоке **service**
        ```
        "execute": <INSTALL_DIR>/bin/auth_service.exe",
        "config":  <INSTALL_DIR>/etc/auth.json",
        "db": "<INSTALL_DIR>/var/db/bolid/auth.db",
        "port": <Порт приложения auth>,
        "paramKey": "/c|-c"
        ```
    1. Указать поле workDir
       ```
       workDir: <DEPLOY_DIR>
       ```
    1. Установить переменную окружения **JSONRPC_ITEST_CONFIG** на созданный конфиг

# Запуск тестов

Запускаем все тесты
pytest <PROJECT_ROOT/ITest>

Параметры запуска
-s - выводить принты :)
--disable-pytest-warnings - отключить варнинги

Пример
    SET JSONRPC_ITEST_CONFIG=config.json
    pytest -s --disable-pytest-warnings
    pytest --junitxml=path # с запуском в формате pytest --junitxml=path
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++,
Чтобы создать файлы результатов, которые могут быть прочитаны Jenkins или другими серверами непрерывной интеграции,
используйте следующий вызов:

pytest --junitxml=path/result.xml

# Доп конфигурация тестов

Логи

+++ Раздел в разработке +++
Пропустить тест (пишем над тестом в коде)
Что-бы пропустить тест используем декоратор для функции
@pytest.mark.skip(reason="в настоящее время нет возможности проверить это")



