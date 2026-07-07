def escape_literal(value: str) -> str:
    """Escapes a string for safe embedding as a SPARQL string literal."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
    )
