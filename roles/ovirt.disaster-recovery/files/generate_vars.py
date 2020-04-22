#!/usr/bin/python3
try:
    from ConfigParser import SafeConfigParser
except ModuleNotFoundError:
    from configparser import SafeConfigParser

import logging
import os.path
import subprocess
import sys
from six.moves import input

import ovirtsdk4 as sdk

from bcolors import bcolors


INFO = bcolors.OKGREEN
INPUT = bcolors.OKGREEN
WARN = bcolors.WARNING
FAIL = bcolors.FAIL
END = bcolors.ENDC
PREFIX = "[Generate Mapping File] "
CA_DEF = '/etc/pki/ovirt-engine/ca.pem'
USERNAME_DEF = 'admin@internal'
SITE_DEF = 'http://localhost:8080/ovirt-engine/api'
VAR_DEF = "/var/lib/ovirt-ansible-disaster-recovery/mapping_vars.yml"
PLAY_DEF = "../examples/dr_play.yml"


class GenerateMappingFile():

    def run(self, conf_file, log_file, log_level):
        log = self._set_log(log_file, log_level)
        log.info("Start generate variable mapping file "
                 "for oVirt ansible disaster recovery")
        dr_tag = "generate_mapping"
        site, username, password, ca_file, var_file_path, _ansible_play = \
            self._init_vars(conf_file, log)
        log.info("Site address: %s \n"
                 "username: %s \n"
                 "password: *******\n"
                 "ca file location: %s \n"
                 "output file location: %s \n"
                 "ansible play location: %s ",
                 site, username, ca_file, var_file_path, _ansible_play)
        if not self._validate_connection(log,
                                         site,
                                         username,
                                         password,
                                         ca_file):
            self._print_error(log)
            exit()
        command = "site=" + site + " username=" + username + " password=" + \
            password + " ca=" + ca_file + " var_file=" + var_file_path
        cmd = []
        cmd.append("ansible-playbook")
        cmd.append(_ansible_play)
        cmd.append("-t")
        cmd.append(dr_tag)
        cmd.append("-e")
        cmd.append(command)
        cmd.append("-vvvvv")
        log.info("Executing command %s", ' '.join(map(str, cmd)))
        if log_file is not None and log_file != '':
            self._log_to_file(log_file, cmd)
        else:
            self._log_to_console(cmd, log)

        if not os.path.isfile(var_file_path):
            log.error("Can not find output file in '%s'.", var_file_path)
            self._print_error(log)
            exit()
        log.info("Var file location: '%s'", var_file_path)
        self._print_success(log)

    def _log_to_file(self, log_file, cmd):
        with open(log_file, "a") as f:
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True)
            for line in iter(proc.stdout.readline, ''):
                f.write(line)
            for line in iter(proc.stderr.readline, ''):
                f.write(line)
                print("%s%s%s" % (FAIL,
                                  line,
                                  END))

    def _log_to_console(self, cmd, log):
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True)
        for line in iter(proc.stdout.readline, ''):
            log.debug(line)
        for line in iter(proc.stderr.readline, ''):
            log.error(line)

    def _set_log(self, log_file, log_level):
        logger = logging.getLogger(PREFIX)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s %(message)s')
        if log_file is not None and log_file != '':
            hdlr = logging.FileHandler(log_file)
            hdlr.setFormatter(formatter)
            logger.addHandler(hdlr)
        else:
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        logger.setLevel(log_level)
        return logger

    def _print_success(self, log):
        msg = "Finished generating variable mapping file " \
              "for oVirt ansible disaster recovery."
        log.info(msg)
        print("%s%s%s%s" % (INFO, PREFIX, msg, END))

    def _print_error(self, log):
        msg = "Failed to generate var file."
        log.error(msg)
        print("%s%s%s%s" % (FAIL, PREFIX, msg, END))

    def _connect_sdk(self, url, username, password, ca):
        connection = sdk.Connection(
            url=url,
            username=username,
            password=password,
            ca_file=ca,
        )
        return connection

    def _validate_connection(self,
                             log,
                             url,
                             username,
                             password,
                             ca):
        conn = None
        try:
            conn = self._connect_sdk(url,
                                     username,
                                     password,
                                     ca)
            dcs_service = conn.system_service().data_centers_service()
            dcs_service.list()
        except Exception as e:
            msg = "Connection to setup has failed. " \
                  "Please check your cradentials: " \
                  "\n URL: " + url \
                  + "\n USER: " + username \
                  + "\n CA file: " + ca
            log.error(msg)
            print("%s%s%s%s" % (FAIL, PREFIX, msg, END))
            log.error("Error: %s", e)
            if conn:
                conn.close()
            return False
        return True

    def _validate_output_file_exists(self, fname, log):
        _dir = os.path.dirname(fname)
        if _dir != '' and not os.path.exists(_dir):
            log.warn("Path '%s' does not exists. Create folder",
                     _dir)
            os.makedirs(_dir)
        if os.path.isfile(fname):
            valid = {"yes": True, "y": True, "ye": True,
                     "no": False, "n": False}
            ans = input("%s%sThe output file '%s' "
                        "already exists. "
                        "Would you like to override it (y,n)?%s "
                        % (WARN, PREFIX, fname, END))
            while True:
                ans = ans.lower()
                if ans in valid:
                    if not valid[ans]:
                        msg = "Failed to create output file. " \
                              "File could not be overriden."
                        log.error(msg)
                        print("%s%s%s%s" % (FAIL, PREFIX, msg, END))
                        sys.exit(0)
                    break
                else:
                    ans = input("%s%sPlease respond with 'yes' or 'no': %s"
                                % (INPUT, PREFIX, END))
            try:
                os.remove(fname)
            except OSError:
                log.error("File %s could not be replaced.", fname)
                print("%s%sFile %s could not be replaced.%s"
                      % (FAIL,
                         PREFIX,
                         fname,
                         END))
                sys.exit(0)

    def _init_vars(self, conf_file, log):
        """ Declare constants """
        _SECTION = 'generate_vars'
        _SITE = 'site'
        _USERNAME = 'username'
        _PASSWORD = 'password'
        _CA_FILE = 'ca_file'
        # TODO: Must have full path, should add relative path
        _OUTPUT_FILE = 'output_file'
        _ANSIBLE_PLAY = 'ansible_play'

        """ Declare varialbles """
        site, username, password, ca_file, output_file, ansible_play = '', \
            '', '', '', '', ''
        settings = SafeConfigParser()
        settings.read(conf_file)
        if _SECTION not in settings.sections():
            settings.add_section(_SECTION)
        if not settings.has_option(_SECTION, _SITE):
            settings.set(_SECTION, _SITE, '')
        if not settings.has_option(_SECTION, _USERNAME):
            settings.set(_SECTION, _USERNAME, '')
        if not settings.has_option(_SECTION, _PASSWORD):
            settings.set(_SECTION, _PASSWORD, '')
        if not settings.has_option(_SECTION, _CA_FILE):
            settings.set(_SECTION, _CA_FILE, '')
        if not settings.has_option(_SECTION, _OUTPUT_FILE):
            settings.set(_SECTION, _OUTPUT_FILE, '')
        if not settings.has_option(_SECTION, _ANSIBLE_PLAY):
            settings.set(_SECTION, _ANSIBLE_PLAY, '')
        site = settings.get(_SECTION, _SITE,
                            vars=DefaultOption(settings,
                                               _SECTION,
                                               site=None))
        username = settings.get(_SECTION, _USERNAME,
                                vars=DefaultOption(settings,
                                                   _SECTION,
                                                   username=None))
        password = settings.get(_SECTION, _PASSWORD,
                                vars=DefaultOption(settings,
                                                   _SECTION,
                                                   password=None))
        ca_file = settings.get(_SECTION, _CA_FILE,
                               vars=DefaultOption(settings,
                                                  _SECTION,
                                                  ca_file=None))
        output_file = settings.get(_SECTION, _OUTPUT_FILE,
                                   vars=DefaultOption(settings,
                                                      _SECTION,
                                                      output_file=None))
        ansible_play = settings.get(_SECTION, _ANSIBLE_PLAY,
                                    vars=DefaultOption(settings,
                                                       _SECTION,
                                                       ansible_play=None))
        if not site:
            site = input("%s%sSite address is not initialized. "
                         "Please provide the site URL (%s):%s "
                         % (INPUT, PREFIX, SITE_DEF, END)) or SITE_DEF
        if not username:
            username = input("%s%sUsername is not initialized. "
                             "Please provide username (%s):%s "
                             % (INPUT, PREFIX, USERNAME_DEF, END)
                             ) or USERNAME_DEF
        while not password:
            password = input("%s%sPassword is not initialized. "
                             "Please provide the password for "
                             "username %s:%s "
                             % (INPUT, PREFIX, username, END))

        while not ca_file:
            ca_file = input("%s%sCa file is not initialized. "
                            "Please provide the ca file location (%s):%s "
                            % (INPUT, PREFIX, CA_DEF, END)) or CA_DEF

        while not output_file:
            output_file = input("%s%sOutput file is not initialized. "
                                "Please provide the output file location "
                                "for the mapping var file (%s):%s "
                                % (INPUT, PREFIX, _OUTPUT_FILE, END)
                                ) or _OUTPUT_FILE
        self._validate_output_file_exists(output_file, log)
        while not ansible_play or not os.path.isfile(ansible_play):
            ansible_play = input("%s%sAnsible play '%s' is not "
                                 "initialized. Please provide the ansible "
                                 "play to generate the mapping var file "
                                 "(%s):%s "
                                 % (INPUT, PREFIX, ansible_play, PLAY_DEF, END)
                                 ) or PLAY_DEF
        return site, username, password, ca_file, output_file, ansible_play


class DefaultOption(dict):

    def __init__(self, config, section, **kv):
        self._config = config
        self._section = section
        dict.__init__(self, **kv)

    def items(self):
        _items = []
        for option in self:
            if not self._config.has_option(self._section, option):
                _items.append((option, self[option]))
            else:
                value_in_config = self._config.get(self._section, option)
                _items.append((option, value_in_config))
        return _items


if __name__ == "__main__":
    level = logging.getLevelName("DEBUG")
    conf = 'dr.conf'
    log = '/tmp/ovirt-dr.log'
    GenerateMappingFile().run(conf, log, level)