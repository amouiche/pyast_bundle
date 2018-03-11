
.phony: all clean

TESTS = $(wildcard test_*)
TESTS_DONE = $(subst test_,done_,$(TESTS))

PYAST_BUNDLE = ../pyast_bundle.py

PYTHON=python3


all: $(TESTS_DONE)

done_%: test_%
	@rm -rf $</.test
	@mkdir $</.test
	$(PYAST_BUNDLE) -v -m $</module.py -o $</.test
	$(PYTHON) $</.test/__main__.py
	touch $@
	
