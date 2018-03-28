#!/usr/bin/env python3
from __future__ import print_function

"""

Copyright (c) 2018, Arnaud Mouiche
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
may be used to endorse or promote products derived from this software without
specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""

VERSION="1.0"

import argparse
import ast
import astor
import os
import logging
import re
import hashlib
import binascii
import tempfile
import shutil
import zipfile
import io
import stat
import json

class App:

    def __init__(self):
        self.modules = []
        self.ids = set()  # all the ID seen in the differents modules
        self.ob_ids_map = dict()  # how IDs are mappend to obfuscated IDs
        
        
        self.ob_docstring_exclude_re = []   # list of re complied object to test each doctring to know if the should not be obfuscated
        
        self.CONFIG = {
            "OBFUSCATE_MODE": "md5",
            "OBFUSCATE_SEED": b"",
            "OBFUSCATE_DOCSTRING_EXCLUDE": [],
            "OBFUSCATE_IDS_INCLUDE": [],
            }
            
    def top_module(self):
        """
        Returns the top module of the app
        """
        return self.modules[0] if self.modules else None
            
    def read_config(self,path):
        logging.debug("Read config from %s" % path)
        config_input = json.load(open(path))
        logging.debug(" => %r" % config_input)
        sef.CONFIG.update(config_input)
        
    def add_module(self, path, target_relative_path):
        """
        Add one module, and recursively, build all depending modules that can be found locally
        """
        path = os.path.normpath(path)
        logging.debug("App::add_module(%r)" % path)
        module = Module(path, app=self)
        module.target_relative_path = target_relative_path
        module.parse()
        
        if module.CONFIG:
            self.CONFIG.update(module.CONFIG)
        
        module.walk_test()
        
        self.modules.append(module)
        self.ids.update(module.collect_ids())
        
        this_module_dir = os.path.dirname(path)
        this_module_target_dir = os.path.dirname(target_relative_path)
        
        for import_path in module.import_paths:
            src_path = os.path.normpath(os.path.join(this_module_dir, import_path))
            if (src_path not in [m.path for m in self.modules]) and (os.path.exists(src_path)):
                self.add_module(src_path, os.path.join(this_module_target_dir, import_path))
    
        
    def build_ob_ids(self):
        """
        For every ID in self.ob_ids_map, build it corresponding obfuscated ID
        """
        IDS_INCLUDE_RULES = []
        for pattern in self.CONFIG["OBFUSCATE_IDS_INCLUDE"]:
            IDS_INCLUDE_RULES.append(re.compile(pattern))
            
            
        for id in self.ids:
            for r in IDS_INCLUDE_RULES:
                if r.match(id):
                    self.ob_ids_map[id] = None
                    break
        
        
        
        for id in list(self.ob_ids_map.keys()):
            print(id)
            m = hashlib.md5()
            m.update(self.CONFIG["OBFUSCATE_SEED"])
            m.update(id.encode())
            ob_id = "O" + binascii.b2a_hex(m.digest()).decode()[0:10]
            logging.debug("%s => %s" % (id, ob_id))
            self.ob_ids_map[id] = ob_id


    def generate_bundled_dir(self, dir_target):
        """
        Generate a bundle of top module + found imports in target_dir.
        Apply obfusaction.
        """
        
        for pattern in self.CONFIG["OBFUSCATE_DOCSTRING_EXCLUDE"]:
            self.ob_docstring_exclude_re.append(re.compile(pattern))
        
        
        
        logging.debug("App::generate_bundled_dir(dir_target=%r)" % dir_target)
        for module in self.modules:
            module.obfuscate_docstring()
            module.obfuscate_remove_libs_main()
            module.obfuscate_ids()
            module.generate(os.path.join( dir_target, module.target_relative_path))
        


class Module:

    shebang = None
    
    def __init__(self, path, app):
        self.path = path
        self.target_relative_path = None
        self.app = app
        
        self.import_paths = set()  # set of imported python files relative to the directory containing this module
        self.shebang = None # initial shebang if there is one

        self.CONFIG = None   # 
        
    def parse(self):
        logging.debug("Module::parse: self.path=%s" % self.path)
        with open(self.path) as F:
            
            # look for a shebang in first line
            line = F.readline()
            F.seek(0,0)
            
            if line[0:2] == "#!":
                self.shebang = line.strip()
                logging.debug("%s: shebang: %s" % (self.path, self.shebang))
            
            self.AST = ast.parse(F.read(), self.path)
            
        # for every node, keep track of its parent
        self.AST.o_level = 0
        for node in ast.walk(self.AST):
            for child in ast.iter_child_nodes(node):
                child.o_parent = node
                child.o_level = node.o_level + 1
                
        # look for "# pyast_bundle_config" top level docstring
        for child in ast.iter_child_nodes(self.AST):

            if isinstance(child, ast.Expr):
                if isinstance(child.value, ast.Str):
                    print("----")
                    print(child.value.s)
                    
                    print("----")
                    m = re.match(r"[ \t\r\n]*# *pyast_bundle_config *\n(.*)", child.value.s, re.MULTILINE | re.DOTALL)
                    if m:
                        print("-"*40)
                        print(m.group(1))
                        
                        self.CONFIG = json.loads(m.group(1))
                        child.value.s = ""
                


    
        # look for imported modules
        dirname = os.path.dirname(self.path)
        for node in ast.walk(self.AST):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # import 'alias.name' as 'alias.asname'
                    print(alias.name)
                    
                    rel_path = alias.name+".py"
                    src = os.path.join(dirname, rel_path)
                    if os.path.exists(src):
                        self.import_paths.add(rel_path)
                        continue
                    
                    rel_path = os.path.join(alias.name, "__init__.py")
                    src = os.path.join(dirname, rel_path)
                    if os.path.exists(src):
                        self.import_paths.add(rel_path)
                        continue
                        
            elif isinstance(node, ast.ImportFrom):
                # fields:
                #   module : name of the module
                #   names : list of alias objects
                #   level : number of .. to apply to find the module
                module_dir = dirname
                for i in range(node.level):
                    module_dir = os.path.join(module_dir, "..")
                    
                rel_path = node.module +".py"
                src = os.path.join(module_dir, rel_path)
                if os.path.exists(src):
                    self.import_paths.add(rel_path)
                    continue
                rel_path = os.path.join(node.module, "__init__.py")
                src = os.path.join(module_dir, rel_path)
                if os.path.exists(src):
                    self.import_paths.add(rel_path)
                    continue

        logging.debug("import_paths: %r" % self.import_paths)
                    
                    
        
    def obfuscate_docstring(self):
        """
        Replace docstring content to an emtpy string
        """
        for node in ast.walk(self.AST):
            if isinstance(node, ast.Expr):
                if isinstance(node.value, ast.Str):
                    # no operation string => docstring.
                    # replace the string content with an empty string
                    
                    remove = True
                    for r in self.app.ob_docstring_exclude_re:
                        if r.search(node.value.s):
                            remove = False
                            break
                    
                    if remove:
                        node.value.s = ""
    
    def obfuscate_remove_libs_main(self):
        """
        Remove 'if __name__ == "__main__":' sections of none top modules
        """
        
        if self == self.app.top_module():
            # this is the top module, don't remove it
            return
        
        
        class RewriteNode(ast.NodeTransformer):

            def visit_If(self_, node):
                print("visit", node)
                
                if not isinstance(node.test, ast.Compare): 
                    return node
                    
                compare = node.test
                if (not isinstance(compare.left, ast.Name)) or (compare.left.id != "__name__"):
                    return node
                    
                if (len(compare.ops) != 1) or (not isinstance(compare.ops[0], ast.Eq)):
                    return node
                    
                if (len(compare.comparators) != 1) or \
                    (not isinstance(compare.comparators[0], ast.Str)) or \
                    (compare.comparators[0].s != "__main__"):
                    return node    
                
                # this is a if __name__ == "__main__" test. 
                # replace its body by a 'pass'
                logging.debug("""%s: Remove 'if __name__ == "__main__":' section.""" % self.target_relative_path)
                node.body = [ast.Pass()] 
                return node
            
        
        self.AST = RewriteNode().visit(self.AST)
        

    def obfuscate_ids(self):
        """
        Replace ids with there obfuscated equivalent
        """
        for node in ast.walk(self.AST):
        
            if "id" in node._fields:
                name = node.id
                if isinstance(name, str) and (name in app.ob_ids_map):
                    node.id = app.ob_ids_map[name]
            if "name" in node._fields:
                name = node.name
                if isinstance(name, str) and (name in app.ob_ids_map):
                    node.name = app.ob_ids_map[name]
            if "attr" in node._fields:
                name = node.attr
                if isinstance(name, str) and (name in app.ob_ids_map):
                    node.attr = app.ob_ids_map[name]
                    
                    
    def collect_ids(self):
        result=set()
        for node in ast.walk(self.AST):
            if "id" in node._fields:
                name = node.id
                if isinstance(name, str):
                    result.add(name)
            if "name" in node._fields:
                name = node.name
                if isinstance(name, str):
                    result.add(name)
            if "attr" in node._fields:
                name = node.attr
                if isinstance(name, str):
                    result.add(name)
        return result
                    
                        
    def walk_sorted(self, node):
        yield node
        for child in ast.iter_child_nodes(node):
            for sub in self.walk_sorted(child):
                yield sub

    def walk_test(self):
        for node in self.walk_sorted(self.AST):
            indent = "    "*node.o_level
            print(indent, type(node).__name__)
            for f in node._fields:
                print(indent+"  ", f+":", getattr(node,f))
            
        
        
    def generate(self, output_path):
        astor.strip_tree(self.AST)
        
        logging.debug("%s: generate to %s" % (self.path, output_path))
        with open(output_path, "w") as F:
            F.write(astor.to_source(self.AST, indent_with=" "))




if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='''Python Bundle tool using AST for introspection and light obfuscation.
Version %s''' % VERSION,
        formatter_class=argparse.RawTextHelpFormatter
        )


    parser.add_argument("-m", "--module", metavar="FILE", required=True, help = 'initial module source file')
    parser.add_argument("-o", "--output-dir", metavar="DIR", help = '''Directory where files are grouped before zipping.
(Temporary directory if missing)''')
    parser.add_argument("-z", "--pyz", metavar="FILE", help = "PYZ package output file")
    parser.add_argument("-Z", "--compression", metavar="METHODE", choices = ["none", "zip", "bzip2", "lzma"], default = "zip", help = "Compression methode to use. (default none)")
    parser.add_argument("-s", "--shebang", action="store_true", help = "Place the main module shebang at the head of the pyz file")
    parser.add_argument("-S", "--shebang-replace", metavar="SHEBANG", help = "Place this specific shebang at the head of the pyz file")
    parser.add_argument("-X", "--executable", action="store_true", help = "chmod a+x")
    
    parser.add_argument("-c", "--config", metavar="FILE", help = "Config file")

    debug_grp = parser.add_argument_group("Debug options")
    debug_grp.add_argument("-k", "--keep", help="keep intermediate generated files (eg. temporary output dir)")
    debug_grp.add_argument("-v", "--verbose", action="store_true", help = 'more debug')
    
    args = parser.parse_args()
    
    
    if not args.output_dir and not args.pyz:
        print("--output-dir and --pyz options are both missing. At least one required.")
        exit(1)
        
    if args.verbose:
        logging.basicConfig(format="[%(message)s)]", level=logging.DEBUG)
                
    if not args.output_dir:
        # select a temporary directory for build result before zipping
        args.output_dir = tempfile.mkdtemp(suffix=".pyast_bundle")
        logging.debug("--output-dir not provided. Use '%s' instead" % args.output_dir)
        temp_outpur_dir = True
    else:
        temp_outpur_dir = False
        

    app = App()
    if args.config:
        app.read_config(args.config)
    
    
    app.add_module(args.module, "__main__.py")
    app.build_ob_ids()
    app.generate_bundled_dir(args.output_dir)
    
    if args.pyz:
        print("Create pyz bundle %s from %s" % (args.pyz, args.output_dir))
        
        zio = io.BytesIO()
        compression = {
            "none":zipfile.ZIP_STORED, 
            "zip": zipfile.ZIP_DEFLATED, 
            "bzip2": zipfile.ZIP_BZIP2, 
            "lzma": zipfile.ZIP_LZMA
            }[args.compression]
        with zipfile.ZipFile(zio, mode="w", compression=compression) as zf:
            for module in app.modules:
                src = os.path.join( args.output_dir, module.target_relative_path )
                print("%s => %s" % (src, module.target_relative_path))
                zf.write(src, module.target_relative_path)
                
        with open(args.pyz, "wb") as F:
            zio.seek(0)
            # put she shebang
            if args.shebang_replace:
                shebang = args.shebang_replace
            elif args.shebang or args.executable:
                shebang = app.top_module().shebang
            else:
                shebang = None

            if shebang:
                shebang = shebang.strip() + "\n"
                F.write(shebang.encode())
                
            # put the zip
            F.write(zio.read())
            
        if args.executable:
            # chmod a+x equivalent
            m = stat.S_IMODE(os.stat(args.pyz).st_mode)
            os.chmod(args.pyz, m | 0o111)
            print(args.pyz)
                
    
    # cleanup of intermediate / temporary files
    if temp_outpur_dir and not args.keep:
        shutil.rmtree(args.output_dir)

    
