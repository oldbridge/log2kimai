#!/usr/bin/python
"""
CommandLine Tool / Modul for Kimai (run on Python 2.7)
"""
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPHandler
from http.cookiejar import CookieJar
from argparse import ArgumentParser
from configparser import ConfigParser
from datetime import datetime, timedelta
from re import search, sub
from sys import stdin

class KimaiMessage(object):
    """
    The Message Object
    """
    def __init__(self, baseurl, user, passwd, version):
        """
        message constructor
        """
        supported_verions = {'0.9.2.1306':0,
                             '0.9.3.1384':1}
        self.baseurl = baseurl
        self.user = user
        self.passwd = passwd
        try:
            self.request_type = supported_verions[version]
        except:
            exit('this version of kimai is currently not supported')
        # get authentication cookie
        cookiejar = CookieJar()
        opener = build_opener(HTTPCookieProcessor(cookiejar), HTTPHandler())
        url = ''.join([self.baseurl, '/index.php?a=checklogin'])
        postdata = urlencode({'name':self.user, 'password':self.passwd}).encode('utf-8')
        request = Request(url, postdata)
        result = opener.open(request)
        self.session = opener
        #extract user id from result body
        for line in result:
            line = line.decode('utf-8')
            if search(r"userID|usr_ID", line):
                self.userid = sub(r'^.*([0-9]{9}).*\n$', r'\1', line)
                break
        try:
            self.userid
        except:
            exit("userID was not found")
        #extract project and activities dicts from result body
        self.projects = {}
        self.activity = {}
        for line in result:
            line = line.decode('utf-8')
            if self.request_type == 1:
                if search(r'buzzer_preselect_project\(', line):
                    match = sub(r".*buzzer_preselect_project\(([0-9]{1,}),'(.*)',.*\n", r'\1,\2', line)
                    (idnum, name) = tuple(match.split(','))
                    if int(idnum) not in self.projects:
                        self.projects[int(idnum)] = name
                elif search(r'buzzer_preselect_activity\(', line):
                    match = sub(r".*buzzer_preselect_activity\(([0-9]{1,}),'(.*)'\).*\n", r'\1,\2', line)
                    (idnum, name) = tuple(match.split(','))
                    if int(idnum) not in self.activity:
                        self.activity[int(idnum)] = name
            elif self.request_type == 0:
                if search(r"buzzer_preselect\('pct", line):
                    match = sub(r".*buzzer_preselect\('pct',([0-9]{1,}),'(.*)',.*\n", r'\1,\2', line)
                    (idnum, name) = tuple(match.split(','))
                    if int(idnum) not in self.projects:
                        self.projects[int(idnum)] = name
                elif search(r"buzzer_preselect\('evt", line):
                    match = sub(r".*buzzer_preselect\('evt',([0-9]{1,}),'(.*)',.*\n", r'\1,\2', line)
                    (idnum, name) = tuple(match.split(','))
                    if int(idnum) not in self.activity:
                        self.activity[int(idnum)] = name

    def __del__(self):
        """
        deconstruct Message
        """
        url = ''.join([self.baseurl, '/index.php?a=logout'])
        self.session.open(Request(url))

    def log_work(self, start, end, pid, aid, comment='', descr=''):
        """
        log work
        """
        param_start_date = start.strftime('%d.%m.%Y')
        param_start_time = start.strftime('%H:%M:%S')
        param_end_date = end.strftime('%d.%m.%Y')
        param_end_time = end.strftime('%H:%M:%S')
        time_delta = end - start
        hours, remainder = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        param_duration = ':'.join([str(hours).zfill(2), str(minutes).zfill(2), str(seconds).zfill(2)])
        url = ''.join([self.baseurl, '/extensions/ki_timesheets/processor.php'])
        if self.request_type == 0:
            postdata = urlencode({  'id': '0',
                                    'axAction': 'add_edit_record',
                                    'pct_ID': pid,
                                    'filter': '',
                                    'evt_ID': aid,
                                    'filter': '',
                                    'edit_in_day': param_start_date,
                                    'edit_out_day': param_end_date,
                                    'edit_in_time': param_start_time,
                                    'edit_out_time': param_end_time,
                                    'edit_duration': param_duration,
                                    'zlocation': '',
                                    'trackingnr': '',
                                    'comment': comment,
                                    'comment_type': '0'})
        elif self.request_type == 1:
            postdata = urlencode({  'id':'',
                                    'axAction':'add_edit_timeSheetEntry',
                                    'projectID':pid,
                                    'filter':'',
                                    'activityID':aid,
                                    'description':descr,
                                    'start_day':param_start_date,
                                    'end_day':param_end_date,
                                    'start_time':param_start_time,
                                    'end_time':param_end_time,
                                    'duration':param_duration,
                                    'location':'',
                                    'trackingNumber':'',
                                    'comment':comment,
                                    'commentType':0,
                                    'userID[]':self.userid,
                                    'budget':'',
                                    'approved':'',
                                    'statusID':1,
                                    'billable':0,
                                    'rate':'',
                                    'fixedRate':''})
        request = Request(url, postdata)
        self.session.open(request)

def main():
    """
    main function for command line usage
    """
    # parse commandline arguments
    cmd_parser = ArgumentParser(description='Log Work to a Kimai instance')
    cmd_parser.add_argument('--configFile', type=str, default='log2kimai.cfg', help='default: log2kimai.cfg')
    cmd_parser.add_argument('-v', '--verbose', action='store_true')
    cmd_parser.add_argument('-d', '--dry', action='store_true', help='dryrun; just validating input')
    cmd_parser.add_argument('action', nargs='+', help='add, info projects/activities')
    cmd_args = cmd_parser.parse_args()
    config_file = ConfigParser()
    try:
        config_file.readfp(open(cmd_args.configFile))
    except IOError:
        exit('Error: Specified config file was not found or not readable.')
    # info mode
    if len(cmd_args.action) == 2 and cmd_args.action[0] == 'info':
        kimai = KimaiMessage(config_file.get('kimai', 'baseurl'),
                             config_file.get('kimai', 'user'),
                             config_file.get('kimai', 'pass'),
                             config_file.get('kimai', 'version'))
        if cmd_args.action[1] == 'activities':
            for key in kimai.activity:
                print(' '.join([str(key), ':', kimai.activity[key]]))
        elif cmd_args.action[1] == 'projects':
            for key in kimai.projects:
                print(' '.join([str(key), ':', kimai.projects[key]]))
        exit()
    elif len(cmd_args.action) == 1 and cmd_args.action[0] == 'add':
        # add mode
        # check stdin
        if stdin.isatty():
            exit()
        # read and validate stdin
        add_list = []
        line_counter = 0
        for line in stdin.readlines():
            line_counter += 1
            line = sub(r'\n', r'', ''.join(line))
            input_list = line.split('|')
            # validate number of arguments per line
            if len(input_list) != 5:
                print(' '.join(['error parsing stdin line', str(line_counter)]))
            # validate startdate
            try:
                datetime_start = datetime.strptime(input_list[0], '%y%m%d-%H%M')
            except ValueError:
                exit(' '.join(['Error parsing start date (format is supposed to be yymmdd-HHmm)', str(line_counter)]))
            # validate duration
            try:
                datetime_end = datetime_start + timedelta(minutes=+int(input_list[1]))
            except ValueError:
                exit(' '.join(['Error parsing duration (supposed to be an integer) in line', str(line_counter)]))
            # validate project id
            try:
                project_id = int(input_list[2])
            except ValueError:
                exit(' '.join(['Error parsing project_id (supposed to be an integer) in line', str(line_counter)]))
            # validate activity id
            try:
                activity_id = int(input_list[3])
            except ValueError:
                exit(' '.join(['Error parsing activity_id (supposed to be an integer) in line', str(line_counter)]))
            comment = input_list[4]
            add_list.append((datetime_start, datetime_end, project_id, activity_id, comment))
            if cmd_args.verbose:
                print((datetime_start, datetime_end, project_id, activity_id, comment))
        if not cmd_args.dry and len(cmd_args.action) > 0 and cmd_args.action[0] == 'add':
            # send requests to log work
            kimai = KimaiMessage(config_file.get('kimai', 'baseurl'),
                                 config_file.get('kimai', 'user'),
                                 config_file.get('kimai', 'pass'),
                                 config_file.get('kimai', 'version'))
            for (start, end, pid, aid, comment) in add_list:
                kimai.log_work(start, end, pid, aid, comment)
    else:
        cmd_parser.print_usage()
if __name__ == "__main__":
    main()
