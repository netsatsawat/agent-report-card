"""Secret scrubbing.

Every ``${VAR}`` value expanded into an endpoint header is registered here,
and every piece of text the tool renders (report, scores sidecar, console
lines, error messages) passes through :func:`scrub` on its way out, which
replaces each expanded value with its ``${VAR}`` placeholder.

Limitation, stated in every report: replacement is exact-substring. An
endpoint that transforms a secret before echoing it back can still leak it.
"""

_SECRETS: list[tuple[str, str]] = []  # (value, var_name), longest value first


MIN_LENGTH = 6  # a 2-char "secret" would rewrite digits all over the report


def register(value: str, var_name: str) -> None:
    if not value or len(value) < MIN_LENGTH:
        return
    _SECRETS.append((value, var_name))
    _SECRETS.sort(key=lambda pair: len(pair[0]), reverse=True)


def scrub(text: str) -> str:
    for value, var_name in _SECRETS:
        text = text.replace(value, "${" + var_name + "}")
    return text


def reset() -> None:
    _SECRETS.clear()


def sprint(*parts: object) -> None:
    """print() that scrubs registered secrets first."""
    print(scrub(" ".join(str(p) for p in parts)))
