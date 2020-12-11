#!/usr/bin/python3

import inspect
import subprocess
import os
import sys
import pprint
import datetime
import argparse
import sqlite3
import numpy
import io
import re
import glob

######################################################
#### private helper functions
######################################################

def shell_to_str(cmd, exit_on_error=False):
    child = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    returncode = child.returncode
    if returncode != 0:
        if child.stderr != None:
            ret_stderr = child.stderr.decode('utf-8').rstrip(' \r\n')
            print()
            print('########################################################')
            print('#### STDERR:')
            print('########################################################')
            print()
            print(ret_stderr)
            print()
        print('ERROR: running "{}" ; returncode {}'.format(cmd, returncode))
        if exit_on_error: exit(1)
    ret_stdout = child.stdout.decode('utf-8').rstrip(' \r\n')
    return ret_stdout

def shell_to_list(cmd, sep=' ', exit_on_error=False):
    return shell_to_str(cmd, exit_on_error).split(sep)

######################################################
#### validator functions
######################################################

def is_nonempty(exp_dict, value):
    return str(value) != '' and str(value) != 'None' and value != None

def is_positive(exp_dict, value, eps=1e-6):
    return float(value) > eps

## note: this is not a validator per se, but rather RETURNS a validator (obtained via currying an argument)
def is_equal(to_this_value):
    def fn(exp_dict, value):
        return value == to_this_value
    return fn

## note: this is not a validator per se, but rather RETURNS a validator (obtained via currying an argument)
def is_run_param(param_name):
    def fn(exp_dict, value):
        if 'type_failures' not in exp_dict: exp_dict['type_failures'] = list()
        # print('param_name={} value={}'.format(param_name, value))
        success = False
        try:
            intval = int(value)
            success = (intval in exp_dict['run_params'][param_name])
        except ValueError:
            exp_dict['type_failures'].append('is_run_param tried to cast value "{}" to int and failed'.format(value))
        if success: return True
        return (value in exp_dict['run_params'][param_name]) or (str(value) in exp_dict['run_params'][param_name])
    return fn

######################################################
#### extractor functions
######################################################

def grep_line(exp_dict, file_name, field_name):   ## memoize files into data to make grepping efficient
    if 'memo_grep_line' not in exp_dict: exp_dict['memo_grep_line'] = dict()
    if file_name not in exp_dict['memo_grep_line'].keys():
        data_list = shell_to_list('grep -E "^[^ =]+=" {}'.format(file_name), sep='\n', exit_on_error=True)
        # print("data_list=" + repr(data_list))
        newdict = dict()
        for item in data_list:
            # print('splitting "{}"'.format(item))
            tokens = item.split('=')
            # if len(tokens) == 2:
            #     newdict[tokens[0]] = tokens[1]
            # else:
            #     newdict[tokens[0]] = '='.join(tokens[1:])
            newdict[tokens[0]] = '='.join(tokens[1:])
            # print('     into "{}" and "{}"'.format(tokens[0], '='.join(tokens[1:])))
        exp_dict['memo_grep_line'][file_name] = newdict

    return exp_dict['memo_grep_line'][file_name][field_name]

def run_param(exp_dict, file_name, field_name):
    print('run_param({}, {}) returns {}'.format(file_name, field_name, exp_dict['replacements'][field_name]))
    return exp_dict['replacements'][field_name]

def get_run_param(exp_dict, field_name):
    return exp_dict['run_params'][field_name]

######################################################
#### user facing functions
######################################################

def set_dir_compile(exp_dict, str):
    exp_dict['replacements']['__dir_compile'] = str

def set_dir_tools(exp_dict, str):
    exp_dict['replacements']['__dir_tools'] = str

def set_dir_run(exp_dict, str):
    exp_dict['replacements']['__dir_run'] = str

def set_dir_data(exp_dict, str):
    exp_dict['replacements']['__dir_data'] = str

def set_cmd_compile(exp_dict, str):
    exp_dict['cmd_compile'] = str

def set_cmd_run(exp_dict, str):
    exp_dict['cmd_run'] = str

def set_file_run_data(exp_dict, str):
    exp_dict['file_run_data'] = str

def get_dir_compile(exp_dict):
    return exp_dict['replacements']['__dir_compile']

def get_dir_tools(exp_dict):
    return exp_dict['replacements']['__dir_tools']

def get_dir_run(exp_dict):
    return exp_dict['replacements']['__dir_run']

def get_dir_data(exp_dict):
    return exp_dict['replacements']['__dir_data']

def add_run_param(exp_dict, name, value_list):
    # print('{}('{}', {})'.format(inspect.currentframe().f_code.co_name, name, value_list))
    exp_dict['run_params'][name] = value_list

def add_data_field(exp_dict, name, coltype='TEXT', validator=is_nonempty, extractor=grep_line):
    d = locals()
    del d['exp_dict']
    exp_dict['data_fields'][name] = d
    # exp_dict['data_fields'][name] = dict({ 'name':name, 'coltype':coltype, 'validator':validator, 'extractor':extractor })

def add_plot_set(exp_dict, name, x_axis, y_axis, plot_type, series='', varying_cols_list=[], filter='', title='', plot_cmd_args='', plot_style_hooks_file=''):
    if plot_style_hooks_file == '' and 'plot_style_hooks_file' in exp_dict:
        plot_style_hooks_file = exp_dict['plot_style_hooks_file']
    d = locals()
    del d['exp_dict']
    exp_dict['plots'].append(d)
    # exp_dict['plots'].append(dict({ 'name':name, 'x_axis':x_axis, 'y_axis':y_axis, 'plot_type':plot_type, 'series':series, 'varying_cols_list':varying_cols_list, 'filter':filter, 'title':title, 'plot_cmd_args':plot_cmd_args, 'plot_style_hooks_file':plot_style_hooks_file }))

def add_page_set(exp_dict, image_files, name='', column_field='', row_field='', table_field='', page_field_list=[], sep='-'):
    tokens = image_files.split(sep)

    if name == '':
        assert(len(tokens) > 0)
        name = tokens[0]
    if column_field == '':
        assert(len(tokens) > 1)
        field_singleton_list = re.findall(r'\{[^\}]*\}', tokens[1])
        assert(len(field_singleton_list) == 1)
        column_field = field_singleton_list[0].replace('{', '').replace('}', '')
    if row_field == '':
        assert(len(tokens) > 2)
        field_singleton_list = re.findall(r'\{[^\}]*\}', tokens[2])
        assert(len(field_singleton_list) == 1)
        row_field = field_singleton_list[0].replace('{', '').replace('}', '')
    if table_field == '' and len(tokens) > 3:
        field_singleton_list = re.findall(r'\{[^\}]*\}', tokens[3])
        assert(len(field_singleton_list) == 1)
        table_field = field_singleton_list[0].replace('{', '').replace('}', '')
    if page_field_list == [] and len(tokens) > 4:
        page_field_list = re.findall(r'\{[^\}]*\}', sep.join(tokens[4:]))
        for i, f in zip(len(page_field_list), page_field_list):
            page_field_list[i] = f.replace('{', '').replace('}', '')

    fields = re.findall(r'\{[^\}]*\}', image_files)
    for i, f in zip(range(len(fields)), fields):
        fields[i] = f.replace('{', '').replace('}', '')

    del i
    del f
    del field_singleton_list
    del tokens
    d = locals()
    del d['exp_dict']
    exp_dict['pages'].append(d)

def set_content_index_html(exp_dict, content_html_string):
    exp_dict['content_index_html']=content_html_string

def set_plot_style_hooks_file(exp_dict, path):
    exp_dict['plot_style_hooks_file'] = path
