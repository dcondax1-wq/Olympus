"""One rule for the browser suites in a container without the PYTHON playwright module (night-reds2 2026-11-23): the
browser part is SKIPPED with a printed reason, the non-browser parts still run and count; where the module exists (the
PC) everything runs exactly as before. Only a missing module skips: a browser that will not start stays a FAIL."""


def missing(part: str = "the browser part") -> bool:
    """True (and one SKIP line printed) when `import playwright.sync_api` fails with ImportError."""
    try:
        import playwright.sync_api  # noqa: F401
        return False
    except ImportError as e:
        print(f"  SKIP {part}: the Python playwright module is not installed here ({e}); pip install playwright runs it")
        return True
