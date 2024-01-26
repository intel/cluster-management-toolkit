import nox

@nox.session
def test_reexecutor(session):
	session.install("natsort")
	session.run("tests/async_fetch", external = True)

@nox.session
def test_logparser(session):
	session.install("natsort")
	session.install("ujson")
	session.install("pyyaml")
	session.run("tests/logtests", external = True)
