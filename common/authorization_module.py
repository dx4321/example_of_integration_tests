from pydantic import BaseModel, Field


class AuthConnectionsInfoUser(BaseModel):
    name: str = Field(..., alias="name")
    role: str = Field(..., alias="role")


class AuthConnectionsInfo(BaseModel):
    uid: int = Field(..., alias="uid")
    group_id: int = Field(..., alias="groupId")
    host: str = Field(..., alias="host")
    user_agent: str = Field(..., alias="userAgent")
    this: bool = Field(..., alias="self")
    auth_from: int = Field(..., alias="authFrom")
    user: AuthConnectionsInfoUser = Field(..., alias="user")
