import ast, sys
try:
    with open('main.py', encoding='utf-8') as f:
        ast.parse(f.read())
    with open('_syntax_result.txt', 'w') as out:
        out.write('SYNTAX OK\n')
except SyntaxError as e:
    with open('_syntax_result.txt', 'w') as out:
        out.write(f'SYNTAX ERROR: {e}\n')
    sys.exit(1)
