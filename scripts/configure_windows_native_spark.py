"""Verify the local Hadoop binaries and configure a Windows child process or user."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
HADOOP_HOME = ROOT / 'artifacts/windows-native-hadoop/hadoop-3.3.4'
EXPECTED_SHA256 = {
    'winutils.exe': '7aea6b168b64366d613345df97087032ccd1a9c539d78b6ad27c6787445af1d6',
    'hadoop.dll': '6ad5d53074692eb540c64b20a6ddd3bae9295c8829c26c8d0f3db407257f5c69',
}


def contains_path(path, directory):
    """Compare Windows PATH entries without changing their spelling or expansion."""
    expected = os.path.normcase(os.path.normpath(directory))
    return any(os.path.normcase(os.path.normpath(os.path.expandvars(entry.strip().strip('"'))))
               == expected for entry in path.split(os.pathsep) if entry.strip())


def persist_user(home, bin_path):
    """Append the directory to HKCU PATH while retaining its original registry type."""
    import ctypes
    from ctypes import wintypes
    import winreg

    access = winreg.KEY_READ | winreg.KEY_WRITE
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Environment', 0, access) as settings:
        try:
            path, kind = winreg.QueryValueEx(settings, 'Path')
        except FileNotFoundError:
            path, kind = '', winreg.REG_EXPAND_SZ
        if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
            raise ValueError('User PATH is not a Windows string value')
        if not contains_path(path, bin_path):
            separator = os.pathsep if path and not path.endswith(os.pathsep) else ''
            winreg.SetValueEx(settings, 'Path', 0, kind, path + separator + bin_path)
        winreg.SetValueEx(settings, 'HADOOP_HOME', 0, winreg.REG_SZ, home)

    # Ask Windows shell applications to refresh user environment settings.
    broadcast = ctypes.windll.user32.SendMessageTimeoutW
    broadcast.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPCWSTR,
                          wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    broadcast.restype = wintypes.LPARAM
    broadcast(0xFFFF, 0x001A, 0, 'Environment', 0x0002, 1000, None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--persist-user', action='store_true', help='Also save HADOOP_HOME and PATH for this Windows user.')
    parser.add_argument('command', nargs=argparse.REMAINDER, help='Optional command to run with the configured environment.')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This setup is for Windows.')

    home = str(HADOOP_HOME)
    bin_path = str(HADOOP_HOME / 'bin')
    for name, expected in EXPECTED_SHA256.items():
        path = HADOOP_HOME / 'bin' / name
        with path.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
        if actual != expected:
            raise ValueError(f'Hash mismatch for {path}. See reports/WINDOWS_NATIVE_SPARK_FIX.md.')

    if args.persist_user:
        persist_user(home, bin_path)
    environment = dict(os.environ, HADOOP_HOME=home)
    if not contains_path(environment.get('PATH', ''), bin_path):
        environment['PATH'] = bin_path + os.pathsep + environment.get('PATH', '')

    print(f'HADOOP_HOME={home}', flush=True)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if command:
        return subprocess.run(command, env=environment).returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
