"""E2E probe: SQL injection sample for the LLM reviewer (not caught by gitleaks)."""


def run_query(conn, user_input):
    query = "SELECT * FROM users WHERE name = '" + user_input + "'"
    return conn.execute(query)