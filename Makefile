yaml_dirs = parsers themes views playbooks
python_executables = ikt iktadm ikt-install iktinv iku tests/validate_yaml

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

export_src:
	git archive --format zip --output ~/ikt-$(shell date -I).zip origin/main

validate_yaml:
	./tests/validate_yaml || /bin/true

validate_playbooks:
	ansible-lint playbooks/*.yaml || /bin/true
