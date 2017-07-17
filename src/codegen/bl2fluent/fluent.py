#!/usr/bin/env python
# -*- coding: utf-8 -*-

# CAVEAT UTILITOR
#
# This file was automatically generated by TatSu.
#
#    https://pypi.python.org/pypi/tatsu/
#
# Any changes you make to it will be overwritten the next time
# the file is generated.


from __future__ import print_function, division, absolute_import, unicode_literals

from tatsu.buffering import Buffer
from tatsu.parsing import Parser
from tatsu.parsing import tatsumasu
from tatsu.util import re, generic_main  # noqa


KEYWORDS = {}  # type: ignore


class FLUENTBuffer(Buffer):
    def __init__(
        self,
        text,
        whitespace=None,
        nameguard=None,
        comments_re=None,
        eol_comments_re=None,
        ignorecase=None,
        namechars='',
        **kwargs
    ):
        super(FLUENTBuffer, self).__init__(
            text,
            whitespace=whitespace,
            nameguard=nameguard,
            comments_re=comments_re,
            eol_comments_re=eol_comments_re,
            ignorecase=ignorecase,
            namechars=namechars,
            **kwargs
        )


class FLUENTParser(Parser):
    def __init__(
        self,
        whitespace=None,
        nameguard=None,
        comments_re=None,
        eol_comments_re=None,
        ignorecase=None,
        left_recursion=True,
        parseinfo=True,
        keywords=None,
        namechars='',
        buffer_class=FLUENTBuffer,
        **kwargs
    ):
        if keywords is None:
            keywords = KEYWORDS
        super(FLUENTParser, self).__init__(
            whitespace=whitespace,
            nameguard=nameguard,
            comments_re=comments_re,
            eol_comments_re=eol_comments_re,
            ignorecase=ignorecase,
            left_recursion=left_recursion,
            parseinfo=parseinfo,
            keywords=keywords,
            namechars=namechars,
            buffer_class=buffer_class,
            **kwargs
        )

    @tatsumasu()
    def _start_(self):  # noqa
        self._rule_()
        self._check_eof()

    @tatsumasu()
    def _rule_(self):  # noqa
        self._catalog_entry_()
        self.name_last_node('lhs')
        self._merge_()
        self.name_last_node('mtype')
        self._rhs_()
        self.name_last_node('rhs')
        self._token(';')
        self.ast._define(
            ['lhs', 'mtype', 'rhs'],
            []
        )

    @tatsumasu('string')
    def _catalog_entry_(self):  # noqa
        self._pattern(r'\w+')

    @tatsumasu()
    def _merge_(self):  # noqa
        with self._choice():
            with self._option():
                self._token('<=')
            with self._option():
                self._token('<+')
            with self._option():
                self._token('<~')
            with self._option():
                self._token('<-')
            self._error('no available options')

    @tatsumasu()
    def _rhs_(self):  # noqa
        with self._choice():
            with self._option():
                self._catalog_entry_()
                self.name_last_node('anchor')
                self._token('.')
                self._cut()
                self._opchain_()
                self.name_last_node('chain')
            with self._option():
                self._opchain_()
                self.name_last_node('chain')
            with self._option():
                self._catalog_entry_()
                self.name_last_node('anchor')
            self._error('no available options')
        self.ast._define(
            ['anchor', 'chain'],
            []
        )

    @tatsumasu()
    def _opchain_(self):  # noqa

        def sep0():
            self._token('.')

        def block0():
            self._op_()
        self._positive_join(block0, sep0)

    @tatsumasu()
    def _op_(self):  # noqa
        self._opname_()
        self.name_last_node('opname')
        with self._optional():
            self._template_params_()
        self.name_last_node('plist')
        self._token('(')
        with self._optional():
            self._op_args_()
        self.name_last_node('op_args')
        self._token(')')
        self.ast._define(
            ['op_args', 'opname', 'plist'],
            []
        )

    @tatsumasu()
    def _opname_(self):  # noqa
        with self._choice():
            with self._option():
                self._token('where')
            with self._option():
                self._token('project')
            with self._option():
                self._token('map')
            with self._option():
                self._token('cross')
            with self._option():
                self._token('join')
            with self._option():
                self._token('groupby')
            self._error('no available options')

    @tatsumasu()
    def _template_params_(self):  # noqa
        self._token('<')

        def sep1():
            self._token(',')

        def block1():
            self._pattern(r'[\w ]+')
        self._positive_join(block1, sep1)
        self.name_last_node('params')
        self._token('>')
        self.ast._define(
            ['params'],
            []
        )

    @tatsumasu()
    def _op_args_(self):  # noqa
        with self._choice():
            with self._option():
                self._pattern(r'\w+')
                self.name_last_node('argname')
                self._codeblock_()
                self.name_last_node('code')
            with self._option():

                def sep2():
                    self._token(',')

                def block2():
                    self._catalog_entry_()
                    self.name_last_node('catitem')
                self._positive_join(block2, sep2)
            self._error('no available options')
        self.ast._define(
            ['argname', 'catitem', 'code'],
            []
        )

    @tatsumasu()
    def _codeblock_(self):  # noqa
        self._token('```')
        self._lang_()
        self.name_last_node('lang')
        self._code_()
        self.name_last_node('code')
        self._token('```')
        self.ast._define(
            ['code', 'lang'],
            []
        )

    @tatsumasu()
    def _code_(self):  # noqa
        self._pattern(r"[^'```']+")

    @tatsumasu()
    def _lang_(self):  # noqa
        with self._choice():
            with self._option():
                self._token('C++')
            with self._option():
                self._token('c++')
            with self._option():
                self._token('C')
            with self._option():
                self._token('c')
            with self._option():
                self._token('Python')
            with self._option():
                self._token('python')
            self._error('no available options')


class FLUENTSemantics(object):
    def start(self, ast):  # noqa
        return ast

    def rule(self, ast):  # noqa
        return ast

    def catalog_entry(self, ast):  # noqa
        return ast

    def merge(self, ast):  # noqa
        return ast

    def rhs(self, ast):  # noqa
        return ast

    def opchain(self, ast):  # noqa
        return ast

    def op(self, ast):  # noqa
        return ast

    def opname(self, ast):  # noqa
        return ast

    def template_params(self, ast):  # noqa
        return ast

    def op_args(self, ast):  # noqa
        return ast

    def codeblock(self, ast):  # noqa
        return ast

    def code(self, ast):  # noqa
        return ast

    def lang(self, ast):  # noqa
        return ast


def main(filename, startrule, **kwargs):
    with open(filename) as f:
        text = f.read()
    parser = FLUENTParser()
    return parser.parse(text, startrule, filename=filename, **kwargs)


if __name__ == '__main__':
    import json
    from tatsu.util import asjson

    ast = generic_main(main, FLUENTParser, name='FLUENT')
    print('AST:')
    print(ast)
    print()
    print('JSON:')
    print(json.dumps(asjson(ast), indent=2))
    print()

