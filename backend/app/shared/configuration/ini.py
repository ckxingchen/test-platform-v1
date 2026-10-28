"""任务运行 INI 配置校验工具。"""

import configparser


def validate_ini_content(content: str) -> None:
    """校验内容是至少包含一个节的合法 INI。"""

    parser = configparser.ConfigParser()
    try:
        parser.read_string(content)
    except configparser.Error as exc:
        raise ValueError(f"INI 配置格式错误：{exc}") from exc
    if not parser.sections():
        raise ValueError("INI 配置至少需要一个 section")
