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
import string
import tatsu

class BloomSemantics(object):
  """docstring for BloomSemantics"""

  schema = {}
  rules = {}
  tups = {}
  tupbuf = []

  def start(self, ast):
    args = { i[0]: i[1] for i in ast.args}

    # args
    retval = fluent_prologue(ast.name, args)

    # schema
    retval += '''
    ///////////////
    // Bloom Schema
'''
    retval += '\n'.join(('    .' + l) for l in translate_schema(self.schema))
    retval += '''
    ///////////////
    ;
'''

    # constant tuples
    for k in self.tups.keys():
      # first the type
      retval += '  using ' + k + '_tuple_t = std::tuple<'
      retval += ', '.join(v for _,v in self.schema[k]['cols'].items())
      retval += '>;\n'
      # then the constant collection
      retval += '  std::vector<' + k + '_tuple_t> ' + k + '_tuples = {\n'
      retval += (';\n'.join('    std::make_tuple(' + ', '.join(a.strip() for a in tup) + ')' for tup in self.tups[k]))
      retval += ';\n  };\n'

    # bootstrap logic
    retval += self.register_rules('Bootstrap', ast.blogic)
    # bloom logic
    retval += self.register_rules('', ast.logic)

    # epilogue
    retval += fluent_epilogue(ast.name)
    return retval

  def register_rules(self, bootp, rules):
    if rules == None or len(rules) == 0:
      return ''

    retval = "  bloom = std::move(bloom)\n"
    retval += "    .Register" + bootp + "Rules([&]("
    retval += ", ".join(('auto& ' + k) for k in self.schema.keys())
    retval += ") {\n"
    retval += "\n".join('      (void)' + l + ';' for l in self.schema.keys())
    retval += '''
      using namespace fluent::infix;

      //////////////
      // Bloom ''' + bootp + ''' Rules
'''
    retval += rules
    retval += '      return std::make_tuple('
    retval += ", ".join(self.rules.keys()) + ');\n'
    retval += '''      //////////////
    })
'''
    return retval


  def logic(self, ast):
    return ''.join(ast)

  def stmt(self, ast):
    if ast != '':
      return '      ' + ast + ';\n'
    else:
      return ast

  def ruledef(self, ast):
    self.rules[ast.var] = ast.rule
    return "auto " + ast.var + " = " + ast.rule     

  def rule(self, ast):
    if ast.rhs == None:
      self.tups[ast.lhs] = self.tupbuf
      self.tupbuf = []
      rhs = 'lra::make_iterable(&' + ast.lhs + '_tuples)'
    else:
      rhs = ast.rhs
    return ast.lhs + ' ' + ast.mtype + ' ' + rhs

  def catalog_entry(self, ast, type):
    retval = (''.join(ast))
    if (retval == 'stdin'):
      return 'fluin'
    elif (retval == 'stdout'):
      return 'fluout'
    else:
      return retval

  def rhs(self, ast):
    retval = "("
    if ast.anchor != None:
      retval += ast.anchor
      if ast.chain != None:
        retval += ' | '
    if ast.chain != None:
      retval += ' | '.join(ast.chain)
    if ast.tups != None:
      self.tupbuf = ast.tups
      return None

    return retval + ")"
    
  def op(self, ast):
    retval = ast.opname
    if ast.plist != None:
      retval += "<" + ','.join(ast.plist) + ">"
    retval += "("
    if type(ast.op_args) == list:
      retval += ', '.join(ast.op_args)
    elif ast.op_args != None:
      retval += '[&]'
      retval += '(const '
      retval += 'auto'
      retval += '& ' + ast.op_args.argname + ')'
      retval += ast.op_args.code.code
    retval += ')'
    return(retval)

  def opname(self, ast):
    return "lra::" + ast

  def rhs_catalog_entry(self, ast):
    return self.cwrap + "(&" + ast + ")"

  def where(self, ast):
    return "filter"

  def cross(self, ast):
    return "make_cross"

  def now(self, ast):
    return "<="

  def next(self, ast):
    return "+="

  def async(self, ast):
    return "<="

  def delete(self, ast):
    return "-="  

  def schemadef(self, ast):
    if ast.name == 'stdin':
      self.schema['fluin'] = None;
    elif ast.name == 'stdout':
      self.schema['fluout'] = None;
    else:
      collection_type = ast.type
      collection_name = ast.name
      cols = { i[0]: i[1] for i in ast.cols}
      self.schema[collection_name] = {
        'type': collection_type,
        'cols': cols
      }
    return ""

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
  auto bloom = fluent::fluent<fluent::lineagedb::NoopClient,fluent::Hash,
                           fluent::lineagedb::ToSql,fluent::MockPickler,
                           std::chrono::system_clock>
                           ("'''
  retval += name + '''_" + std::to_string(rand()),
                                    args.address, &context,
                                    connection_config)
    .ConsumeValueOrDie();
  bloom = std::move(bloom)
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
  i = 0
  for tabname in spec['preload'].keys():
    # ruledef = tabname + " <= lra::make_iterable(&" + make_collection_name(tabname) + ")"
    ruledef = tabname + " <= " + make_collection_name(tabname) + ';'
    if not ('bootstrap' in spec):
      spec.update({'bootstrap': {}})
    spec['bootstrap'][tabname + "_boot"] = ruledef
  return retval

# def convert_mtype(m):
#   if m == '<+':
#     return '+='
#   elif m == '<-':
#     return '-='
#   else:
#     return '<='

# def translate_chain(ast, collection_wrap):
#   return ' | '.join([translate_op(o, collection_wrap) for o in ast])

# def translate_op(op, collection_wrap):
#   opname = op.opname
#   if opname == 'cross':
#     opname = 'make_cross'
#   elif opname == 'where':
#     opname = 'filter'
#   retval = 'lra::' + opname
#   if not op.plist == None:
#     retval += '<' + ''.join(o for o in op.plist) + '>'
#   retval += '('
#   if op.op_args != None:
#     retval += translate_op_args(op.op_args, collection_wrap)
#   retval += ')'
#   return retval

# def wrap_collection(c, collection_wrap): 
#   return 'lra::' + collection_wrap + '(&' + c + ')'

# def translate_op_args(args, collection_wrap):
#   retval = ''
#   if type(args) == list:
#     retval += ', '.join(wrap_collection(a, collection_wrap) for a in args)
#   elif args.code != None:
#     retval += '[&]'
#     retval += '(const '
#     retval += 'auto'
#     retval += '& ' + args.argname + ')'
#     retval += args.code.code  
#   return retval

# def expand_ruledict(r, collection_wrap):
#   retval = r.lhs + ' ' + convert_mtype(r.mtype) + ' ('
#   if r.rhs.anchor != None:
#     retval += wrap_collection(r.rhs.anchor, collection_wrap)
#     if r.rhs.chain != None:
#       retval += ' | '
#   if r.rhs.chain != None:
#     retval += translate_chain(r.rhs.chain, collection_wrap)
#   # pprint.pprint(r.rhs.chain)
#   # if not r.rhs.chain == None:
#   #   retval += (' | ').join(translate_op(op) for op in r.rhs.chain)
#   retval += ')'
#   return retval

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
    grammar = open('./fluent.tatsu').read()
    sem = BloomSemantics();
    setattr(sem, "cwrap", collection_wrap)
    v = tatsu.parse(grammar, k +': ' + v, parseinfo=True, semantics=sem)
    retval += ("      auto " + v)
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
    # we ignore the definition for stdin and stdout
    if (name == 'fluin'):
      result.append('stdin' + '()')
    elif name == 'fluout':
      result.append('stdout' + '()')
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
    lines.append(translate_rules(spec['bootstrap'], 'lra::make_iterable'))
    lines.append('      ////////////////////////\n')
    lines.append("    })\n")
    lines.append(';\n')
    lastvar = "bootstrap"

  if ('bloom' in spec):
    lines.append("  bloom = std::move(" + lastvar + ")\n")
    lines.append("    .RegisterRules([&](")
    lines.append(arglist_tablenames(schema))
    lines.append(") {\n")
    lines.append(useTables)
    lines.append("      using namespace fluent::infix;\n")
    lines.append('\n      //////////////\n')
    lines.append('      // Bloom Rules\n')
    lines.append(translate_rules(spec['bloom'], 'lra::make_collection'))
    lines.append('      //////////////\n')
    lines.append("    })\n")

  lines.append(fluent_epilogue(spec['name']))
  return "".join(lines)

def fullparse(specFile):
  """convert Bloom spec to a Fluent C++ header file

  Args:
    specFile (str): path to the .yml file

  Returns:
    text of the C++ file
  """
  spec = open(specFile).read()
  grammar = open('./fluent2.tatsu').read()
  sem = BloomSemantics();
  setattr(sem, "cwrap", "")
  parser = tatsu.compile(grammar)
  retval = parser.parse(spec, semantics=sem)

  return retval

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

  result = fullparse(args.spec)
  codeFd.write(result)
  codeFd.close()
