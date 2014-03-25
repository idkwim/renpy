# Copyright 2004-2014 Tom Rothamel <pytom@bishoujo.us>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import renpy.display

import renpy.sl2.slast as slast

# A list of style prefixes that we know of.
STYLE_PREFIXES = [
    '',
    'insensitive_',
    'hover_',
    'idle_',
    'activate_',
    'selected_',
    'selected_insensitive_',
    'selected_hover_',
    'selected_idle_',
    'selected_activate_',
]

##############################################################################
# Parsing.

# The parser that things are being added to.
parser = None

# All statements we know about.
all_statements = [ ]

# Statements that can contain children.
childbearing_statements = set()

class Positional(object):
    """
    This represents a positional parameter to a function.
    """

    def __init__(self, name):
        self.name = name

        if parser:
            parser.add(self)

# Used to generate the documentation
all_keyword_names = set()

class Keyword(object):
    """
    This represents an optional keyword parameter to a function.
    """

    def __init__(self, name):
        self.name = name

        all_keyword_names.add(self.name)

        if parser:
            parser.add(self)

class Style(object):
    """
    This represents a style parameter to a function.
    """

    def __init__(self, name):
        self.name = name

        for j in STYLE_PREFIXES:
            all_keyword_names.add(j + self.name)

        if parser:
            parser.add(self)


class PrefixStyle(object):
    """
    This represents a prefixed style parameter to a function.
    """

    def __init__(self, prefix, name):
        self.prefix = prefix
        self.name = name

        for j in STYLE_PREFIXES:
            all_keyword_names.add(prefix + j + self.name)

        if parser:
            parser.add(self)


class Parser(object):

    def __init__(self, name):

        # The name of this object.
        self.name = name

        # The positional arguments, keyword arguments, and child
        # statements of this statement.
        self.positional = [ ]
        self.keyword = { }
        self.children = { }

        all_statements.append(self)

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.name)

    def add(self, i):
        """
        Adds a clause to this parser.
        """

        if isinstance(i, list):
            for j in i:
                self.add(j)

            return

        if isinstance(i, Positional):
            self.positional.append(i)

        elif isinstance(i, Keyword):
            self.keyword[i.name] = i

        elif isinstance(i, Style):
            for j in STYLE_PREFIXES:
                self.keyword[j + i.name] = i

        elif isinstance(i, PrefixStyle):
            for j in STYLE_PREFIXES:
                self.keyword[i.prefix + j + i.name] = i

        elif isinstance(i, Parser):
            self.children[i.name] = i

    def parse_statement(self, l, layout_mode=False):
        word = l.word() or l.match(r'\$')

        if word and word in self.children:
            if layout_mode:
                c = self.children[word].parse_layout(l, self)
            else:
                c = self.children[word].parse(l, self)

            return c
        else:
            return None

    def parse_layout(self, l, parent):
        l.error("The %s statement cannot be used as a container for the has statement." % self.name)

    def parse(self, l, parent):
        """
        This is expected to parse a function statement, and to return
        a list of python ast statements.

        `l` the lexer.

        `name` the name of the variable containing the name of the
        current statement.
        """

        raise Exception("Not Implemented")

    def parse_contents(self, l, target, layout_mode=False, can_has=False, can_tag=False, block_only=False):
        """
        Parses the remainder of the current line of `l`, and all of its subblock,
        looking for keywords and children.

        `layout_mode`
            If true, parsing continues to the end of `l`, rather than stopping
            with the end of the first logical line.

        `can_has`
            If true, we should parse layouts.

        `can_tag`
            If true, we should parse the ``tag`` keyword, as it's used by
            screens.

        `block_only`
            If true, only parse the
        """

        seen_keywords = set()

        # Parses a keyword argument from the lexer.
        def parse_keyword(l):
            name = l.word()

            if name is None:
                l.error('expected a keyword argument, colon, or end of line.')

            if can_tag and name == "tag":
                if target.tag is not None:
                    l.error('keyword argument %r appears more than once in a %s statement.' % (name, self.name))

                target.tag = l.require(l.word)

                return True

            if name not in self.keyword:
                l.error('%r is not a keyword argument or valid child for the %s statement.' % (name, self.name))

            if name in seen_keywords:
                l.error('keyword argument %r appears more than once in a %s statement.' % (name, self.name))

            seen_keywords.add(name)


            expr = l.simple_expression()

            target.keyword.append((name, expr))

        if block_only:
            l.expect_eol()
            l.expect_block(self.name)
            block = True

        else:

            # If not block_only, we allow keyword arguments on the starting
            # line.
            while True:
                if l.match(':'):
                    l.expect_eol()
                    l.expect_block(self.name)
                    block = True
                    break

                if l.eol():
                    l.expect_noblock(self.name)
                    block = False
                    break

                parse_keyword(l)


        # The index of the child we're adding to this statement.
        child_index = 0

        # A list of lexers we need to parse the contents of.
        lexers = [ ]

        if block:
            lexers.append(l.subblock_lexer())

        if layout_mode:
            lexers.append(l)

        # If we have a block, parse it. This also takes care of parsing the
        # block after a has clause.

        for l in lexers:

            while l.advance():

                state = l.checkpoint()

                if l.keyword(r'has'):
                    if self.nchildren != 1:
                        l.error("The %s statement does not take a layout." % self.name)

                    if child_index != 0:
                        l.error("The has statement may not be given after a child has been supplied.")

                    c = self.parse_statement(l, layout_mode=True)

                    if c is None:
                        l.error('Has expects a child statement.')

                    target.children.append(c)

                    continue

                c = self.parse_statement(l)

                if c is not None:
                    target.children.append(c)

                    child_index += 1

                    continue

                l.revert(state)

                while not l.eol():
                    parse_keyword(l)


def add(thing):
    parser.add(thing)

# A singleton value.
many = object()

class DisplayableParser(Parser):
    """
    This is responsible for parsing statements that create displayables.
    """

    def __init__(self, name, displayable, style, nchildren=0, scope=False, text_style=None, pass_context=False):
        """
        `name`
            The name of the statement that creates the displayable.

        `displayable`
            A function that creates the displayable.

        `style`
            The name of the style that is applied to this displayable.

        `nchildren`
            The number of children of this displayable. One of:

            0
                The displayable takes no children.
            1
                The displayable takes 1 child. If more than one child is given,
                the children are placed in a Fixed.
            many
                The displayable takes more than one child.

        `scope`
            If true, the scope is passed into the displayable as a keyword
            argument named "scope".

        `text_style`
            The name of the text style that is applied to this displayable. This
            also enables the whole text style handling mechanism.

        `pass_context`
            If true, the context is passed as the first positional argument of the
            displayable.
        """

        super(DisplayableParser, self).__init__(name)

        # The displayable that is called when this statement runs.
        self.displayable = displayable

        # The number of children we have.
        self.nchildren = nchildren

        # Add us to the appropriate lists.
        global parser
        parser = self

        if nchildren != 0:
            childbearing_statements.add(self)

        self.style = style
        self.scope = scope
        self.text_style = text_style
        self.pass_context = pass_context

    def parse_layout(self, l, parent):
        return self.parse(l, parent, True)

    def parse(self, l, parent, layout_mode=False):

        rv = slast.SLDisplayable(self.displayable, scope=self.scope, child_or_fixed=(self.nchildren == 1),
            style=self.style, text_style=self.text_style, pass_context=self.pass_context)

        for _i in self.positional:
            rv.positional.append(l.simple_expression())

        can_has = (self.nchildren == 1)
        self.parse_contents(l, rv, layout_mode=layout_mode, can_has=can_has, can_tag=False)

        return rv

class IfParser(Parser):

    def __init__(self, name):
        super(IfParser, self).__init__(name)

    def parse(self, l, parent):

        rv = slast.SLIf()

        condition = l.require(l.python_expression)

        l.require(':')

        block = slast.SLBlock()
        parent.parse_contents(l, block, block_only=True)

        rv.entries.append((condition, block))

        state = l.checkpoint()

        while l.advance():

            if l.keyword("elif"):

                condition = l.require(l.python_expression)
                l.require(':')

                block = slast.SLBlock()
                parent.parse_contents(l, block, block_only=True)

                rv.entries.append((condition, block))

                state = l.checkpoint()

            elif l.keyword("else"):

                condition = None
                l.require(':')

                block = slast.SLBlock()
                parent.parse_contents(l, block, block_only=True)

                rv.entries.append((condition, block))

                state = l.checkpoint()

                break

            else:
                l.revert(state)
                break

        return rv

if_statement = IfParser("if")

class ForParser(Parser):

    def __init__(self, name):
        super(ForParser, self).__init__(name)
        childbearing_statements.add(self)

    def name_or_tuple_pattern(self, l):
        """
        Matches either a name or a tuple pattern. If a single name is being
        matched, returns it. Otherwise, returns None.
        """

        while True:

            if l.match(r"\("):
                name = self.name_or_tuple_pattern(l)
                l.require(r'\)')
            else:
                name = l.name()

                if not name:
                    l.error("Expected tuple pattern.")

            if l.match(r","):
                name = None
            else:
                break

        return name

    def parse(self, l, parent):

        l.skip_whitespace()

        tuple_start = l.pos
        name = self.name_or_tuple_pattern(l)

        if not name:
            name = "_i_" + str(self.serial)
            pattern = l.text[tuple_start:l.pos]
            stmt = pattern + " = " + name
            code = renpy.ast.PyCode(stmt, (l.filename, l.lineno))
        else:
            code = None

        l.require('in')

        expression = l.require(l.python_expression)

        l.require(':')
        l.expect_eol()

        rv = slast.SLFor(name, expression)

        if code:
            rv.children.append(slast.SLPython(code))

        self.parse_contents(l, rv, block_only=True)

        return rv

ForParser("for")


class OneLinePythonParser(Parser):

    def parse(self, l, parent):

        loc = l.get_location()
        source = l.require(l.rest)

        l.expect_eol()
        l.expect_noblock("one-line python")

        code = renpy.ast.PyCode(source, loc)
        return slast.SLPython(code)

OneLinePythonParser("$")


class ScreenLangScreen(renpy.object.Object):
    """
    This represents a screen defined in the screen language.
    """

    def __init__(self):

        # The name of the screen.
        self.name = None

        # Should this screen be declared as modal?
        self.modal = "False"

        # The screen's zorder.
        self.zorder = "0"

        # The screen's tag.
        self.tag = None

        # The variant of screen we're defining.
        self.variant = "None" # expr.

        # Should we predict this screen?
        self.predict = "None" # expr.

        # The parameters this screen takes.
        self.parameters = None

        # True if this screen has been prepared.
        self.prepared = False

        # The keywords that make up the screen. (This is removed once parsing
        # is finished.)
        self.keywords = [ ]

        # The children that make up the screen's ast.
        self.children = [ ]

    def define(self):
        """
        Defines a screen.
        """

        renpy.display.screen.define_screen(
            self.name,
            self,
            modal=self.modal,
            zorder=self.zorder,
            tag=self.tag,
            variant=renpy.python.py_eval(self.variant),
            predict=renpy.python.py_eval(self.predict),
            parameters=self.parameters,
            )

    def __call__(self, *args, **kwargs):
        scope = kwargs["_scope"]

        if self.parameters:

            args = scope.get("_args", ())
            kwargs = scope.get("_kwargs", { })

            values = renpy.ast.apply_arguments(self.parameters, args, kwargs)
            scope.update(values)

        context = slast.SLContext()
        context.scope = scope

        if not self.prepared:
            self.prepared = True

            for i in self.children:
                i.prepare()

        for i in self.children:
            i.execute(context)

        for i in context.children:
            renpy.ui.add(i)


class ScreenParser(Parser):

    def __init__(self):
        super(ScreenParser, self).__init__("screen")

    def parse(self, l, parent, name="_name"):

        screen = ScreenLangScreen()

        screen.name = l.require(l.word)
        screen.parameters = renpy.parser.parse_parameters(l)

        self.parse_contents(l, screen, can_tag=True)

        keywords = dict(screen.keywords)

        screen.modal = keywords.get("modal", "False")
        screen.zorder = keywords.get("modal", "0")
        screen.variant = keywords.get("modal", "None")
        screen.predict = keywords.get("modal", "None")

        del screen.keywords

        return screen

screen_parser = ScreenParser()
Keyword("modal")
Keyword("zorder")
Keyword("variant")
Keyword("predict")

def init():
    screen_parser.add(all_statements)

    for i in all_statements:

        if i in childbearing_statements:
            i.add(all_statements)
        else:
            i.add(if_statement)



def parse_screen(l):
    """
    Parses the screen statement.
    """

    return screen_parser.parse(l, None)
