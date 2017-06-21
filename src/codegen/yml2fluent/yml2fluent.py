#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Fluent code generator

XXX THIS CODE IS CURRENTLY UNSTABLE.

This module takes in Bloom-like YAML files and generates 
fluent-compatible C++ implementations as header files to
be included in a C++ driver program.

The YAML file has the format:
    name: <projectname>
    args: 
      - <arg1>: <arg1type>
      - <arg2>: <arg2type>
      ...
    schema:
      stdin:
      stdout:
      <collectionname>: 
        type: {channel|table|...}
        cols:
          <col1>: <C++ type>
          <col2>: <C++ type>
          ...
      ...

    preload:
      <collectionname>: [[<C++>, <C++>, <C++>]]

    bootstrap:
      <rulename>: <Fluent C++ text of rule>
      <rulename>: <Fluent C++ text of rule>

    bloom:
      <rulename>: <Fluent C++ text of rule>
      <rulename>: <Fluent C++ text of rule>


Example:
  In this example, the target we build is a `.dylib`
  file suitable for linking into Python. It contains code
  for both a server and a client.
    $ python fluentgen.py client.yml -o client.h
    $ python fluentgen.py server.yml -o server.h
    $ g++  -std=c++14 -Wall -c -g -I../fluent/src -I../fluent/build/Debug/vendor/googletest/src/googletest/googletest/include -I../fluent/build/Debug/vendor/range-v3/range-v3-prefix/src/range-v3/include -Wall -Wextra -Werror -pedantic  -c fluentchat.cc
    $ g++  -Wall -g -dynamiclib fluentchat.o -L../fluent/build/Debug/fluent -lfluent -lzmq -lglog -lfmt -o fluentchat.dylib

  the context of fluentchat.cc is

Attributes:
  This module has no module-level variables

Todo:
  * test on more examples
  * think about modularity (e.g. the `import` feature of Bud)

"""

from ctypes import * #cdll
import argparse
from os import system
from os import close
import yaml
import tempfile
from sys import stdout
from collections import defaultdict,OrderedDict
import pprint
from itertools import chain
import tatsu

# https://stackoverflow.com/a/21912744/7333257
def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def fluent_prologue(name, args):
  """Generate C++ file preamble.

  Args:
    name (str): project name from the YAML name key
    args (list): the YAML args key, used to pass in runtime configuration arguments

  Returns:
    str: C++ code for the top of the generated file
  """
  retval = '''#ifndef ''' + str.upper(name) + '''_H_
#define ''' + str.upper(name) + '''_H_

#include <vector>

#include "zmq.hpp"

#include "common/status.h"
#include "fluent/fluent_builder.h"
#include "fluent/fluent_executor.h"
#include "fluent/infix.h"
#include "lineagedb/connection_config.h"
#include "lineagedb/noop_client.h"
#include "lineagedb/to_sql.h"
#include "ra/logical/all.h"
#include "common/hash_util.h"

namespace lra = fluent::ra::logical;

struct ''' + name + '''Args {
'''
  for vari, typei in args.items():
    retval += "  " + typei + " " + vari + ";\n"
  retval += '''};

int ''' + name + '''Main(const ''' + name + '''Args& args) {
  zmq::context_t context(1);
  fluent::lineagedb::ConnectionConfig connection_config;
  auto fb = fluent::fluent<fluent::lineagedb::NoopClient,fluent::Hash,
                           fluent::lineagedb::ToSql,fluent::MockPickler,
                           std::chrono::system_clock>
                           ("'''
  retval += name + '''_" + std::to_string(rand()),
                                    args.address, &context,
                                    connection_config)
    .ConsumeValueOrDie();
  auto schema = std::move(fb)
'''
  return retval

def fluent_epilogue(name):
  """Generate C++ file postamble.

  Args:
    name (str): project name from the YAML name key

  Returns:
    str: C++ code for the bottom of the generated file
  """

  return '''
  .ConsumeValueOrDie();
    fluent::Status status = std::move(bloom).Run();
    CHECK_EQ(fluent::Status::OK, status);

    return 0;
}

#endif  // ''' + str.upper(name) + '''_H_
'''

def extract_table_name(tdef):
  """Extract table names from schema definitions.
  Need to handle `stdin()` and `stdout()` specially.

  Args:
    tdef (str): table definition from the YAML schema list

  Returns:
    str: the table name in the definition
  """

  if (tdef == 'stdin()'):
    return 'fluin'
  elif (tdef == 'stdout()'):
    return 'fluout'
  else:
    return str.strip(str.split(str.split(tdef, '(')[1], ',')[0], '"\n \t')
  end

def arglist_tablenames(tables):
  """generate typed C++ method argument list for table names.
  Need to handle `stdin()` and `stdout()` specially.

  Args:
    tables (list of str): list of table definitions from YAML schema

  Returns:
    str: a string of the form "auto& tab1, auto& tab2, ..."
  """
  return ", ".join(('auto& ' + extract_table_name(table)) for table in tables)

def avoid_unused_table_warnings(tables):
  """generate empty uses of tablename variables to suppress unused variable warnings

  Args:
    tables (list of str): list of table definitions from YAML schema

  Returns:
    str: newline-separated strings of the form "(void)tablename;"
  """
  return '\n'.join(("      (void)" + extract_table_name(t) + ";") for t in tables)

def make_collection_name(tabname):
  return tabname + '_tuples'

def preload_types(stmts, schema):
  """create C++ types for the tuples to be preloaded

  Args:
    stmts: YAML dict with entries tablename: [(C++, C++, ...)]
    schema: YAML schema
  """
  retval = ""
  for tabname, tups in stmts.items():
    # declare type
    tup_type = tabname + "_tuple_t"
    retval += "  using " + tup_type + " = std::tuple<"
    retval += ",".join(schema[tabname]['cols'].values())
    retval += ">;\n"
    # create in-memory collection
    retval += "  std::vector<" + tup_type + "> "
    retval += make_collection_name(tabname) + " = {\n"
    retval += ",\n".join(("    std::make_tuple" + tup) for tup in tups)
    retval += "\n  };\n"
  return retval

def preload_rules_into_bootstrap(spec):
  """convert preload
  """
  retval = ""
  for tabname in spec['preload'].keys():
    # ruledef = tabname + " <= lra::make_iterable(&" + make_collection_name(tabname) + ")"
    ruledef = tabname + " <= " + make_collection_name(tabname) + ';'
    if not ('bootstrap' in spec):
      spec.update({'bootstrap': {}})
    spec['bootstrap'][tabname + "_boot"] = ruledef
  return retval

def convert_mtype(m):
  if m == '<+':
    return '+='
  elif m == '<-':
    return '-='
  else:
    return '<='

def input_schema(op):
  return "GET SCHEMA IN HERE"

def translate_chain(ast, collection_wrap):
  return ' | '.join([translate_op(o, collection_wrap) for o in ast if isinstance(o, tatsu.ast.AST)])

def translate_op(op, collection_wrap):
  opname = op.opname
  if opname == 'cross':
    opname = 'make_cross'
  elif opname == 'where':
    opname = 'filter'
  retval = 'lra::' + opname
  if not op.plist == None:
    retval += '<' + ''.join(o for o in chain.from_iterable(op.plist.params)) + '>'
  retval += '('
  if op.op_args != None:
    retval += translate_op_args(op.op_args, collection_wrap)
  retval += ')'
  return retval

def wrap_collection(c, collection_wrap): 
  return 'lra::' + collection_wrap + '(&' + c + ')'

def translate_op_args(args, collection_wrap):
  retval = ''
  if args.code != None:
    retval += '[&]'
    retval += '(const '
    # retval += std::tuple<'
    # retval += input_schema(op)
    # retval += '>'
    retval += 'auto'
    retval += '& ' + args.argname + ')'
    retval += args.code.code
  elif args.catitem != None:
    retval += ', '.join(wrap_collection(a, collection_wrap) for a in args.catitem)
  return retval

def expand_ruledict(r, collection_wrap):
  retval = r.lhs + ' ' + convert_mtype(r.mtype) + ' ('
  if r.rhs.anchor != None:
    retval += wrap_collection(r.rhs.anchor, collection_wrap)
    if r.rhs.chain != None:
      retval += ' | '
  if r.rhs.chain != None:
    retval += translate_chain(r.rhs.chain, collection_wrap)
  # pprint.pprint(r.rhs.chain)
  # if not r.rhs.chain == None:
  #   retval += (' | ').join(translate_op(op) for op in r.rhs.chain)
  retval += ')'
  return retval

def translate_rules(rules, collection_wrap):
  """convert YAML version of rules into Fluent C++

  Args:
    rules (list of str): list of rule definitions from YAML schema

  Returns:
    str: newline-separated string of the form
      "  auto <rulevariable1> = <rulesyntax>
         auto <rulevariable2> = <rulesyntax>
         ...
         return std::make_tuple(<rulevariable1>, <rulevariable2>, ...);
      "
  """
  retval = ''
  for k, v in rules.items():
    grammar = open('./fluent.ebnf').read()
    ruledict = tatsu.parse(grammar, v, parseinfo=True)
    v = expand_ruledict(ruledict, collection_wrap)
    retval += ("      auto " + k + " = " + v + ';\n')
  retval += ("      return std::make_tuple(" + ",".join(rules.keys()) + ");\n")
  return retval

def chain_schema_defs(clist):
  """take Fluent C++ collection definitions and string them together into a method chain

  Args:
    clist (list of str): list of Fluent C++ collection definitions

  Returns:
    str: newline-separated string of the form
      "  .<collectiondef1>
         .<collectiondef2>
         ...;
      "
  """
  retval = ""
  for l in clist:
    retval += '    .' + l + '\n'
  return retval

def translate_schema(sdict):
  """convert YAML schema to a list of Fluent C++ collection definitions

  Args:
    sdict (dict): YAML entries for collection definitions

  Returns:
    list of str: list with entries with one of the following forms:
      "stdin()"
      "stdout()"
      "template collection_type <type1,...>(collection_name, {{name1, ...}})"
  """
  result = []
  for name, defn in sdict.items():
    if (name == 'stdin' or name == 'stdout'):
      result.append(name + '()')
      # we ignore the definition for stdin and stdout
    else:
      collection_type = defn['type']
      collection_name = name
      cols = defn['cols']
      colnames = ('"' + col + '"' for col in cols.keys())
      coltypes = cols.values()
      str = "template " + collection_type + "<"
      str += ", ".join(coltypes) + ">("
      str += '"' + collection_name + '", {{' + ', '.join(colnames) + '}})'
      result.append(str)
  return result


def codegen(specFile):
  """convert YAML Bloom spec to a Fluent C++ header file

  Args:
    specFile (str): path to the .yml file

  Returns:
    text of the C++ file
  """
  spec = ordered_load(open(specFile, "r"))
  # we ensure that we have (address: std::string) in args
  if (not 'args' in spec):
    spec['args'] = {}
  keys = spec['args']
  if (not 'address' in keys):
    spec['args'].update({'address':'std::string'})
  elif(spec['args']['address'] != 'std::string'):
    raise Exception('''argument 'address' reserved to be 'std::string' ''')

  lines = []

  lines.append(fluent_prologue(spec['name'], spec['args']))

  lastvar = 'fd'
  useTables = ''
  schema = []

  if ('schema' in spec):
    lines.append('\n    ///////////////\n')
    lines.append('    // Bloom Schema\n')
    schema = translate_schema(spec['schema'])
    lines.append(chain_schema_defs(schema))
    lines.append('    ///////////////\n')
    lines.append( '  ;\n')
    lastvar = "schema"
    useTables = avoid_unused_table_warnings(schema) + '\n'

  if ('preload' in spec):
    lines.append(preload_types(spec['preload'], spec['schema']))
    preload_rules_into_bootstrap(spec)

  if ('preamble' in spec):
    lines.append('\n  // Explicit C++ preamble code\n')
    lines.append(spec['preamble'] + '\n')

  if ('bootstrap' in spec):
    lines.append("  auto bootstrap = std::move(" + lastvar + ")\n")
    lines.append("    .RegisterBootstrapRules([&](")
    lines.append(arglist_tablenames(schema))
    lines.append(") {\n")
    lines.append(useTables)
    lines.append("      using namespace fluent::infix;\n")
    lines.append('\n      ////////////////////////\n')
    lines.append('      // Bloom Bootstrap Rules\n')
    lines.append(translate_rules(spec['bootstrap'], 'make_iterable'))
    lines.append('      ////////////////////////\n')
    lines.append("    })\n")
    lines.append(';\n')
    lastvar = "bootstrap"

  lines.append("  auto bloom = std::move(" + lastvar + ")\n")
  if ('bloom' in spec):
    lines.append("    .RegisterRules([&](")
    lines.append(arglist_tablenames(schema))
    lines.append(") {\n")
    lines.append(useTables)
    lines.append("      using namespace fluent::infix;\n")
    lines.append('\n      //////////////\n')
    lines.append('      // Bloom Rules\n')
    lines.append(translate_rules(spec['bloom'], 'make_collection'))
    lines.append('      //////////////\n')
    lines.append("    })\n")

  lines.append(fluent_epilogue(spec['name']))
  return "".join(lines)

if __name__ == "__main__":
  parser = argparse.ArgumentParser("Generate Fluent C++ code from YAML spec.")
  parser.add_argument('spec',
                    help='path to the YAML spec file')
  parser.add_argument('-o', '--out',
                    help='output C++ file')


  args = parser.parse_args()

  if (args.out == None):
    codeFd = stdout
  else:
    codeFd = open(args.out, "w")

  codeFd.write(codegen(args.spec))
  codeFd.close()
