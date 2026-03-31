# Validates that required fields are present in state before an agent runs.
# Each agent calls the relevant check at the top so failures are caught early.


def check_fields_present(state, required_fields, agent_name):
    # Returns a list of error messages for any missing or empty required fields.
    # An empty list means the state is valid.
    errors = []

    for field in required_fields:
        value = state.get(field)

        if value is None:
            errors.append(f"{agent_name}: required field '{field}' is missing from state")
        elif isinstance(value, str) and value.strip() == "":
            errors.append(f"{agent_name}: required field '{field}' is empty")

    return errors


def check_file_path(path, agent_name):
    # Returns an error message if the file path is missing or blank.
    # Actual file existence is checked inside the agent using os.path.exists.
    if not path or str(path).strip() == "":
        return f"{agent_name}: file path is missing or empty"
    return None
