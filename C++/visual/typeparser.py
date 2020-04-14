from lark import Lark

l = Lark('''start: c
            c: a | a"::"c
            a: WORD "<" [c ("," c)*] ">" /[\*]+/ | WORD "<" [c ("," c)*] ">" | WORD
            METADATA: /[\*]+/
            _metadata: METADATA?
            WORD: /[A-Za-z0-9 _*]+/
            %import common.WS
            %ignore WS
            ''')

t = l.parse("void*")
# print(t.children[0].children[1].children[0].children[1].children[0])
print(t.data)

t = t.children[0]

while t.data == 'c' and len(t.children) == 2:
    t = t.children[1]

print(t.data)

t = t.children[0].children[0]

print(t)