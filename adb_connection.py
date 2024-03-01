import subprocess
import os
import sys
import re
import shlex
import atexit
import logging

if sys.platform == 'win32':
    from utils import placebo as timeout

else:
    from wrapt_timeout_decorator import timeout

from config import CODEPATH


class ADBConnection:
    UNIX = ['linux', 'linux2', 'darwin']
    MODES = {
        'download': 'download',
        'bootloader': 'bootloader',
        'recovery': 'recovery',
        'sideload': 'sideload',
        'sideload-auto-reboot': 'sideload-auto-reboot'
    }

    def __init__(self, **kwargs):
        self.startupinfo = None
        self.adb_bin = None
        self.is_unix = sys.platform in self.UNIX
        self.rmr = b'\r\n'
        self._run_opt = None
        self.setup_logging()
        self.setup()
        self._is_adb_out_post_v5 = False

        atexit.register(self.kill)

    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    def setup(self):
        self.logger.debug(f'Platform: {sys.platform}')

        if self.is_unix:
            self.adb_bin = self._get_adb_bin()

            self.logger.debug(f'Using adb binary: {self.adb_bin}')

        else:
            self.adb_bin = os.path.join(CODEPATH, 'bin', 'adb.exe')
            self._win_startupinfo()

        if not self.adb_bin or not os.path.exists(self.adb_bin):
            self.logger.warning('ADB binary is not found!')

            raise ADBConnectionError('ADB binary is not found!')

        self._is_adb_out_post_v5 = self._adb_has_exec()

    def _win_startupinfo(self):
        self.startupinfo = subprocess.STARTUPINFO()
        self.startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.rmr = b'\r\r\n'

    def _opt_use_capture(self):
        return tuple(sys.version_info) >= (3, 7)

    @property
    def run_opt(self):
        if not self._run_opt:
            opt = {'shell': False, 'startupinfo': self.startupinfo}

            if self._opt_use_capture():
                opt['capture_output'] = True

            else:
                opt['stdout'] = subprocess.PIPE

            self._run_opt = opt

        return self._run_opt

    @timeout(60 * 60 * 2, use_signals=False)
    def adb(self, cmd, binary=False, su=False, _for_out=False, **kwargs):
        cmd = self._get_adb_cmd(cmd, su, _for_out)
        
        run = subprocess.run([self.adb_bin, *cmd], **self.run_opt)

        return self._return_run_output(run, binary)

    def adb_out(self, cmd, binary=False, su=False, **kwargs):
        return self.adb(cmd, binary=binary, su=su, _for_out=True, **kwargs)

    def _get_adb_cmd(self, cmd, su, _for_out):
        if isinstance(cmd, str):
            cmd = self.split_cmd(cmd)

        if su:
            cmd.insert(0, 'su -c')

        if _for_out:
            cmd.insert(0, 'exec-out' if self._is_adb_out_post_v5 else 'shell')

        self.logger.debug(f'ADB cmd: {cmd}')

        return cmd

    def _return_run_output(self, run: subprocess.CompletedProcess, binary):
        if run.stdout and run.returncode == 0:
            if binary:
                if self._is_adb_out_post_v5:
                    return run.stdout
                
                return self.unstrip(run.stdout)

        return run.stdout.decode().strip()

    def unstrip(self, data):
        return re.sub(self.rmr, b'\n', data)

    def cmditer(self, cmd):
        process = subprocess.Popen(
            self.split_cmd(cmd),
            shell=False,
            startupinfo=self.startupinfo,
            stdout=subprocess.PIPE
        )

        while True:
            output = process.stdout.readline()

            if output == b'' and process.poll() is not None:
                break

            if output:
                yield output.decode().rstrip()

        rc = process.poll()

        return rc

    def device(self):
        dev = self.adb('devices', timeout=5)

        if dev:
            dev = dev.split('\n')

            if len(dev) > 1:
                dev = dev[1].split('\t')

                return dev

        else:
            self.logger.error('ADB binary cannot be used to check for connected devices!')

        return None, None

    def start(self):
        self.adb('start-server', timeout=10)

    def kill(self):
        self.adb('kill-server', timeout=5)

    @staticmethod
    def _file_regex(fp):
        return re.compile(f'^{fp.replace("*", "(.+?)")}$')

    def exists(self, file_path):
        file_path_strict = self.strict_name(file_path)
        file_remote = self.adb_out(f'ls {file_path_strict}')

        if not file_remote:
            return None

        if re.match(self._file_regex(file_path), file_remote):
            return file_remote

    def get_file(self, file_path):
        file_path_strict = self.strict_name(file_path)

        data = self.adb_out(f'cat {file_path_strict}', binary=True)

        return data

    def pull_file(self, file_path, dst_path):
        file_path_strict = re.sub(' ', r'\ ', file_path)
        dst_path_strict = re.sub(' ', r'\ ', dst_path)

        self.adb(f'pull {file_path_strict} "{dst_path_strict}"')

    def get_size(self, file_path):
        file_path_strict = self.strict_name(file_path)

        size_functions = [
            lambda: self.adb_out(f'stat -c %s {file_path_strict}'),
            lambda: self.adb_out(f'ls -nl {file_path_strict}').split()[3],
            lambda: self.adb_out(f'wc -c < {file_path_strict}')
        ]

        for size_function in size_functions:
            size = size_function()

            if size and size.isdigit():
                return int(size)

        self.logger.debug(f'Size Error for: {file_path}')

        return -1

    @timeout(30, use_signals=False)
    def cmd_shell(self, cmd, code = False):
        self.logger.debug(f'Shell cmd: {cmd}')

        run = subprocess.run(self.split_cmd(cmd), **self.run_opt)

        if code:
            return run.returncode

        if run.stdout:
            return run.stdout.decode().strip()

    def _get_adb_bin(self):
        return self.cmd_shell('which adb') or None

    def _adb_has_exec(self):
        cmd = f'{self.adb_bin} exec-out id'

        return self.cmd_shell(cmd, code=True) == 0

    def split_cmd(self, cmd):
        if self.is_unix:
            return shlex.split(cmd)

        return cmd.split(' ')

    def reboot(self, mode=None):
        mode = self.MODES.get(mode, '')

        self.logger.info(f'Rebooting in {mode}.')
        self.adb(f'reboot {mode}', timeout=20)

    def __call__(self, cmd, *args):
        return self.adb(cmd, *args)

    @staticmethod
    def strict_name(file_path):
        file_name = os.path.split(file_path)[1]

        if ' ' in file_name:
            return file_path.replace(file_name, repr(file_name).replace(' ', r'\ '))

        return file_path


class ADBConnectionError(Exception):
    pass
