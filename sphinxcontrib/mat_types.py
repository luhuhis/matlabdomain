# -*- coding: utf-8 -*-
"""
    sphinxcontrib.mat_types
    ~~~~~~~~~~~~~~~~~~~~~~~

    Types for MATLAB.

    :copyright: Copyright 2014 Mark Mikofski
    :license: BSD, see LICENSE for details.
"""

import os
import sys
from copy import copy

from pygments.lexers import MatlabLexer
from pygments.token import Token

# TODO: use `self.tokens.pop()` instead of idx += 1, see MatFunction

# XXX: Don't use `type()` or metaclasses. Not trivial to create metafunctions.
# XXX: Some special attributes **are** required even though `getter()` methods
# are also used.

# create some MATLAB objects
# TODO: +packages & @class folders
# TODO: subfunctions (not nested) and private folders/functions/classes
# TODO: script files
# TODO: remove continuation dots "...\n" in all mfiles with 
class MatObject(object):
    """
    Base MATLAB object to which all others are subclassed.

    :param name: Name of MATLAB object.
    :type name: str

    MATLAB objects can be :class:`MatModule`, :class:`MatFunction` or
    :class:`MatClass`. :class:`MatModule` are just folders that define a psuedo
    namespace for :class:`MatFunction` and :class:`MatClass` in that folder.
    :class:`MatFunction` and :class:`MatClass` must begin with either
    ``function`` or ``classdef`` keywords.
    """
    def __init__(self, name):
        #: name of MATLAB object
        self.name = name

    @property
    def __name__(self):
        return self.name

    def __repr__(self):
        # __str__() method not required, if not given, then __repr__() used
        return '<%s: "%s">' % (self.__class__.__name__, self.name)

    def getter(self, name, *defargs):
        if name == '__name__':
            return self.__name__
        elif len(defargs) == 1:
            return defargs[0]
        else:
            return defargs

    @staticmethod
    def matlabify(basedir, objname):
        """
        Makes a MatObject.

        :param basedir: Config value of ``matlab_src_dir``, path to source.
        :type basedir: str
        :param objname: Name of object to matlabify without file extension.
        :type objname: str

        Assumes that object is contained in a folder described by a namespace
        composed of modules and packages connected by dots, and that the top-
        level module or package is in the Sphinx config value ``basedir``. For
        example: ``my_project.my_package.sub_pkg.MyClass`` represents either a
        folder ``basedir/my_project/my_package/sub_pkg/MyClass`` or an mfile
        ``basedir/my_project/my_package/sub_pkg/MyClass.m``. If there is both a
        folder and an mfile with the same name, the folder takes precedence
        over the mfile.
        """
        # no object name given
        if not objname:
            return None
        # matlab modules are really packages
        package = objname  # for packages it's namespace of __init__.py
        # convert namespace to path
        objname = objname.replace('.', os.sep)  # objname may have dots
        # separate path from file/folder name
        path, name = os.path.split(objname)
        # make a full path out of basedir and objname
        fullpath = os.path.join(basedir, objname)  # fullpath to objname
        # package folders imported over mfile with same name
        if os.path.isdir(fullpath):
            return MatModule(name, fullpath, package)  # import package
        elif os.path.isfile(fullpath + '.m'):
            mfile = fullpath + '.m'
            return MatObject.parse_mfile(mfile, name, path)  # parse mfile
        return None

    @staticmethod
    def parse_mfile(mfile, name, path):
        """
        Use Pygments to parse mfile to determine type: function or class.

        :param mfile: Full path of mfile.
        :type mfile: str
        :param name: Name of :class:`MatObject`.
        :type name: str
        :param path: Path of module containing :class:`MatObject`.
        :type path: str
        :returns: :class:`MatObject` that represents the type of mfile.

        Assumes that the first token in the file is either one of the keywords:
        "classdef" or "function" otherwise it is assumed to be a script.
        """
        # use Pygments to parse mfile to determine type: function/classdef
        # read mfile code
        with open(mfile, 'r') as f:
            code = f.read()
        code = code.replace('...\n','')  # replace all ellipsis
        tks = list(MatlabLexer().get_tokens(code))  # tokenenize code
        modname = path.replace(os.sep, '.')  # module name
        # assume that functions and classes always start with a keyword
        if tks[0] == (Token.Keyword, 'function'):
            return MatFunction(name, modname, tks)
        elif tks[0] == (Token.Keyword, 'classdef'):
            return MatClass(name, modname, tks)
        else:
            # it's a script file
            return MatScript(name, modname, tks)
        return None


class MatModule(MatObject):
    """ 
    All MATLAB modules are packages. A package is a folder that serves as the
    namespace for any :class:`MatObjects` in the package folder. Sphinx will
    treats objects without a namespace as builtins, so all MATLAB projects
    should be packaged in a folder so that they will have a namespace. This
    can also be accomplished by using the MATLAB +folder package scheme.

    :param name: Name of :class:`MatObject`.
    :type name: str
    :param path: Path of folder containing :class:`MatObject`.
    :type path: str
    """
    def __init__(self, name, path, package):
        super(MatModule, self).__init__(name)
        #: Path to module on disk, path to package's __init__.py
        self.path = path
        #: name of package (same as module)
        self.package = package
        # add module to system dictionary
        sys.modules[name] = self

    def safe_getmembers(self):
        results = []
        for key in os.listdir(self.path):
            # make full path
            path = os.path.join(self.path, key)
            # don't visit vcs directories
            if os.path.isdir(path) and key in ['.git', '.hg', '.svn', '.bzr']:
                continue
            # only visit mfiles
            if os.path.isfile(path) and not key.endswith('.m'):
                continue
            # trim file extension
            if os.path.isfile(path):
                key, _ = os.path.splitext(key)
            if not results or key not in zip(*results)[0]:
                value = self.getter(key, None)
                if value:
                    results.append((key, value))
        results.sort()
        return results

    @property
    def __doc__(self):
        return None

    @property
    def __all__(self):
        results = self.safe_getmembers
        if results:
            results = zip(*self.safe_getmembers)[0]
        return results

    @property
    def __path__(self):
        return [self.path]

    @property
    def __file__(self):
        return self.path

    @property
    def __package__(self):
        return self.package

    def getter(self, name, *defargs):
        """
        :class:`MatModule` ``getter`` method to get attributes.
        """
        if name == '__name__':
            return self.__name__
        elif name == '__doc__':
            return self.__doc__
        elif name == '__all__':
            return self.__all__
        elif name == '__file__':
            return self.__file__
        elif name == '__path__':
            return self.__path__
        elif name == '__package__':
            return self.__package__
        else:
            pkg = self.package.split('.')  # list of object paths in package
            # basedir is portion of path minus the package
            basedir = self.path.rsplit(os.sep, len(pkg))  # split path
            basedir = basedir[0]  # MATLAB base src folder
            attr = MatObject.matlabify(basedir, '.'.join([self.package, name]))
            if attr:
                return attr
            else:
                super(MatModule, self).getter(name, *defargs)


class MatMixin(object):
    """
    Methods to comparing and manipulating tokens in :class:`MatFunction` and
    :class:`MatClass`.
    """
    def _tk_eq(self, idx, token):
        """
        Returns ``True`` if token keys are the same and values are equal.

        :param idx: Index of token in :class:`MatObject`.
        :type idx: int
        :param token: Comparison token.
        :type token: tuple
        """
        return (self.tokens[idx][0] is token[0] and
                self.tokens[idx][1] == token[1])
    def _tk_ne(self, idx, token):
        """
        Returns ``True`` if token keys are not the same or values are not equal.

        :param idx: Index of token in :class:`MatObject`.
        :type idx: int
        :param token: Comparison token.
        :type token: tuple
        """
        return (self.tokens[idx][0] is not token[0] or
                self.tokens[idx][1] != token[1])
    def _eotk(self, idx):
        """
        Returns ``True`` if end of tokens is reached.
        """
        return idx >= len(self.tokens)

    def _blanks(self, idx):
        """
        Returns number of blank text tokens.

        :param idx: Token index.
        :type idx: int
        """
        # idx0 = idx  # original index
        # while self._tk_eq(idx, (Token.Text, ' ')): idx += 1
        # return idx - idx0  # blanks
        return self._indent(idx)

    def _whitespace(self, idx):
        """
        Returns number of whitespaces text tokens, including blanks, newline
        and tabs.

        :param idx: Token index.
        :type idx: int
        """
        idx0 = idx  # original index
        while (self.tokens[idx][0] is Token.Text and
               self.tokens[idx][1] in [' ', '\n', '\t']):
            idx += 1
        return idx - idx0  # whitespace

    def _indent(self, idx):
        """
        Returns indentation tabs or spaces. No indentation is zero.

        :param idx: Token index.
        :type idx: int
        """
        idx0 = idx  # original index
        while (self.tokens[idx][0] is Token.Text and
               self.tokens[idx][1] in [' ', '\t']):
            idx += 1
        return idx - idx0  # indentation


class MatFunction(MatObject):
    """
    A MATLAB function.

    :param name: Name of :class:`MatObject`.
    :type name: str
    :param modname: Name of folder containing :class:`MatObject`.
    :type modname: str
    :param tokens: List of tokens parsed from mfile by Pygments.
    :type tokens: list
    """
    # MATLAB keywords that increment keyword-end pair count
    mat_kws = zip((Token.Keyword,) * 5,
                  ('if', 'while', 'for', 'switch', 'try'))
    def __init__(self, name, modname, tokens):
        super(MatFunction, self).__init__(name)
        #: Path of folder containing :class:`MatObject`.
        self.module = modname
        #: List of tokens parsed from mfile by Pygments.
        self.tokens = tokens
        #: docstring
        self.docstring = ''
        #: output args
        self.retv = None
        #: input args
        self.args = None
        #: remaining tokens after main function is parsed
        self.rem_tks = None
        # =====================================================================
        # parse tokens
        # XXX: Pygments always reads MATLAB function signature as:
        # [(Token.Keyword, 'function'),  # any whitespace is stripped
        #  (Token.Text.Whitesapce, ' '),  # spaces and tabs are concatenated
        #  (Token.Text, '[o1, o2]'),  # if there are outputs, they're all
        #                               concatenated w/ or w/o brackets and any
        #                               trailing whitespace
        #  (Token.Punctuation, '='),  # possibly an equal sign
        #  (Token.Text.Whitesapce, ' '),  # spaces and tabs are concatenated
        #  (Token.Name.Function, 'myfun'),  # the name of the function
        #  (Token.Punctuation, '('),  # opening parenthesis
        #  (Token.Text, 'a1, a2',  # if there are args, they're concatenated
        #  (Token.Punctuation, ')'),  # closing parenthesis
        #  (Token.Text.Whitesapce, '\n')]  # all whitespace after args 
        # XXX: Pygments does not tolerate MATLAB continuation ellipsis!
        tks = copy(self.tokens)  # make a copy of tokens
        tks.reverse()  # reverse in place for faster popping, stacks are LiLo
        # =====================================================================
        # parse function signature
        # function [output] = name(inputs)
        # % docstring
        # =====================================================================
        # check function keyword
        func_kw = tks.pop()  # function keyword
        if func_kw[0] is not Token.Keyword or func_kw[1].strip() != 'function':
            raise TypeError('Object is not a function. Expected a function.')
            # TODO: what is a better error here?
        # skip blanks and tabs
        if tks.pop()[0] is not Token.Text.Whitespace:
            raise TypeError('Expected a whitespace after function keyword.')
            # TODO: what is a better error here?
        # =====================================================================
        # output args
        retv = tks.pop()  # return values
        if retv[0] is Token.Text:
            self.retv = [rv.strip() for rv in retv[1].strip('[ ]').split(',')]
            if tks.pop() != (Token.Punctuation, '='):
                raise TypeError('Token after outputs should be Punctuation.')
                # TODO: raise an matlab token error or what?
            # check for whitespace after equal sign
            wht = tks.pop()
            if wht[0] is not Token.Text.Whitespace:
                tks.append(wht)  # if not whitespace, put it back in list
        # =====================================================================
        # function name
        func_name = tks.pop()
        if func_name != (Token.Name.Function, self.name):
            if isinstance(self, MatMethod):
              self.name = func_name[1]
            else:
                errmsg = 'Unexpected function name: "%s".' % func_name[1]
                raise Exception(errmsg)
                # TODO: create mat_types or tokens exceptions!
        # =====================================================================
        # input args
        if tks.pop() == (Token.Punctuation, '('):
            args = tks.pop()
            if args[0] is Token.Text:
                self.args = [arg.strip() for arg in args[1].split(',')]
            if tks.pop() != (Token.Punctuation, ')'):
                raise TypeError('Token after outputs should be Punctuation.')
                # TODO: raise an matlab token error or what?
        # skip blanks and tabs
        if tks.pop()[0] is not Token.Text.Whitespace:
            raise TypeError('Expected a whitespace after input args.')
            # TODO: what is a better error here?
        # =====================================================================
        # docstring
        docstring = tks.pop()
        while docstring[0] is Token.Comment:
            self.docstring += docstring[1].lstrip('%') + '\n'  # concatenate
            wht = tks.pop()  # skip whitespace
            while wht in zip((Token.Text,) * 3, (' ', '\t', '\n')):
                wht = tks.pop()
            docstring = wht  # check if Token is Comment
        # =====================================================================
        # main body
        # find Keywords - "end" pairs
        kw = docstring  # last token
        lastkw = ''  # set last keyword placeholder
        kw_end = 1  # count function keyword
        while kw_end > 0:
            if kw in MatFunction.mat_kws:
                kw_end += 1
            elif kw == (Token.Keyword, 'end'):
                # don't decrement `end` used as index
                if lastkw not in zip((Token.Punctuation,) * 2, (':', '(')):
                    kw_end -= 1
            try:
                lastkw, kw = kw, tks.pop()
            except IndexError:
                break
        tks.append(kw)  # put last token back in list
        # if there are any tokens left save them
        if len(tks) > 0:
            self.rem_tks = tks  # save extra tokens

    @property
    def __doc__(self):
        return unicode(self.docstring)

    @property
    def __module__(self):
        return self.module

    def getter(self, name, *defargs):
        if name == '__name__':
            return self.__name__
        elif name == '__doc__':
            return self.__doc__
        elif name == '__module__':
            return self.__module__
        else:
            super(MatFunction, self).getter(name, *defargs)


class MatClass(MatMixin, MatObject):
    """
    A MATLAB class definition.

    :param name: Name of :class:`MatObject`.
    :type name: str
    :param path: Path of folder containing :class:`MatObject`.
    :type path: str
    :param tokens: List of tokens parsed from mfile by Pygments.
    :type tokens: list
    """
    #: dictionary of MATLAB class "attributes"
    # http://www.mathworks.com/help/matlab/matlab_oop/class-attributes.html
    cls_attr_types = {'Abstract': bool, 'AllowedSubclasses': list,
                      'ConstructOnLoad': bool, 'HandleCompatible': bool,
                      'Hidden': bool, 'InferiorClasses': list, 'Sealed': bool}
    prop_attr_types = {'AbortSet': bool, 'Abstract': bool, 'Access': list,
                       'Constant': bool, 'Dependent': bool, 'GetAccess': list,
                       'GetObservable': bool, 'Hidden': bool, 'SetAccess': list,
                       'SetObservable': bool, 'Transient': bool}
    meth_attr_types = {'Abstract': bool, 'Access': list, 'Hidden': bool,
                       'Sealed': list, 'Static': bool}
    def __init__(self, name, modname, tokens):
        super(MatClass, self).__init__(name)
        #: Path of folder containing :class:`MatObject`.
        self.module = modname
        #: List of tokens parsed from mfile by Pygments.
        self.tokens = tokens
        #: dictionary of class attributes
        self.attrs = {}
        #: list of class superclasses
        self.bases = []
        #: docstring
        self.docstring = ''
        #: dictionary of class properties
        self.properties = {}
        #: dictionary of class methods
        self.methods = {}
        #: remaining tokens after main class definition is parsed
        self.rem_tks = None
        # =====================================================================
        # parse tokens
        # TODO: use generator and next() instead of stepping index!
        idx = 0  # token index
        # check classdef keyword
        if self._tk_ne(idx, (Token.Keyword, 'classdef')):
            raise TypeError('Object is not a class. Expected a class.')
        idx += 1
        # TODO: allow continuation dots "..." in signature
        # parse classdef signature
        # classdef [(Attributes [= true], Attributes [= {}] ...)] name ...
        #   [< bases & ...]
        # % docstring
        # =====================================================================
        # class "attributes"
        self.attrs, idx = self.attributes(idx, MatClass.cls_attr_types)
        # =====================================================================
        # classname
        idx += self._blanks(idx)  # skip blanks
        if self._tk_ne(idx, (Token.Name, self.name)):
            errmsg = 'Unexpected class name: "%s".' % self.tokens[idx][1]
            raise Exception(errmsg)
            # TODO: create exception classes
        idx += 1
        idx += self._blanks(idx)  # skip blanks
        # =====================================================================
        # super classes
        if self._tk_eq(idx, (Token.Operator, '<')):
            idx += 1
            # newline terminates superclasses
            while self._tk_ne(idx, (Token.Text, '\n')):
                idx += self._blanks(idx)  # skip blanks
                # concatenate base name
                base_name = ''
                while not self._whitespace(idx):
                    base_name += self.tokens[idx][1]
                    idx += 1
                # if newline, don't increment index
                if self._tk_ne(idx, (Token.Text, '\n')):
                    idx += 1
                if base_name:
                    self.bases.append(base_name)
                idx += self._blanks(idx)  # skip blanks
                # continue to next super class separated by &
                if self._tk_eq(idx, (Token.Operator, '&')):
                    idx += 1
            idx += 1  # end of super classes
        # newline terminates classdef signature
        elif self._tk_eq(idx, (Token.Text, '\n')):
            idx += 1  # end of classdef signature
        # =====================================================================
        # docstring
        # Must be immediately after class and indented
        indent = self._indent(idx)  # calculation indentation
        if indent:
            idx += indent
            # concatenate docstring
            while self.tokens[idx][0] is Token.Comment:
                self.docstring += self.tokens[idx][1].lstrip('%')
                idx += 1
                # append newline to docstring
                if self._tk_eq(idx, (Token.Text, '\n')):
                    self.docstring += self.tokens[idx][1]
                    idx += 1
                # skip tab
                indent = self._indent(idx)  # calculation indentation
                if indent:
                    idx += indent
        elif self.tokens[idx][0] is Token.Comment:
            raise Exception('Comments must be indented.')
            # TODO: add to matlab domain exceptions
        # =====================================================================
        # properties & methods blocks
        # loop over code body searching for blocks until end of class
        while self._tk_ne(idx, (Token.Keyword, 'end')):
            # skip comments and whitespace
            while (self._whitespace(idx) or
                   self.tokens[idx][0] is Token.Comment):
                whitespace = self._whitespace(idx)
                if whitespace:
                    idx += whitespace
                else:
                    idx += 1
            # =================================================================
            # properties blocks
            if self._tk_eq(idx, (Token.Keyword, 'properties')):
                idx += 1
                # property "attributes"
                attr_dict, idx = self.attributes(idx, MatClass.prop_attr_types)
                # Token.Keyword: "end" terminates properties & methods block
                while self._tk_ne(idx, (Token.Keyword, 'end')):
                    # skip comments and whitespace
                    while (self._whitespace(idx) or
                           self.tokens[idx][0] is Token.Comment):
                        whitespace = self._whitespace(idx)
                        if whitespace:
                            idx += whitespace
                        else:
                            idx += 1
                    # TODO: alternate multiline docstring before property
                    # with "%:" directive trumps docstring after property
                    if self.tokens[idx][0] is Token.Name:
                        prop_name = self.tokens[idx][1]
                        self.properties[prop_name] = {'attrs': attr_dict}
                        idx += 1
                    else:
                        raise TypeError('Expected property.')
                    idx += self._blanks(idx)  # skip blanks
                    # defaults
                    default = {'default': None}
                    if self._tk_eq(idx, (Token.Punctuation, '=')):
                        idx += 1
                        idx += self._blanks(idx)  # skip blanks
                        # concatenate default value until newline or comment
                        default = ''
                        while (self._tk_ne(idx, (Token.Text, '\n')) and
                               self.tokens[idx][0] is not Token.Comment):
                            default += self.tokens[idx][1]
                            idx += 1
                        if self.tokens[idx][0] is not Token.Comment:
                            idx += 1
                        if default:
                            default = {'default': default.rstrip()}
                    self.properties[prop_name].update(default)
                    docstring = {'docstring': None}
                    if self.tokens[idx][0] is Token.Comment:
                        docstring['docstring'] = self.tokens[idx][1].lstrip('%')
                        idx += 1
                    self.properties[prop_name].update(docstring)
                    idx += self._whitespace(idx)
                idx += 1
            # =================================================================
            # method blocks
            if self._tk_eq(idx, (Token.Keyword, 'methods')):
                idx += 1
                # method "attributes"
                attr_dict, idx = self.attributes(idx, MatClass.meth_attr_types)
                # Token.Keyword: "end" terminates properties & methods block
                while self._tk_ne(idx, (Token.Keyword, 'end')):
                    # skip comments and whitespace
                    while (self._whitespace(idx) or
                           self.tokens[idx][0] is Token.Comment):
                        whitespace = self._whitespace(idx)
                        if whitespace:
                            idx += whitespace
                        else:
                            idx += 1
                    # find methods
                    meth = MatMethod(self.module, self.tokens[idx:],
                                     self.__class__, attr_dict)
                    idx += meth.reset_tokens()  # reset method tokens and index
                    self.methods[meth.name] = meth  # update methods
                    idx += self._whitespace(idx)
                idx += 1
        self.rem_tks = idx  # index of last token
            

    def attributes(self, idx, attr_types):
        """
        Retrieve MATLAB class, property and method attributes.
        """
        attr_dict = {}
        idx += self._blanks(idx)  # skip blanks
        # class, property & method "attributes" start with parenthesis
        if self._tk_eq(idx, (Token.Punctuation, '(')):
            idx += 1
            # closing parenthesis terminates attributes
            while self._tk_ne(idx, (Token.Punctuation, ')')):
                idx += self._blanks(idx)  # skip blanks

                k, attr_name = self.tokens[idx]  # split token key, value
                if k is Token.Name and attr_name in attr_types:
                    attr_dict[attr_name] = True  # add attibute to dictionary
                    idx += 1
                else:
                    errmsg = 'Unexpected attribute: "%s".' % attr_name
                    raise Exception(errmsg)
                    # TODO: make matlab exception
                idx += self._blanks(idx)  # skip blanks
                # continue to next attribute separated by commas
                if self._tk_eq(idx, (Token.Punctuation, ',')):
                    idx += 1
                    continue
                # attribute values
                elif self._tk_eq(idx, (Token.Punctuation, '=')):
                    idx += 1
                    idx += self._blanks(idx)  # skip blanks
                    # logical value
                    k, attr_val = self.tokens[idx]  # split token key, value
                    if (k is Token.Name and attr_val in ['true', 'false']):
                        if attr_val == 'false':
                            attr_dict[attr_name] = False
                        idx += 1
                    elif k is Token.Name or self._tk_eq(idx, (Token.Text, '?')):
                        # concatenate enumeration or meta class
                        enum_or_meta = self.tokens[idx][1]
                        idx += 1
                        while (self._tk_ne(idx, (Token.Text, ' ')) and
                               self._tk_ne(idx, (Token.Text, '\t')) and
                               self._tk_ne(idx, (Token.Punctuation, ',')) and
                               self._tk_ne(idx, (Token.Punctuation, ')'))):
                            enum_or_meta += self.tokens[idx][1]
                            idx += 1
                        if self._tk_ne(idx, (Token.Punctuation, ')')):
                            idx += 1
                        attr_dict[attr_name] = enum_or_meta
                    # cell array of values
                    elif self._tk_eq(idx, (Token.Punctuation, '{')):
                        idx += 1
                        # closing curly braces terminate cell array
                        while self._tk_ne(idx, (Token.Punctuation, '}')):
                            idx += self._blanks(idx)  # skip blanks
                            # concatenate attr value string
                            attr_val = ''
                            # TODO: use _blanks or _indent instead
                            while (self._tk_ne(idx, (Token.Text, ' ')) and
                                   self._tk_ne(idx, (Token.Text, '\t')) and
                                   self._tk_ne(idx, (Token.Punctuation, ','))):
                                attr_val += self.tokens[idx][1]
                                idx += 1
                            idx += 1
                            if attr_val:
                                attr_dict[attr_name].append(attr_val)
                        idx += 1
                    idx += self._blanks(idx)  # skip blanks
                    # continue to next attribute separated by commas
                    if self._tk_eq(idx, (Token.Punctuation, ',')):
                        idx += 1
            idx += 1  # end of class attributes
        return attr_dict, idx

    @property
    def __module__(self):
        return self.module

    @property
    def __doc__(self):
        return unicode(self.docstring)

    @property
    def __bases__(self):
        bases_ = dict.fromkeys(self.bases)
        mod = sys.modules[self.module]
        pkg = mod.package.split('.')  # list of object paths in package
        # basedir is portion of path minus the package
        basedir = mod.path.rsplit(os.sep, len(pkg))  # split path
        basedir = basedir[0]  # MATLAB base src folder
        for root, dirs, files in os.walk(basedir):
            # don't visit vcs directories
            for vcs in ['.git', '.hg', '.svn', '.bzr']:
                if vcs in dirs:
                    dirs.remove(vcs)
            # only visit mfiles
            for f in tuple(files):
                if not f.endswith('.m'):
                    files.remove(f)
            # search folders
            for b in self.bases:
                for m in dirs:
                    if m not in sys.modules:
                        continue
                    b_ = sys.modules[m].getter(b)
                    if b_:
                        bases_[b] = b_
                        break
                if bases_[b]: continue
                if b + '.m' in files:
                    mfile = os.path.join(root, b) + '.m'
                    return MatObject.parse_mfile(mfile, b, root)
            # keep walking tree
        # no matching folders or mfiles
        return bases_

    def getter(self, name, *defargs):
        """
        :class:`MatClass` ``getter`` method to get attributes.
        """
        if name == '__name__':
            return self.__name__
        elif name == '__doc__':
            return self.__doc__
        elif name == '__module__':
            return self.__module__
        elif name == '__bases__':
            return self.__bases__
        elif name in self.properties:
            return MatProperty(name, self.__class__, self.properties[name])
        elif name in self.methods:
            return self.methods[name]
        elif name == '__dict__':
            objdict = dict([(pn, self.getter(pn)) for pn in
                            self.properties.iterkeys()])
            objdict.update(self.methods)
            return objdict
        else:
            super(MatClass, self).getter(name, *defargs)


class MatProperty(MatObject):
    def __init__(self, name, cls, attrs):
        super(MatProperty, self).__init__(name)
        self.cls = cls
        self.attrs = attrs['attrs']
        self.default = attrs['default']
        self.docstring = attrs['docstring']

    @property
    def __doc__(self):
        return unicode(self.docstring)


class MatMethod(MatFunction):
    def __init__(self, modname, tks, cls, attrs):
        # set name to None
        super(MatMethod, self).__init__(None, modname, tks)
        self.cls = cls
        self.attrs = attrs

    def reset_tokens(self):
        num_rem_tks = len(self.rem_tks)
        len_meth = len(self.tokens) - num_rem_tks
        self.tokens = self.tokens[:-num_rem_tks]
        self.rem_tks = None
        return len_meth

    @property
    def __module__(self):
        return self.module

    @property
    def __doc__(self):
        return unicode(self.docstring)


class MatScript(MatObject):
    def __init__(self, name, path, tks):
        super(MatScript, self).__init__(name)
        self.path = path
        self.tks = tks
        self.docstring = ''

    @property
    def __doc__(self):
        return unicode(self.docstring)


class MatException(MatObject):
    def __init__(self, name, path, tks):
        super(MatScript, self).__init__(name)
        self.path = path
        self.tks = tks
        self.docstring = ''

    @property
    def __doc__(self):
        return unicode(self.docstring)


class MatcodeError(Exception):
    def __str__(self):
        res = self.args[0]
        if len(self.args) > 1:
            res += ' (exception was: %r)' % self.args[1]
        return res


class MatModuleAnalyzer(object):
    # cache for analyzer objects -- caches both by module and file name
    cache = {}

    @classmethod
    def for_folder(cls, dirname, modname):
        if ('folder', dirname) in cls.cache:
            return cls.cache['folder', dirname]
        obj = cls(None, modname, dirname, True)
        cls.cache['folder', dirname] = obj
        return obj

    @classmethod
    def for_module(cls, modname):
        if ('module', modname) in cls.cache:
            entry = cls.cache['module', modname]
            if isinstance(entry, MatcodeError):
                raise entry
            return entry
        mod = sys.modules.get(modname)
        if mod:
            obj = cls.for_folder(mod.path, modname)
        else:
            err = MatcodeError('error importing %r' % modname)
            cls.cache['module', modname] = err
            raise err
        cls.cache['module', modname] = obj
        return obj

    def __init__(self, source, modname, srcname, decoded=False):
        # name of the module
        self.modname = modname
        # name of the source file
        self.srcname = srcname
        # file-like object yielding source lines
        self.source = source
        # cache the source code as well
        self.encoding = None
        self.code = None
        # will be filled by tokenize()
        self.tokens = None
        # will be filled by parse()
        self.parsetree = None
        # will be filled by find_attr_docs()
        self.attr_docs = None
        self.tagorder = None
        # will be filled by find_tags()
        self.tags = None

    def find_attr_docs(self, scope=''):
        """Find class and module-level attributes and their documentation."""
        if self.attr_docs is not None:
            return self.attr_docs
        attr_visitor_collected = {}
        attr_visitor_tagorder = {}
        tagnumber = 0
        mod = sys.modules[self.modname]
        # walk package tree
        for k, v in mod.safe_getmembers():
            attr_visitor_collected[mod.package, k] = v.docstring
            attr_visitor_tagorder[k] = tagnumber
            tagnumber += 1
            if isinstance(v, MatClass):
                for mk, mv in v.getter('__dict__').iteritems():
                    namespace = '.'.join([mod.package, k])
                    attr_visitor_collected[namespace, mk] = mv.docstring
                    attr_visitor_tagorder[mk] = tagnumber
                    tagnumber += 1
        self.attr_docs = attr_visitor_collected
        self.tagorder = attr_visitor_tagorder
        return attr_visitor_collected
