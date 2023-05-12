from typing import Optional

from pydantic import BaseModel

from api.conf.base_config import BaseConfig
from utils.common import singleton_with_lock

_TYPE_CHECKING = False


class CommonSetting(BaseModel):
    print_sql: bool = False
    create_initial_admin_user: bool = True
    initial_admin_user_username: str = 'admin'
    initial_admin_user_password: str = 'password'
    sync_conversations_on_startup: bool = True
    sync_conversations_regularly: bool = True


class HttpSetting(BaseModel):
    host: str = '127.0.0.1'
    port: int = 8000
    cors_allow_origins: list = ['http://localhost', 'http://127.0.0.1']


class DataSetting(BaseModel):
    data_dir: str = './data'
    database_url: str = 'sqlite+aiosqlite:///data/database.db'
    mongodb_url: str = 'mongodb://cws:password@localhost:27017'
    run_migration: bool = False


class AuthSetting(BaseModel):
    jwt_secret: str = 'MODIFY_THIS_TO_RANDOM_SECRET'
    jwt_lifetime_seconds: int = 86400
    cookie_max_age: int = 86400
    cookie_name: str = 'user_auth'
    user_secret: str = 'MODIFY_THIS_TO_RANDOM_SECRET'


class RevChatGPTSetting(BaseModel):
    is_plus_account: bool = False
    chatgpt_base_url: Optional[str] = None
    ask_timeout: int = 600


class APISetting(BaseModel):
    openai_base_url: str = 'https://api.openai.com/v1/'
    connect_timeout: int = 5
    read_timeout: int = 60


class LogSetting(BaseModel):
    log_dir: str = 'logs'
    console_log_level: str = 'INFO'


class StatsSetting(BaseModel):
    request_counter_time_window: int = 30 * 24 * 60 * 60  # 30 days
    request_counts_interval: int = 30 * 60  # 30 minutes
    ask_log_time_window: int = 604800  # 7 days


class ConfigModel(BaseModel):
    common: CommonSetting = CommonSetting()
    http: HttpSetting = HttpSetting()
    data: DataSetting = DataSetting()
    auth: AuthSetting = AuthSetting()
    revchatgpt: RevChatGPTSetting = RevChatGPTSetting()
    api: APISetting = APISetting()
    log: LogSetting = LogSetting()
    stats: StatsSetting = StatsSetting()

    class Config:
        underscore_attrs_are_private = True


@singleton_with_lock
class Config(BaseConfig[ConfigModel]):
    if _TYPE_CHECKING:
        common: CommonSetting = CommonSetting()
        http: HttpSetting = HttpSetting()
        data: DataSetting = DataSetting()
        auth: AuthSetting = AuthSetting()
        revchatgpt: RevChatGPTSetting = RevChatGPTSetting()
        api: APISetting = APISetting()
        log: LogSetting = LogSetting()
        stats: StatsSetting = StatsSetting()

    def __init__(self):
        super().__init__(ConfigModel, "config.yaml")


if __name__ == '__main__':
    # 用于生成默认配置文件
    cfg = Config()
    cfg._model = ConfigModel()
    cfg._config_path = './config.example.yaml'
    cfg.save()