yaml_dirs = parsers themes views playbooks
python_executables = ikt iktadm ikt-install iktinv iku tests/validate_yaml tests/check_theme_use tests/iotests

checks: bandit yamllint validate_yaml validate_playbooks

bandit:
	bandit -c .bandit $(python_executables) *.py || /bin/true

pylint:
	@pylint --rcfile .pylint $(python_executables) *.py || /bin/true

yamllint:
	@for dir in $(yaml_dirs); do \
		yamllint $$dir/*.yaml || /bin/true; \
	done; \
	yamllint ikt.yaml || /bin/true

mypy-strict:
	@for file in $(python_executables) *.py; do \
		mypy --ignore-missing-imports --check-untyped-defs $$file || true; \
	done

mypy:
	@for file in $(python_executables) *.py; do \
		mypy --ignore-missing-imports $$file || true; \
	done

export_src:
	git archive --format zip --output ~/ikt-$(shell date -I).zip origin/main

validate_yaml:
	./tests/validate_yaml || /bin/true

validate_playbooks:
	ansible-lint playbooks/*.yaml || /bin/true

parser_bundle:
	@printf -- "Building parser bundle\n" ;\
	rm -f parsers/BUNDLE.yaml; \
	for file in parsers/*.yaml; do \
		printf -- "---\n" >> parsers/BUNDLE.yaml; \
		cat $$file >> parsers/BUNDLE.yaml; \
	done

setup_tests:
	@(cd tests ;\
	 test -L ansible_helper.py || ln -s ../ansible_helper.py . ;\
	 test -L iktio.py || ln -s ../iktio.py . ;\
	 test -L iktio_yaml.py || ln -s ../iktio_yaml.py . ;\
	 test -L iktlib.py || ln -s ../iktlib.py . ;\
	 test -L iktpaths.py || ln -s ../iktpaths.py . ;\
	 test -L iktprint.py || ln -s ../iktprint.py . ;\
	 test -L ikttypes.py || ln -s ../ikttypes.py . ;\
	 test -L networkio.py || ln -s ../networkio.py . ;\
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
	 test -f 09-this_is_not_valid.yaml || printf -- ": this isn't valid yaml\n" > 09-this_is_not_valid.yaml ;\
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
