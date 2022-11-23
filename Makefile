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
	 test -e ansible_helper.py || ln -s ../ansible_helper.py . ;\
	 test -e iktio.py || ln -s ../iktio.py . ;\
	 test -e iktio_yaml.py || ln -s ../iktio_yaml.py . ;\
	 test -e iktlib.py || ln -s ../iktlib.py . ;\
	 test -e iktpaths.py || ln -s ../iktpaths.py . ;\
	 test -e iktprint.py || ln -s ../iktprint.py . ;\
	 test -e ikttypes.py || ln -s ../ikttypes.py . ;\
	 test -e networkio.py || ln -s ../networkio.py .);\
	(cd tests/testpaths ;\
	 test -e 02-symlink || ln -s 05-not_executable.sh 02-symlink ;\
	 test -e 04-dir_symlink || ln -s 03-wrong_dir_permissions 04-dir_symlink ;\
	 test -L 07-dangling_symlink || ln -s this_destination_does_not_exist 07-dangling_symlink ;\
	 test -e 15-symlink_directory || ln -s 13-correct_directory 15-symlink_directory ;\
	 test -e ssh || ln -s /usr/bin/ssh ssh ;\
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
