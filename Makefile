yaml_dirs = parsers themes views playbooks
python_executables = cmt cmtadm cmt-install cmtinv cmu tests/validate_yaml tests/check_theme_use tests/iotests
test_lib_symlinks = about.py ansible_helper.py ansithemeprint.py cmtio.py cmtio_yaml.py cmtlib.py cmtpaths.py cmttypes.py networkio.py

# Most of these are warnings/errors emitted due to coding style differences
FLAKE8_IGNORE := W191,E501,E305,E251,E302,E261,E101,E126,E128,E265,E712,E201,E202,E122,E241,E713,W504,E115,E222,E303,E231,E221,E116,E129,E127,E124
# This is the warning about unused assignments; flake8 doesn't recognise "_<variable>" to capture unused return values;
# pylint does, so we rely on that one to handle it instead.
FLAKE8_IGNORE := $(FLAKE8_IGNORE),F841,W605,E402
# These warnings are for invalid escape sequences and imports not at the top;
# they are triggered by the shell script-based workaround
FLAKE8_IGNORE := $(FLAKE8_IGNORE),W605,E402

ANSIBLE_LINT_SKIP := no-changed-when

checks: bandit yamllint validate_yaml validate_playbooks

clean: remove_test_symlinks

bandit:
	@cmd=bandit ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	$$cmd -c .bandit $(python_executables) *.py || /bin/true

pylint:
	@cmd=pylint ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	$$cmd --rcfile .pylint $(python_executables) *.py || /bin/true

flake8:
	@cmd=flake8 ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	$$cmd --ignore $(FLAKE8_IGNORE) $(python_executables) *.py || /bin/true

regexploit:
	@cmd=regexploit-py ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed; install with 'pip install regexploit' or 'pip install --proxy <proxy> regexploit'\n"; \
		exit 2; \
	fi; \
	printf -- "Checking executables\n"; \
	$$cmd $(python_executables); \
	printf -- "\nChecking libraries\n"; \
	$$cmd *.py

yamllint:
	@cmd=yamllint ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	for dir in $(yaml_dirs); do \
		$$cmd $$dir/*.yaml || /bin/true; \
	done; \
	$$cmd cmt.yaml || /bin/true

mypy-strict:
	@cmd=mypy ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	for file in $(python_executables) *.py; do \
		$$cmd --ignore-missing-imports --check-untyped-defs $$file || true; \
	done

mypy:
	@cmd=mypy ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "$$cmd not installed\n"; \
		exit 2; \
	fi; \
	for file in $(python_executables) *.py; do \
		$$cmd --ignore-missing-imports $$file || true; \
	done

export_src:
	git archive --format zip --output ~/cmt-$(shell date -I).zip origin/main

validate_yaml:
	./tests/validate_yaml || /bin/true

validate_playbooks:
	@cmd=ansible-lint ;\
	if ! command -v $$cmd > /dev/null 2> /dev/null; then \
		printf -- "ansible-lint not installed\n"; \
		exit 2; \
	fi; \
	ansible-lint -x $(ANSIBLE_LINT_SKIP) playbooks/*.yaml || /bin/true

parser_bundle:
	@printf -- "Building parser bundle\n" ;\
	rm -f parsers/BUNDLE.yaml; \
	for file in parsers/*.yaml; do \
		printf -- "---\n" >> parsers/BUNDLE.yaml; \
		cat $$file >> parsers/BUNDLE.yaml; \
	done

remove_test_symlinks:
	@(cd tests ;\
	  for file in $(test_lib_symlinks); do \
		rm -f $$file; \
	  done)

create_test_symlinks:
	@(cd tests ;\
	  for file in $(test_lib_symlinks); do \
		test -L $$file || ln -s ../$$file . ;\
	  done)

setup_tests: create_test_symlinks
	@(cd tests ;\
	  test -d testpaths || mkdir testpaths );\
	(cd tests/testpaths ;\
	 test -f 01-wrong_permissions || touch 01-wrong_permissions ;\
	 test -L 02-symlink || ln -s 05-not_executable.sh 02-symlink ;\
	 test -d 03-wrong_dir_permissions || mkdir 03-wrong_dir_permissions ;\
	 test -L 04-dir_symlink || ln -s 03-wrong_dir_permissions 04-dir_symlink ;\
	 test -e 05-not_executable.sh || echo "#! /bin/sh\nprint -- \"This file should be executable\n\"" > 05-not_executable.sh ;\
	 test -e 06-executable.sh || echo "#! /bin/sh\nprint -- \"This file should NOT be executable\n\"" > 06-executable.sh ;\
	 test -L 07-dangling_symlink || ln -s this_destination_does_not_exist 07-dangling_symlink ;\
	 test -f 08-not_utf8.txt || /usr/bin/printf -- "\xc3\x28" > 08-not_utf8.txt ;\
	 test -f 09-this_is_not_valid.yaml || printf -- ": this is not valid yaml\n" > 09-this_is_not_valid.yaml ;\
	 test -f 10-valid_yaml_for_load_all.yaml || printf -- "---\nvalid_yaml:\n  this_should_load_with_load_all: true\n---\nalso_valid_yaml:\n  everything_should_be_fine: true\n" > 10-valid_yaml_for_load_all.yaml ;\
	 test -f 11-valid_yaml_but_single.yaml || printf -- "valid_yaml:\n  but_only_when_using_load: true\n  this_wont_work_with_load_all: true\n" > 11-valid_yaml_but_single.yaml ;\
	 test -f 12-valid_yaml_followed_by_invalid_yaml.yaml || printf -- "---\nvalid_yaml:\n  this_should_load_with_load_all: true\n---\ninvalid_yaml:\n  : this is not valid yaml\n" > 12-valid_yaml_followed_by_invalid_yaml.yaml ;\
	 test -d 13-correct_directory || mkdir 13-correct_directory ;\
	 test -f 03-wrong_dir_permissions/14-correct_file_in_wrong_permission_directory || touch 03-wrong_dir_permissions/14-correct_file_in_wrong_permission_directory ;\
	 test -L 15-symlink_directory || ln -s 13-correct_directory 15-symlink_directory ;\
	 test -f 13-correct_directory/16-correct_file_in_correct_permission_directory || touch 13-correct_directory/16-correct_file_in_correct_permission_directory ;\
	 test -e ssh || ln -s /usr/bin/ssh ssh ;\
	 test -f testfile.txt || printf -- "Random text\n" > testfile.txt ;\
	 test -f test_symlink || ln -s $$(pwd)/05-not_executable.sh test_symlink ;\
	 chmod a+x 06-executable.sh ;\
	 chmod o+w 03-wrong_dir_permissions ;\
	 chmod o+w 01-wrong_permissions )

iotests: setup_tests
	@(cd tests && ./iotests)

check_theme_use: setup_tests
	@for theme in themes/*.yaml; do \
		printf -- "\nChecking against theme file $$theme:\n" ;\
		printf -- "---\n" ;\
		./tests/check_theme_use $$theme $(python_executables) *.py ;\
	done
