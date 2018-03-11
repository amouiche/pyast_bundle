
.phony: all clean

TESTS = $(wildcard test_*)
TESTS_DONE = $(subst test_,done_,$(TESTS))

PYAST_BUNDLE = ../pyast_bundle.py

PYTHON=python3
SHEBANG=\#!/usr/bin/env python3


all: $(TESTS_DONE)

done_%: test_%
	@rm -rf $</.test*
	@mkdir $</.test
	$(PYAST_BUNDLE) -v -m $</module.py -o $</.test -z $</.test.pyz -X -S '$(SHEBANG)'
	
	# test the package gathered in a spearate directory
	$(PYTHON) $</.test/__main__.py
	
	# test the pyz package itself directly through shebang
	$(PYTHON) $</.test.pyz
	touch $@
	
	
clean:
	rm -rf done_*
