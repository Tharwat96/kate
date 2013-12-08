# -*- coding: utf-8 -*-
# This file is part of Pate, Kate' Python scripting plugin.
#
# Copyright (C) 2006 Paul Giannaros <paul@giannaros.org>
# Copyright (C) 2013 Alex Turbov <i.zaufi@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Library General Public
# License as published by the Free Software Foundation; either
# version 2 of the License, or (at your option) version 3.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public License
# along with this library; see the file COPYING.LIB.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA 02110-1301, USA.

''' Engine to expand `User Defined Functions` (including Jinja2 templates) '''

import functools
import imp
import inspect
import os
import re
import sys
import time
import traceback

import jinja2

from PyQt4.QtGui import QToolTip
from PyKDE4.kdecore import KConfig, i18nc
from PyKDE4.ktexteditor import KTextEditor

import kate
import kate.ui

from libkatepate import common


_EXPANDS_EXT = '.expand'
_EXPANDS_BASE_DIR = 'expand'
_JINJA_TEMPLATES_BASE_DIR = os.path.join(_EXPANDS_BASE_DIR, 'templates')

class ParseError(Exception):
    pass


def wordAndArgumentAtCursorRanges(document, cursor):
    line = document.line(cursor.line())

    argument_range = None
    # Handle some special cases:
    if cursor.column() > 0:
        if cursor.column() < len(line) and line[cursor.column()] == ')':
            # special case: cursor just right before a closing brace
            argument_end = KTextEditor.Cursor(cursor.line(), cursor.column())
            argument_start = matchingParenthesisPosition(document, argument_end, opening=')')
            argument_end.setColumn(argument_end.column() + 1)
            argument_range = KTextEditor.Range(argument_start, argument_end)
            cursor = argument_start                         #  NOTE Reassign

        if line[cursor.column() - 1] == ')':
            # one more special case: cursor past end of arguments
            argument_end = KTextEditor.Cursor(cursor.line(), cursor.column() - 1)
            argument_start = matchingParenthesisPosition(document, argument_end, opening=')')
            argument_end.setColumn(argument_end.column() + 1)
            argument_range = KTextEditor.Range(argument_start, argument_end)
            cursor = argument_start                         #  NOTE Reassign

    word_range = common.getBoundTextRangeSL(
        common.IDENTIFIER_BOUNDARIES
      , common.IDENTIFIER_BOUNDARIES
      , cursor
      , document
      )
    end = word_range.end().column()
    if argument_range is None and word_range.isValid():
        if end < len(line) and line[end] == '(':
            # ruddy lack of attribute type access from the KTextEditor
            # interfaces.
            argument_start = KTextEditor.Cursor(cursor.line(), end)
            argument_end = matchingParenthesisPosition(document, argument_start, opening='(')
            argument_range = KTextEditor.Range(argument_start, argument_end)
    return word_range, argument_range


# TODO Generalize this and move to `common' package
def matchingParenthesisPosition(document, position, opening='('):
    closing = ')' if opening == '(' else '('
    delta = 1 if opening == '(' else -1
    # take a copy, Cursors are mutable
    position = position.__class__(position)

    level = 0
    state = None
    while 1:
        character = document.character(position)
        if state in ('"', "'"):
            if character == state:
                state = None
        else:
            if character == opening:
                level += 1
            elif character == closing:
                level -= 1
                if level == 0:
                    if closing == ')':
                        position.setColumn(position.column() + delta)
                    break
            elif character in ('"', "'"):
                state = character

        position.setColumn(position.column() + delta)
        # must we move down a line?
        if document.character(position) == None:
            position.setPosition(position.line() + delta, 0)
            if delta == -1:
                # move to the far right
                position.setColumn(document.lineLength(position.line()) - 1)
            # failure again => EOF
            if document.character(position) == None:
                raise ParseError(i18nc('@info', 'end of file reached'))
            else:
                if state in ('"', "'"):
                    raise ParseError(
                        i18nc(
                            '@info'
                          , 'end of line reached while searching for <icode>%1</icode>', state
                          )
                      )
    return position


def loadExpansionsFromFile(path):
    kate.kDebug('Loading expansions from {}'.format(path))
    name = os.path.basename(path).split('.')[0]
    module = imp.load_source(name, path)
    expansions = {}
    # expansions are everything that don't begin with '__' and are callable
    for name in dir(module):
        o = getattr(module, name)
        # ignore builtins. Note that it is callable.__name__ that is used
        # to set the expansion key so you are free to reset it to something
        # starting with two underscores (or more importantly, a Python
        # keyword)
        # NOTE Detect ONLY a real function!
        if not name.startswith('__') and inspect.isfunction(o):
            expansions[o.__name__] = (o, path)
            kate.kDebug('Adding expansion `{}`'.format(o.__name__))
    return expansions


def mergeExpansions(left, right):
    assert(isinstance(left, dict) and isinstance(right, dict))
    result = left
    for exp_key, exp_tuple in right.items():
        if exp_key not in result:
            result[exp_key] = exp_tuple
        else:
            result[exp_key] = result[exp_key]
            kate.kDebug('WARNING: Ignore duplicate expansion `{}` from {}'.format(exp_key, exp_tuple[1]))
            kate.kDebug('WARNING: First defined here {}'.format(result[exp_key][1]))
    return result


def _getExpansionsFor(mime):
    expansions = {}
    # TODO What about other (prohibited in filesystem) symbols?
    mime_filename = mime.replace('/', '_') + _EXPANDS_EXT
    for directory in kate.applicationDirectories(_EXPANDS_BASE_DIR):
        if os.path.exists(os.path.join(directory, mime_filename)):
            expansions = mergeExpansions(
                expansions
              , loadExpansionsFromFile(os.path.join(directory, mime_filename))
              )
    return expansions


@functools.lru_cache()
def getExpansionsFor(mime):
    kate.kDebug('Collecting expansions for MIME {}'.format(mime))
    result = mergeExpansions(_getExpansionsFor(mime), _getExpansionsFor('all'))
    kate.kDebug('Got {} expansions at the end'.format(len(result)))
    return result


def _makeEditableField(param, **kw):
    act = '@' if 'active' in kw else ''
    if 'name' in kw:
        name = kw['name']
    else:
        name = param.strip()
    return '${{{}{}:{}}}'.format(name, act, param)


def _is_bool(s):
    return isinstance(s,bool)


def _is_int(s):
    return isinstance(s,int)


@functools.lru_cache()
def getJinjaEnvironment(baseDir):
    kate.kDebug('Make a templates loader for a base dir: {}'.format(baseDir))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(baseDir))
    #env.trim_blocks = True
    #env.lstrip_blocks = True
    env.block_start_string = '/*%'
    env.block_end_string = '%*/'
    env.variable_start_string = '/*<'
    env.variable_end_string = '>*/'
    env.line_statement_prefix = '//%'
    env.line_comment_prefix = '//#'
    env.filters['editable'] = _makeEditableField
    env.tests['boolean'] = _is_bool
    env.tests['integer'] = _is_int
    return env


def getHelpOnExpandAtCursor():
    document = kate.activeDocument()
    view = document.activeView()
    try:
        word_range, argument_range = wordAndArgumentAtCursorRanges(document, view.cursorPosition())
    except ParseError as e:
        kate.ui.popup(i18nc('@title:window', 'Parse error'), e, 'dialog-warning')
        return
    word = document.text(word_range)
    expansions = getExpansionsFor(document.mimeType())
    if word in expansions:
        func = expansions[word][0]
        cursor_pos = view.cursorPositionCoordinates()
        tooltip_text = '\n'.join([
            line[8:] if line.startswith(' ' * 8) else line for line in func.__doc__.splitlines()
          ])
        kate.kDebug('Expand: help on {}: {}'.format(word, tooltip_text))
        QToolTip.showText(cursor_pos, tooltip_text)
    else:
        kate.kDebug('WARNING: undefined expansion `{}`'.format(word))


def expandAtCursor():
    ''' Attempt text expansion on the word at the cursor.

        The expansions available are based firstly on the mimetype of the
        document, for example "text_x-c++src.expand" for "text/x-c++src", and
        secondly on "all.expand".
    '''
    document = kate.activeDocument()
    view = document.activeView()
    try:
        word_range, argument_range = wordAndArgumentAtCursorRanges(document, view.cursorPosition())
    except ParseError as e:
        kate.ui.popup(i18nc('@title:window', 'Parse error'), e, 'dialog-warning')
        return
    word = document.text(word_range)
    expansions = getExpansionsFor(document.mimeType())
    if word in expansions:
        func = expansions[word][0]
    else:
        kate.ui.popup(
            i18nc('@title:window', 'Error')
          , i18nc('@info:tooltip', 'Expansion "<icode>%1</icode>" not found', word)
          , 'dialog-warning'
          )
        return
    arguments = []
    namedArgs = {}
    if argument_range is not None:
        # strip parentheses and split arguments by comma
        preArgs = [arg.strip() for arg in document.text(argument_range)[1:-1].split(',') if bool(arg.strip())]
        kate.kDebug('Arguments = {}'.format(arguments))
        # form a dictionary from args w/ '=' character, leave others in a list
        for arg in preArgs:
            if '=' in arg:
                key, value = [item.strip() for item in arg.split('=')]
                namedArgs[key] = value
            else:
                arguments.append(arg)
    # Call user expand function w/ parsed arguments and
    # possible w/ named params dict
    try:
        kate.kDebug('Arguments = {}'.format(arguments))
        kate.kDebug('Named arguments = {}'.format(namedArgs))
        if len(namedArgs):
            replacement = func(*arguments, **namedArgs)
        else:
            replacement = func(*arguments)
    except Exception as e:
        # remove the top of the exception, it's our code
        try:
            type, value, tb = sys.exc_info()
            sys.last_type = type
            sys.last_value = value
            sys.last_traceback = tb
            tblist = traceback.extract_tb(tb)
            del tblist[:1]
            l = traceback.format_list(tblist)
            if l:
                l.insert(0, i18nc('@info', 'Traceback (most recent call last):<nl/>'))
            l[len(l):] = traceback.format_exception_only(type, value)
        finally:
            tblist = tb = None
        # convert file names in the traceback to links. Nice.
        def replaceAbsolutePathWithLinkCallback(match):
            text = match.group()
            filePath = match.group(1)
            fileName = os.path.basename(filePath)
            text = text.replace(filePath, i18nc('@info', '<link url="%1">%2</link>', filePath, fileName))
            return text
        s = ''.join(l).strip()
        # FIXME: extract the filename and then use i18nc, instead of manipulate the i18nc text
        s = re.sub(
            i18nc('@info', 'File <filename>"(/[^\n]+)"</filename>, line')
          , replaceAbsolutePathWithLinkCallback
          , s
          )
        kate.kDebug('EXPAND FAILURE: {}'.format(s))
        kate.ui.popup(
            i18nc('@title:window', 'Error')
          , i18nc('@info:tooltip', '<bcode>%1</bcode>', s)
          , 'dialog-error'
          )
        return

    # Check what type of expand function it was
    if hasattr(func, 'template'):
        assert(isinstance(replacement, dict))
        # Ok, going to render some jinja2 template...
        filename = kate.findApplicationResource('{}/{}'.format(_JINJA_TEMPLATES_BASE_DIR, func.template))
        if not filename:
            kate.ui.popup(
                i18nc('@title:window', 'Error')
              , i18nc('@info:tooltip', 'Template file not found <filename>%1</filename>', func.template)
              , 'dialog-error'
              )
            return

        kate.kDebug('found abs template: {}'.format(filename))

        # Get a corresponding environment for jinja!
        base_dir_pos = filename.find(_JINJA_TEMPLATES_BASE_DIR)
        assert(base_dir_pos != -1)
        basedir = filename[:base_dir_pos + len(_JINJA_TEMPLATES_BASE_DIR)]
        filename = filename[base_dir_pos + len(_JINJA_TEMPLATES_BASE_DIR) + 1:]
        env = getJinjaEnvironment(basedir)
        kate.kDebug('basedir={}, template_rel={}'.format(basedir, filename))
        try:
            kate.kDebug('Using jinja template file: {0}'.format(filename))
            tpl = env.get_template(filename)
            kate.kDebug('data dict={}'.format(replacement))
            replacement = tpl.render(replacement)
        except jinja2.TemplateError as e:
            kate.ui.popup(
                i18nc('@title:window', 'Error')
              , i18nc(
                    '@info:tooltip'
                  , 'Template file error [<filename>%1</filename>]: <status>%2</status>'
                  , func.template
                  , e.message
                  )
              , 'dialog-error'
              )
            return

    with kate.makeAtomicUndo(document):
        # Remove old text
        if argument_range is not None:
            document.removeText(argument_range)
        document.removeText(word_range)

        kate.kDebug('Expanded text:\n{}'.format(replacement))

        # Check if expand function requested a TemplateInterface2 to render
        # result content...
        if hasattr(func, 'use_template_iface') and func.use_template_iface:
            # Use TemplateInterface2 to insert a code snippet
            kate.kDebug('TI2 requested!')
            ti2 = view.templateInterface2()
            if ti2 is not None:
                ti2.insertTemplateText(word_range.start(), replacement, {}, None)
                return
            # Fallback to default (legacy) way...

        # Just insert text :)
        document.insertText(word_range.start(), replacement)
