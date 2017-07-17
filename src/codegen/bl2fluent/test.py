import tatsu
from pprint import pprint

class BloomSemantics(object):
  """docstring for BloomSemantics"""
  def logic(self, ast):
    return ''.join(ast)

  def ruledef(self, ast):
    return ast.var + " = " + ast.rule + ';\n'

  def rule(self, ast):
    return ast.lhs + ' ' + ast.mtype + ' ' + ast.rhs

  def catalog_entry(self, ast, type):
    return(''.join(ast))

  def rhs(self, ast):
    retval = "("
    if ast.anchor != None:
      retval += ast.anchor
      if ast.chain != None:
        retval += ' | '
    if ast.chain != None:
      retval += ' | '.join(ast.chain)
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





grammar = open('./fluent2.tatsu').read()
bloom = open('./test.txt').read()
sem = BloomSemantics()
setattr(sem, 'cwrap', 'lra::make_collection')
result = tatsu.parse(grammar, bloom, semantics=sem)
print(result)