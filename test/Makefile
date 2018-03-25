
.phony: all clean

TESTS = $(wildcard test_*)
TESTS_DONE = $(subst test_,done_,$(TESTS))

PYAST_BUNDLE = ../pyast_bundle.py

export PYTHON=python3
SHEBANG=\#!/usr/bin/env python3


all: $(TESTS_DONE)

done_%: test_%
	@rm -rf $</.test*
	@mkdir $</.test
	$(PYAST_BUNDLE) -v -m $</module.py -o $</.test -z $</.test.pyz -X -S '$(SHEBANG)'
	
	
	# If there is a special script to test, run it
	if [ -x $</do_test ]; then $</do_test; fi
	 
	# Otherwise test the package gathered in a spearate directory
	if [ ! -x $</do_test ]; then $(PYTHON) $</.test/__main__.py; fi 
	
	# test the pyz package itself directly through shebang
	if [ ! -x $</do_test ]; then $(PYTHON) $</.test.pyz; fi
	touch $@
	
	
clean:
	rm -rf done_*
