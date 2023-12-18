from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

__all__ = [
    "User",
    "Data",
    "Config",
    "DefaultUser",
    "Service"
]


class Service(BaseModel):
    execute: Path = Field(..., alias="execute")
    db: Path = Field(..., alias="db")
    config: Path = Field(..., alias="config")
    port: int = Field(..., alias="port")
    param_key: str = Field(..., alias="paramKey")


class DefaultUser(BaseModel):
    name: str = Field(..., alias="name")
    password: str = Field(..., alias="password")


class User(BaseModel):
    name: str = Field(..., alias="name")
    password: str = Field(..., alias="password")
    role: str = Field(..., alias="role")


class Data(BaseModel):
    default_user: DefaultUser = Field(..., alias="defaultUser")
    users: List[User] = Field(..., alias="users")


class Config(BaseModel):
    """
    Конфигурация на базе pydantic. BaseModel, реализует доп методы так же имеет предустановленные поля
    Методы формируют абсолютные пути используя ключ installDir
    """
    service: Service = Field(..., alias="service")
    work_dir: Path = Field(..., alias="workDir")
    data: Data = Field(..., alias="data")
