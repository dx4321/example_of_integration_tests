import os
import json

__all__ = [
    'get_environ',
    'read_json_config',
    'write_file',
    'write_json_config',
]


def get_environ(param: str):
    """ Вернуть значение переменной окружения """
    return os.environ.get(param)


def read_json_config(path_to_file: str) -> dict:
    """ Прочитать конфиг"""
    with open(path_to_file, 'r', encoding="UTF-8") as f:
        conf = json.load(f)
    return conf


def write_file(path_to_file: str, line: str, param="a"):
    with open(path_to_file, param, encoding="UTF-8") as f:
        f.write(line)


def write_json_config(path_to_file: str, conf: dict):
    with open(path_to_file, 'w', encoding="UTF-8") as f:
        json.dump(conf, f, indent=4, sort_keys=True)
