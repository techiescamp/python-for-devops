#!/bin/sh
# -*- mode: Python -*-

# The installer (this current file) is executed initially as a shell script.
# Here we either "exec python serverpilot-installer" or exit if we can't find a
# version of python this script is compatible with.
""":"
install_on_el5() {
  echo "***************************************************************************"
  echo "It looks like you're using RHEL/CentOS 5. ServerPilot only supports Ubuntu."
  echo
  echo "https://serverpilot.io/community/articles/server-requirements.html"
  echo "***************************************************************************"
  exit 1
}

# Some distros only have a "python3" command by default.
# Others may have Python 2.4 as "python" but with another version installed
# installed alongside it.
for py in python3 python27 python2.7 python26 python2.6 ; do
    which $py >/dev/null 2>&1 && exec $py "$0" "$@"
done
if which python >/dev/null 2>&1 ; then
    if [ "`python -V 2>&1`" == "Python 2.4.3" ]; then
        install_on_el5
        exit 0
    fi
    exec python "$0" "$@"
fi
echo "Unable to install ServerPilot. Python not found."
exit 1
":"""

"""
ServerPilot installer. See https://serverpilot.io
"""

__copyright__ = 'Copyright (c) 2020, Less Bits, Inc.'
__license__ = 'Proprietary.'

import sys

# If Python is pre-2.7, this is an unsupported distro/version. Multiple parts
# of this installer rely on 2.7, so abort here with a useful error message.
if sys.version_info[:2] < (2, 7):
    print('*' * 80)
    print("Sorry, you can't connect this server to ServerPilot.")
    print('')
    print("You'll need to use Ubuntu 18.04, 20.04, or 22.04.")
    print('')
    print("More info here:")
    print('')
    print('https://serverpilot.io/community/articles/ubuntu-control-panel.html')
    print('*' * 80)
    sys.exit(1)

import argparse
import base64
try:
    import ConfigParser as configparser
except:
    import configparser
import datetime
import errno
import hashlib
import json
import os
import platform
import pwd
import shutil
import socket
import subprocess
import time
import tempfile
import traceback
try:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
except ImportError:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError


# Python 3 renamed raw_input to input.
if sys.version_info[0] >= 3:
    raw_input = input


API_URL = 'https://api.serverpilot.io/v1'

SERVERPILOT_CONF_DIR = '/etc/serverpilot'

AGENT_CONF_FILE = SERVERPILOT_CONF_DIR + '/agent.conf'

SP_VERSION = 1

REPO_URL = 'https://download.serverpilot.io/ubuntu'

INSTALLER_LOG_FILE = '/var/log/serverpilot/install.log'

INSTALLER_VERSION = '1'

DISTRO_UBUNTU = 'ubuntu'
DISTRO_UBUNTU_RELS = ['18.04', '20.04', '22.04']
CHANNEL_STABLE = 'stable'

DISTRO_UBUNTU_CODENAMES = {
    '12.04': 'precise',
    '14.04': 'trusty',
    '16.04': 'xenial',
    '18.04': 'bionic',
    '20.04': 'focal',
    '22.04': 'jammy',
}

RELEASES_KEYRING_URL = 'https://download.serverpilot.io/serverpilot.gpg'
RELEASES_KEYRING_FILE = '/usr/share/keyrings/serverpilot.gpg'
RELEASES_KEYRING_FILE_SHA256 = 'b357636ac39a4f554a242f29b5997094b3d0f746c69a3768991dbfbe3b553589'


class ShellColor():
    # TODO: use the tput command to get the color sequences.
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)
    RESET_SEQ = '\033[0m'
    FOREGROUND_COLOR_SEQ = '\033[1;3{}m'
#    BOLD_SEQ = '\033[1m'
    BOLD_SEQ = '\033[1'

    def __init__(self):
        if self._is_bash():
            # Don't use color if stdout isn't a tty (e.g. it has been redirected
            # to a log file).
            self.use_color = subprocess.call("tty -s <&1", shell=True) == 0
        else:
            self.use_color = False

    def _is_bash(self):
        # Only detecting bash is probably overly-restrictive for now.
        shell = os.environ.get('SHELL')
        if not shell:
            return False
        if not shell:
            return False
        return os.path.basename(shell) == 'bash'
        # tty -s <&1

    def _color(self, msg, colorcode):
        if self.use_color:
            return self.FOREGROUND_COLOR_SEQ.format(colorcode) + msg + self.RESET_SEQ
        else:
            return msg

    def red(self, msg):
        return self._color(msg, self.RED)

    def green(self, msg):
        return self._color(msg, self.GREEN)

    def yellow(self, msg):
        return self._color(msg, self.YELLOW)

    def bold(self, msg):
        """Use bold instead of white because white foreground will be unreadable
           if the user has a white background on their terminal."""
        return self._color(msg, self.BOLD_SEQ)


color = ShellColor()


class InstallError(Exception):
    pass


class UserQuit(InstallError):
    pass


class UnsupportedDistro(InstallError):
    pass


class UnsupportedArch(InstallError):
    pass


class UnsupportedKernel(InstallError):
    pass


class NotEnoughMemory(InstallError):
    pass


class SysuserAlreadyExists(InstallError):
    pass


class AlreadyInstalled(InstallError):
    pass


class CmdError(InstallError):
    pass


def cmd(args, input=None):
    if input is not None:
        stdin = subprocess.PIPE
    else:
        stdin = None
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, stdin=stdin)
    except OSError as exc:
        raise_cmd_error(args, None, None, str(exc))
    stdout, stderr = p.communicate(input)
    stdout = stdout.strip()
    stderr = stderr.strip()
    if p.returncode != 0:
        raise_cmd_error(args, p.returncode, stdout, stderr)
    return stdout


def check_exec_cmd(args):
    retval = exec_cmd(args)
    if retval != 0:
        raise CmdError('The command "{}" exited with non-zero status {}.'.format(
            ' '.join(args), retval))


def exec_cmd(args):
    '''Forks a child process which exec's the command and waits for the child
       to exit. Returns the exit status of the child.
    '''
    if os.fork() == 0:
        os.execvp(args[0], args)
    else:
        try:
            pid, exitinfo = os.wait()
        except KeyboardInterrupt:
            return -1
        if os.WIFEXITED(exitinfo):
            return os.WEXITSTATUS(exitinfo)
        else:
            # It may have been killed.
            return -1


def format_cmd_output(retval, stdout, stderr):
    lines = []
    lines.append('Return value: {0}'.format(retval))
    lines.append('stdout: {0}'.format(stdout))
    lines.append('stderr: {0}'.format(stderr))
    return os.linesep.join(lines)


def raise_cmd_error(args, retval, stdout, stderr):
    msg = 'Error executing command: {0}\n'.format(args)
    msg += format_cmd_output(retval, stdout, stderr)
    raise CmdError(msg)


def read_file_lines(path):
    f = open(path)
    try:
        return f.readlines()
    finally:
        f.close()


def write_file(path, contents, mode=0o600):
    fd, temppath = tempfile.mkstemp()
    try:
        os.close(fd)
        f = open(temppath, 'w')
        try:
            f.write(contents)
        finally:
            f.close()
        os.chmod(temppath, mode)
        shutil.move(temppath, path)
    except:
        os.remove(temppath)
        raise


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else: raise


def write_to_log_file(str):
    logdir = os.path.dirname(INSTALLER_LOG_FILE)
    if not os.path.exists(logdir):
        mkdir_p(logdir)
    with open(INSTALLER_LOG_FILE, 'a') as f:
        f.write(str + '\n')


def read_log_file():
    try:
        with open(INSTALLER_LOG_FILE, 'r') as f:
            return f.read()
    except Exception as exc:
        return None


def user_exists(user):
    try:
        pwd.getpwnam(user)
    except KeyError:
        return False
    return True


class Installer(object):

    def __init__(self):
        self.starttime = datetime.datetime.utcnow()
        self.distroname = None
        self.distroversion = None
        self.arch = None
        self.channel = CHANNEL_STABLE
        self.serverid = None
        self.apikey = None
        self.skip_server_info = False
        self.skip_mysql_check = False
        self.skip_webserver_check = False
        self.skip_install = False

    def report(self, status):
        data = {'status': status}
        data['hostname'] = socket.gethostname()
        data['distroname'] = self.distroname
        data['distroversion'] = self.distroversion
        data['arch'] = self.arch
        data['serverid'] = self.serverid
        data['log'] = read_log_file()
        data['channel'] = self.channel
        data['elapsedtime'] = (datetime.datetime.utcnow() - self.starttime).total_seconds()
        data['env'] = str(os.environ)
        try:
            urlopen(self.insecure_api_request('/installer/report', data=data))
        except Exception as exc:
            self.record_error('Failed to send report', exc)

    def insecure_api_request(self, api_path, data=None):
        """Make an API request that doesn't use SSL securely.

        Python 2.x does a terrible job of secure SSL. So, this method should
        only be used for requests that don't need to be secure.
        """
        headers = {}
        if data is not None:
            data = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        return Request(API_URL + api_path, data, headers)

    def insecure_hashedkey_api_request(self, api_path, data=None):
        """Make an API request that doesn't use SSL securely.

        Python 2.x does a terrible job of secure SSL. So, this method should
        only be used for requests that don't need to be secure.
        """
        headers = {}
        if data is not None:
            data = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        hashedkey = hashlib.sha256(self.apikey.encode()).hexdigest()
        authval = '{}:{}'.format(self.serverid, hashedkey)
        b64authval = base64.b64encode(authval.encode()).decode()
        headers['Authorization'] = 'Basic {}'.format(b64authval)
        return Request(API_URL + api_path, data, headers)

    def record_error(self, msg, exc=None):
        write_to_log_file(msg)
        if exc:
            write_to_log_file(traceback.format_exc())
        write_to_log_file('-' * 80)

    def run(self):
        try:
            self._run()
        except SystemExit:
            self.record_error('Exited due to SystemExit')
            self.report('exit')
            raise
        except UserQuit:
            self.record_error('Exited due to UserQuit')
            self.report('abort')
            raise
        except InstallError as exc:
            self.record_error('', exc)
            self.report('fail')
            raise
        except Exception as exc:
            self.record_error('', exc)
            self.report('error')
            raise
        else:
            self.report('success')

    def _run(self):
        os.umask(0o077)
        self.check_running_as_root()
        write_to_log_file('=' * 80)
        displaytime = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        write_to_log_file('Starting installation. {0}\n'.format(displaytime))
        try:
            self.get_distro_and_version()
            self.check_architecture()
            self.check_kernel()
            self.check_memory()
            self.check_serverpilot_user()
            self.check_mysql()
            self.check_apache()
            self.check_nginx()
            # Do this last so conf file not written unless all checks pass.
            self.ask_server_ident()
        except KeyboardInterrupt:
            write_to_log_file('Quiting installer.')
            print('Quiting installer.')
            raise UserQuit
        self.install_packages()
        self.show_finished_message()

    def get_distro_and_version(self):
        try:
            if os.path.exists('/etc/lsb-release'):
                lines = read_file_lines('/etc/lsb-release')
                # TODO: don't assume the lines are in a specific order.
                if lines[0].startswith('DISTRIB_ID='):
                    self.distroname = lines[0].split('=')[1].strip().lower()
                if lines[1].startswith('DISTRIB_RELEASE='):
                    self.distroversion = lines[1].split('=')[1].strip()
                if self.distroname != DISTRO_UBUNTU:
                    raise UnsupportedDistro(self.distroname)
                if self.distroversion not in DISTRO_UBUNTU_RELS:
                    raise UnsupportedDistro(self.distroversion)
            else:
                raise UnsupportedDistro
        except UnsupportedDistro:
            write_to_log_file('Unsupported operating system.')
            print(color.red('*' * 80))
            print(color.bold("Sorry, you can't connect this server to ServerPilot."))
            print('')
            print(color.bold("You'll need to use Ubuntu 18.04, 20.04, or 22.04."))
            print('')
            print(color.bold("More info here:"))
            print('')
            print(color.bold('https://serverpilot.io/community/articles/ubuntu-control-panel.html'))
            print(color.red('*' * 80))
            raise

    def check_running_as_root(self):
        if os.getuid() != 0:
            print(color.red('The ServerPilot installer must be run as root. Please run the exact installer command we provided.'))
            sys.exit(1)

    def check_architecture(self):
        self.arch = platform.machine()
        if self.arch != 'x86_64':
            write_to_log_file('Unsupported architecture: {}'.format(self.arch))
            print(color.red('ServerPilot only supports 64-bit servers.'))
            print(color.red('Your server appears to be {0}.'.format(self.arch)))
            raise UnsupportedArch

    def check_kernel(self):
        kernel = platform.uname()[2]
        kernelparts = kernel.split('.')
        kernelmajor = int(kernelparts[0])
        kernelminor = int(kernelparts[1])
        if (kernelmajor, kernelminor) < (3, 2):
            write_to_log_file('Unsupported kernel version: {}'.format(kernel))
            print(color.red('ServerPilot supports only Linux kernel versions >= 3.2.'))
            print(color.red('Your system is running {0}.'.format(kernel)))
            print(color.red('This can happen when running a server on OpenVZ with an old host kernel.'))
            print(color.red('You should use a non-OpenVZ server (e.g. KVM or Xen) or switch providers.'))
            raise UnsupportedKernel

    def check_memory(self):
        with open('/proc/meminfo') as f:
            for line in f.readlines():
                if 'MemTotal:' in line:
                    memtotal = int(line.split()[1]) / 1024
                    break
            else:
                print(color.red('Could not determine available memory.'))
                sys.exit(1)
        # Allow a little less than 256 just in case a system is close.
        if memtotal < 230:
            write_to_log_file('Not enough system memory: {} MB'.format(memtotal))
            print(color.red('ServerPilot only supports systems with at least 256 MB of memory.'))
            print(color.red('Your system has {0} MB.'.format(memtotal)))
            raise NotEnoughMemory

    def check_serverpilot_user(self):
        if user_exists('serverpilot'):
            write_to_log_file('System user "serverpilot" already exists.')
            print(color.red('System user "serverpilot" already exists.'))
            raise SysuserAlreadyExists

    def ask_server_ident(self):
        if self.skip_server_info:
            return
        if os.path.exists(AGENT_CONF_FILE):
            write_to_log_file('File {} already exists.'.format(AGENT_CONF_FILE))
            print(color.red('You have already run the ServerPilot installer on this server.'))
            raise AlreadyInstalled
        if not self.serverid or not self.apikey:
            write_to_log_file('Asking for server ID and API key.')
            print(color.green("What's this server's ID and API key?"))
            print(color.bold("You can get these by logging in to https://serverpilot.io and"))
            print(color.bold("creating a new server. After you create the server, you will"))
            print(color.bold("be shown the ID and API key to enter here."))
        while True:
            if not self.serverid or not self.apikey:
                sys.stdout.write(color.yellow('Server ID: '))
                self.serverid = raw_input()
                sys.stdout.write(color.yellow('API key: '))
                self.apikey = raw_input()
            try:
                write_to_log_file('Testing apikey for serverid {}'.format(self.serverid))
                url = '/authtest/server/hashedkey'
                req = self.insecure_hashedkey_api_request(url)
                urlopen(req)
            except HTTPError as e:
                if e.code == 401:
                    write_to_log_file('Invalid Server ID and API key.')
                    print(color.red('Invalid Server ID and API key. Please enter them again.'))
                    self.serverid = None
                    self.apikey = None
                    continue
                else:
                    raise
            break
        mkdir_p(SERVERPILOT_CONF_DIR)
        with open(AGENT_CONF_FILE, 'w') as f:
            config = configparser.ConfigParser()
            config.add_section('server')
            config.set('server', 'id', self.serverid)
            config.set('server', 'apikey', self.apikey)
            config.write(f)
        print('')

    def check_mysql(self):
        if self.skip_mysql_check:
            return

        try:
            stdout = cmd(['dpkg-query', '-W', '-f=${db:Status-Abbrev}', 'mysql-server']).decode().strip()
        except CmdError:
            pass
        else:
            if stdout != 'un':
                write_to_log_file('MySQL server is already installed.')
                print(color.red('MySQL server is already installed. You must install ServerPilot on a fresh server.'))
                raise InstallError("mysql-server is already installed.")

    def check_apache(self):
        if self.skip_webserver_check:
            return

        try:
            stdout = cmd(['dpkg-query', '-W', '-f=${db:Status-Abbrev}', 'apache2']).decode().strip()
        except CmdError:
            pass
        else:
            if stdout != 'un':
                write_to_log_file('Apache is already installed.')
                print(color.red('Apache is already installed. You must install ServerPilot on a fresh server.'))
                raise InstallError("apache is already installed.")

    def check_nginx(self):
        if self.skip_webserver_check:
            return

        try:
            stdout = cmd(['dpkg-query', '-W', '-f=${db:Status-Abbrev}', 'nginx']).decode().strip()
        except CmdError:
            pass
        else:
            if stdout != 'un':
                write_to_log_file('Nginx is already installed.')
                print(color.red('Nginx is already installed. You must install ServerPilot on a fresh server.'))
                raise InstallError("nginx is already installed.")

    def add_repo(self):
        def add_repo_deb():
            cmd(['wget', '-O', RELEASES_KEYRING_FILE, RELEASES_KEYRING_URL])
            os.chmod(RELEASES_KEYRING_FILE, 0o644)
            sha256sum = cmd(['sha256sum', RELEASES_KEYRING_FILE]).decode().split()[0]
            if sha256sum != RELEASES_KEYRING_FILE_SHA256:
                raise InstallError("Keyring SHA256 checksum is {}, expected {}".format(
                    sha256sum, RELEASES_KEYRING_FILE_SHA256))

            options = '[signed-by={keyring}]'.format(keyring=RELEASES_KEYRING_FILE)
            path = '/etc/apt/sources.list.d/serverpilot.list'
            contents = 'deb {options} {url} {codename} main'.format(
                options=options, url=REPO_URL,
                codename=DISTRO_UBUNTU_CODENAMES[self.distroversion])
            write_file(path, contents + os.linesep, 0o644)

        if self.distroname in [DISTRO_UBUNTU]:
            add_repo_deb()
        else:
            raise InstallError('Unexpected distro: {0}'.format(self.distroname))

    def install_packages(self):
        if self.skip_install:
            return

        def wait_for_apt():
            # Wait for up to 10 minutes for existing apt/dpkg commands to finish.
            try:
                for i in range(100):
                    stdout = cmd(['ps', '-e', '-o', 'comm']).decode()
                    if 'apt' not in stdout and 'dpkg' not in stdout:
                        break
                    print('Waiting for existing apt or dpkg process to exit.')
                    write_to_log_file('Waiting for existing apt or dpkg process to exit.')
                    time.sleep(6)
                else:
                    raise InstallError('Giving up on waiting for existing apt or dpkg to exit.')
            except CmdError as exc:
                write_to_log_file('Unable to check for running apt or dpkg: {0}'.format(exc))

        def install_packages_deb():
            os.putenv('DEBIAN_FRONTEND', 'noninteractive')

            try:
                wait_for_apt()
                check_exec_cmd(['apt-get', 'update'])

                # Try to fix any broken dependencies before proceeding.
                wait_for_apt()
                check_exec_cmd(['apt-get', '--assume-yes', '--fix-broken', 'install'])

                # Some systems don't have apt-transport-https installed by default.
                wait_for_apt()
                try:
                    check_exec_cmd(['apt-get', '--assume-yes', 'install', 'apt-transport-https'])
                except CmdError:
                    # If we still weren't able to avoid a race with anything else installing
                    # packages, retry once here.
                    write_to_log_file('Unable to install apt-transport-https. Will try again.')
                    time.sleep(10)
                    wait_for_apt()
                    check_exec_cmd(['apt-get', '--assume-yes', 'install', 'apt-transport-https'])

                wait_for_apt()
                check_exec_cmd(['apt-get', '--assume-yes', 'install', 'wget'])

                self.add_repo()

                # Now update again since we just added our repo.
                wait_for_apt()
                check_exec_cmd(['apt-get', 'update'])

                wait_for_apt()
                pkgs = ['sp-serverpilot-agent']
                check_exec_cmd(['apt-get', '--assume-yes', 'install'] + pkgs)
            except CmdError as exc:
                print(color.red(str(exc)))
                raise

        # We're actually serious that we only support Ubuntu LTS. If you are
        # looking at these lines of code trying to hack around our installer
        # telling you we don't support the OS you are trying to install on,
        # please take us seriously and just use Ubuntu LTS. Thanks!
        if (self.distroname == DISTRO_UBUNTU and
            self.distroversion in DISTRO_UBUNTU_RELS):
            install_packages_deb()
        else:
            raise NotImplementedError

    def show_finished_message(self):
        write_to_log_file('Installation complete.')
        print(color.green('*' * 80))
        print(color.bold('ServerPilot is now configuring and securing your server.'))
        print(color.bold('Do not stop/resize/reboot your server right now.'))
        print('')
        print(color.bold('You can manage this server at https://manage.serverpilot.io'))
        print(color.green('*' * 80))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server-id')
    parser.add_argument('--server-apikey')
    parser.add_argument('--skip-server-info', action='store_true')
    parser.add_argument('--skip-mysql-check', action='store_true')
    parser.add_argument('--skip-webserver-check', action='store_true')
    parser.add_argument('--skip-install', action='store_true')
    args = parser.parse_args()

    installer = Installer()
    installer.serverid = args.server_id
    installer.apikey = args.server_apikey
    installer.skip_server_info = args.skip_server_info
    installer.skip_mysql_check = args.skip_mysql_check
    installer.skip_webserver_check = args.skip_webserver_check
    installer.skip_install = args.skip_install
    try:
        installer.run()
    except Exception:
        sys.exit(1)


if __name__ == '__main__':
    main()
