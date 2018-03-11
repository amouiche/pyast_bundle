#!/usr/bin/env python3

import argparse
import ast
import astor
import os
import logging
import re
import hashlib
import binascii



class App:

    def __init__(self):
        self.modules = []
        self.ids = set()  # all the ID seen in the differents modules
        self.ob_ids_map = dict()  # how IDs are mappend to obfuscated IDs
        
        
        self.ob_ids_map["FLASH_ADDR"] = None
        
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
        exec(open(path).read(), self.CONFIG)
        logging.debug(" => %r" % self.CONFIG)
        
    def add_module(self, path, target_relative_path):
        """
        Add one module, and recursively, build all depending modules that can be found locally
        """
        path = os.path.normpath(path)
        logging.debug("App::add_module(%r)" % path)
        module = Module(path, app=self)
        module.target_relative_path = target_relative_path
        module.parse()
        
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
        logging.debug("App::generate_bundled_dir(dir_target=%r)" % dir_target)
        for module in self.modules:
            module.obfuscate_docstring()
            module.obfuscate_ids()
            module.generate(os.path.join( dir_target, module.target_relative_path))
        


class Module:

    shebang = None
    
    def __init__(self, path, app):
        self.path = path
        self.target_relative_path = None
        self.app = app
        
        self.docstring_exclude = []
        
        self.import_paths = set()  # set of imported python files relative to the directory containing this module


        
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
                        
            if isinstance(node, ast.ImportFrom):
                # todo
                pass

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
                    for r in self.docstring_exclude:
                        if r.search(node.value.s):
                            remove = False
                            break
                    
                    if remove:
                        node.value.s = ""


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
        description='Python Bundle tool using AST for introspection',
        formatter_class=argparse.RawTextHelpFormatter
        )


    parser.add_argument("-v", "--verbose", action="store_true", help = 'more debug')
    parser.add_argument("-o", "--output-dir", metavar="DIR", required=True, help = 'directory where new files are created')
    parser.add_argument("-m", "--module", metavar="FILE", required=True, help = 'initial source file')
    
    parser.add_argument("-c", "--config", metavar="FILE", help = "Config file")
    parser.add_argument("-t", action="store_true", help = "Config file")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(format="[%(message)s)]", level=logging.DEBUG)


    app = App()
    if args.config:
        app.read_config(args.config)
    
    
    app.add_module(args.module, "__main__.py")
    app.build_ob_ids()
    app.generate_bundled_dir(args.output_dir)
    


    