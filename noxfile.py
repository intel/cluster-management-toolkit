import nox

@nox.session
def test_asynchronous_fetch(session):
	session.install("cryptography")
	session.install("natsort")
	session.install("ujson")
	session.install("urllib3")
	session.install("pyyaml")
	session.run("tests/async_fetch", external = True)

