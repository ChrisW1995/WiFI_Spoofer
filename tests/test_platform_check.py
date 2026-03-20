import pytest
from unittest.mock import patch, MagicMock

from wifi_cut.platform_check import check_root


def test_check_root_fails_when_not_root_macos():
    with patch("wifi_cut.platform_check.sys.platform", "darwin"):
        with patch("os.geteuid", return_value=1000):
            with pytest.raises(SystemExit):
                check_root()


def test_check_root_passes_when_root_macos():
    with patch("wifi_cut.platform_check.sys.platform", "darwin"):
        with patch("os.geteuid", return_value=0):
            check_root()


def test_check_root_fails_when_not_admin_windows():
    mock_ctypes = MagicMock()
    mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 0
    with patch("wifi_cut.platform_check.sys.platform", "win32"):
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            with pytest.raises(SystemExit):
                check_root()


def test_check_root_passes_when_admin_windows():
    mock_ctypes = MagicMock()
    mock_ctypes.windll.shell32.IsUserAnAdmin.return_value = 1
    with patch("wifi_cut.platform_check.sys.platform", "win32"):
        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            check_root()
