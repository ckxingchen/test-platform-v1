import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.modules.executors.models import Environment
from app.modules.executors.schemas import EnvironmentIn
from app.modules.objects.agent_packages.models import AgentPackage
from app.modules.objects.frameworks.package import inspect_framework_package
from app.modules.users.schemas import UserCreate
from app.platform.db.base import Base
from app.shared.files.paths import validate_relative_path
from app.shared.resources.schemas import ResourceCreate
from agent.utils.runtime import extract_archive
from sqlalchemy import create_engine



class PathValidationTests(unittest.TestCase):
    def test_accepts_project_structure(self):
        self.assertEqual(validate_relative_path(r"testcase\登录\成功.yaml"), "testcase/登录/成功.yaml")
        self.assertEqual(validate_relative_path("config/配置文件.ini"), "config/配置文件.ini")

    def test_rejects_escape_and_unknown_root(self):
        for value in ("../secret", "testcase/../../secret", "D:/secret", "/other/file"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_relative_path(value)

    def test_extracts_windows_zip_paths_on_linux(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            archive = root / "framework.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr(r"runmain\cli.py", "print('ok')")
            extract_archive(archive, root / "output")
            self.assertTrue((root / "output" / "runmain" / "cli.py").is_file())


class EnvironmentSchemaTests(unittest.TestCase):
    def test_allows_platform_server_as_executor(self):
        """执行器允许使用平台服务器地址与 SSH 凭据。"""

        data = EnvironmentIn(name="local-agent", host="192.168.14.100", ssh_username="root", ssh_password="secret")
        self.assertEqual(data.host, "192.168.14.100")
        self.assertEqual(data.ssh_port, 22)

    def test_rejects_unspecified_host(self):
        """未指定地址不能作为执行器主机标识。"""

        with self.assertRaises(ValueError):
            EnvironmentIn(name="invalid-agent", host="0.0.0.0", ssh_username="root", ssh_password="secret")

    def test_accepts_windows_agent_home(self):
        """Windows 安装目录支持盘符绝对路径。"""

        data = EnvironmentIn(name="win-agent", host="192.168.1.20", ssh_username="administrator", ssh_password="secret", agent_home="D:\\kw-agent")
        self.assertEqual(data.agent_home, "D:\\kw-agent")

    def test_rejects_relative_agent_home(self):
        """Agent 安装目录必须是绝对路径。"""

        with self.assertRaises(ValueError):
            EnvironmentIn(name="bad-agent", host="192.168.1.20", ssh_username="root", ssh_password="secret", agent_home="kw-agent")


class CreateSchemaTests(unittest.TestCase):
    def test_accepts_and_trims_chinese_project_name(self):
        """测试项目名称允许中文并自动清理首尾空白。"""

        self.assertEqual(ResourceCreate(name="  登录自动化  ").name, "登录自动化")

    def test_rejects_project_path_separator(self):
        """项目显示名称不能伪装为对象存储路径。"""

        with self.assertRaises(ValueError):
            ResourceCreate(name="project/test")

    def test_trims_username_before_length_validation(self):
        """用户名应按清理后的实际内容执行长度校验。"""

        self.assertEqual(UserCreate(username="  tester  ", password="123456").username, "tester")
        with self.assertRaises(ValueError):
            UserCreate(username=" a ", password="123456")


class PackageInspectionTests(unittest.TestCase):
    def test_reads_framework_entry(self):
        """不依赖 framework.json，仅凭目录结构与传入的入口路径即可生成部署元数据。"""

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("x86-centos/runmain/cli.py", "print('ok')")
        result = inspect_framework_package(stream.getvalue(), "framework.zip", "runmain/cli.py")
        self.assertEqual(result["archive_root"], "x86-centos")
        self.assertEqual(result["runner_path"], "runmain/cli.py")

    def test_counts_files(self):
        """目录解析器应统计归档内文件数量。"""

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("bundle/driver/kw-cli", b"binary")
            archive.writestr("bundle/testsuits/a.yaml", b"a")
            archive.writestr("bundle/testsuits/b.yaml", b"b")
        result = inspect_framework_package(stream.getvalue(), "framework.zip", "driver/kw-cli")
        self.assertEqual(result["file_count"], 3)

    def test_rejects_missing_entry(self):
        """入口文件不存在时应报错。"""

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("bundle/driver/kw-cli", b"binary")
        with self.assertRaises(ValueError):
            inspect_framework_package(stream.getvalue(), "framework.zip", "driver/not-exist")

    def test_rejects_absolute_archive_path(self):
        """上传包不得借助绝对路径写出远程执行器工作目录。"""

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("/driver/kw-cli", b"binary")
        with self.assertRaises(ValueError):
            inspect_framework_package(stream.getvalue(), "unsafe.zip", "driver/kw-cli")


class AgentPackageInspectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def _package(self, os_name):
        from app.modules.objects.agent_packages.service import inspect_agent_package

        stream = io.BytesIO()
        entry = "bin/kw-agent.exe" if os_name == "windows" else "bin/kw-agent"
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(entry, b"binary")
            archive.writestr("bin/_internal/lib.dll", b"lib")
        return inspect_agent_package(stream.getvalue(), "agent.zip", os_name)

    def test_accepts_linux_package(self):
        result = self._package("linux")
        self.assertEqual(result["entry"], "bin/kw-agent")
        self.assertEqual(result["file_count"], 2)

    def test_accepts_windows_package(self):
        result = self._package("windows")
        self.assertEqual(result["entry"], "bin/kw-agent.exe")

    def test_rejects_missing_entry(self):
        from app.modules.objects.agent_packages.service import inspect_agent_package
        from app.shared.errors import ServiceError

        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("kw-agent", b"binary")
        with self.assertRaises(ServiceError):
            inspect_agent_package(stream.getvalue(), "agent.zip", "linux")

    def test_agent_package_unique_constraint(self):
        """(name, os, arch) 唯一：同平台重复插入应违反唯一约束。"""

        from sqlalchemy.exc import IntegrityError
        from sqlalchemy.orm import Session

        with Session(self.engine) as db:
            db.add(AgentPackage(name="kw-agent", os="linux", arch="x86_64", file_name="agent.tar.gz", object_key="k", sha256="a" * 64, size=1))
            db.commit()
            db.add(AgentPackage(name="kw-agent", os="linux", arch="x86_64", file_name="agent.tar.gz", object_key="k2", sha256="b" * 64, size=1))
            with self.assertRaises(IntegrityError):
                db.commit()

    def test_executor_allows_null_framework(self):
        """新架构框架在 Agent 上线后部署，framework_id 允许为空。"""

        from sqlalchemy.orm import Session

        with Session(self.engine) as db:
            item = Environment(name="nullable-fw", host="127.0.0.1", ssh_port=22, agent_home="/opt/kw-agent")
            db.add(item)
            db.commit()
            self.assertIsNone(item.framework_id)
            self.assertEqual(item.agent_status, "pending")
            self.assertEqual(item.framework_status, "not_deployed")


if __name__ == "__main__":
    unittest.main()
