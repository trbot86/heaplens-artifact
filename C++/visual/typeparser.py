from lark import Lark

l = Lark('''start: c
            c: a | a"::"c
            a: WORD "<" [c ("," c)*] ">" e | WORD "<" [c ("," c)*] ">" | WORD
            e: /[\*]+/
            WORD: /[A-Za-z0-9 _*]+/
            %import common.WS
            %ignore WS
            ''')

def parsetypeandpointer(inpt):
    t = l.parse(inpt)
    # print(t.pretty())

    t = t.children[0]

    while t.data == 'c' and len(t.children) == 2:
        t = t.children[1]
        # print(t.data)

    t = t.children[0]

    stars = ""

    if len(t.children) >= 3 and t.children[len(t.children)-1].data == 'e':
        stars = t.children[len(t.children)-1].children[0]
        # print("stars: ",stars)

    t = t.children[0]

    return t+stars

parsetypeandpointer("blockpool<bst_glock_ns::Node<long long, void*>, void* >***")