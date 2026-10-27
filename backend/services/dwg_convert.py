# -*- coding: utf-8 -*-
"""DWG -> DXF 转换服务。

优先使用本机安装的 ODA File Converter（免费，命令行批处理）：
    ODAFileConverter.exe <输入目录> <输出目录> ACAD2013 DXF 0 1 input.dwg
找不到转换器时抛出 ConverterMissing，由路由层返回可操作的提示。
"""
from __future__ import annotations

import ctypes
import glob
import os
import shutil
import subprocess
import tempfile
import threading

# 输出 DXF 版本（dxf-parser 对 R2010~R2018 ASCII DXF 兼容良好）
_OUT_VERSION = "ACAD2013"

# ODA 转换器单实例串行，避免多个大图纸同时转换抢占资源
_CONV_LOCK = threading.Lock()


def _hide_process_windows(pid: int, stop: threading.Event) -> None:
    """后台轮询，把 ODA 弹出的 Qt 界面窗口隐藏（命令行批处理时无需用户看到）。"""
    user32 = ctypes.windll.user32
    SW_HIDE = 0
    hwnds = set()

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def _enum(hwnd, _lparam):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            user32.ShowWindow(hwnd, SW_HIDE)
            hwnds.add(hwnd)
        return True

    while not stop.wait(0.5):
        try:
            user32.EnumWindows(_enum, None)
        except Exception:
            pass


class ConverterMissing(RuntimeError):
    """本机未安装 ODA File Converter。"""


class ConverterError(RuntimeError):
    """转换执行失败。"""


def find_oda() -> str | None:
    """定位 ODAFileConverter.exe。

    查找顺序：环境变量 → 系统安装位置 → 注册表。
    """
    env = os.environ.get("ODA_FILE_CONVERTER")
    if env and os.path.isfile(env):
        return env
    # 只查找本机安装目录；本项目不随软件分发 ODA。
    candidates = [
        r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
        r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe",
        r"C:\Program Files\ODAFileConverter *\ODAFileConverter.exe",
        os.path.join(os.path.expanduser("~"), "ODAFileConverter", "ODAFileConverter.exe"),
    ]
    for pat in candidates:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    # 注册表 Uninstall 键兜底
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ):
                try:
                    with winreg.OpenKey(hive, sub) as root:
                        i = 0
                        while True:
                            try:
                                key_name = winreg.EnumKey(root, i)
                                i += 1
                            except OSError:
                                break
                            if "ODA" not in key_name and "File Converter" not in key_name:
                                continue
                            try:
                                with winreg.OpenKey(root, key_name) as k:
                                    loc, _ = winreg.QueryValueEx(k, "InstallLocation")
                                exe = os.path.join(loc, "ODAFileConverter.exe")
                                if loc and os.path.isfile(exe):
                                    return exe
                            except OSError:
                                continue
                except OSError:
                    continue
    except ImportError:
        pass
    return None


def convert_file(dwg_path: str, timeout: int = 300) -> tuple[str, str]:
    """把单个 DWG 转成 ASCII DXF。

    返回 (dxf_path, work_dir)：work_dir 由调用方在用完后清理。
    """
    exe = find_oda()
    if not exe:
        raise ConverterMissing(
            "未检测到 ODA File Converter。请安装后重试，或在 CAD 中把图纸另存为 DXF 后直接导入。"
        )
    if not os.path.isfile(dwg_path):
        raise ConverterError(f"源文件不存在：{dwg_path}")

    work = tempfile.mkdtemp(prefix="agv_dwg_")
    in_dir = os.path.join(work, "in")
    out_dir = os.path.join(work, "out")
    os.makedirs(in_dir)
    os.makedirs(out_dir)
    # 统一用 ASCII 文件名，规避中文/空格在命令行参数里的编码问题
    in_file = os.path.join(in_dir, "input.dwg")
    shutil.copy2(dwg_path, in_file)

    args = [exe, in_dir, out_dir, _OUT_VERSION, "DXF", "0", "1", "input.dwg"]
    out_file = os.path.join(out_dir, "input.dxf")
    # 尽量不让 Qt 窗口闪现
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    with _CONV_LOCK:
        stop_hide = threading.Event()
        hide_thread = None
        try:
            proc = subprocess.Popen(
                args, cwd=work, startupinfo=si,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            shutil.rmtree(work, ignore_errors=True)
            raise
        try:
            hide_thread = threading.Thread(
                target=_hide_process_windows, args=(proc.pid, stop_hide), daemon=True)
            hide_thread.start()
            ret = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            shutil.rmtree(work, ignore_errors=True)
            raise ConverterError(
                f"转换超时（>{timeout}s），图纸可能过大或转换器弹窗阻塞。")
        except Exception:
            proc.kill()
            shutil.rmtree(work, ignore_errors=True)
            raise
        finally:
            stop_hide.set()
        if not os.path.isfile(out_file):
            shutil.rmtree(work, ignore_errors=True)
            raise ConverterError(f"转换器未生成 DXF（exit={ret}）。")
        with open(out_file, "rb") as f:
            head = f.read(20000)
        if b"$ACAD" not in head:
            shutil.rmtree(work, ignore_errors=True)
            raise ConverterError("生成的文件不是有效的 ASCII DXF。")
        return out_file, work
