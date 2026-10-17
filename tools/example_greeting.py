def generate_greeting(name: str) -> dict[str, str]:
    """Generate a sample greeting for registered script tools."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("A name is required to generate a greeting.")

    return {"message": f"Hello, {clean_name}! The Python script ran successfully."}
