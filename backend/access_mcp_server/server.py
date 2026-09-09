"""
Custom MCP server for Microsoft Access databases (.accdb / .mdb).

Scans a configured folder for Access database files and exposes tools to
list them, inspect their schema, and run SQL against them via pyodbc and
the Microsoft Access ODBC Driver.

Usage:
    python server.py --folder "C:\\path\\to\\folder\\with\\accdb\\files"

Environment variable alternative:
    ACCESS_MCP_FOLDER=C:\\path\\to\\folder python server.py
"""
import argparse
import os
import re
import glob

import pyodbc
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("access-mcp")

# Populated at startup from --folder or ACCESS_MCP_FOLDER.
ACCESS_FOLDER = None

# Only these statement types are allowed to run - basic guardrail against
# obviously destructive administrative statements this server isn't meant
# to support (dropping the whole database, etc.). Actual DELETE/UPDATE/INSERT
# are allowed since this server is read-write by design; the chat-level
# system prompt is responsible for asking the user to confirm those first.
_DISALLOWED_PATTERN = re.compile(r"^\s*(DROP\s+DATABASE|SHUTDOWN)\b", re.IGNORECASE)


def _discover_databases() -> dict:
    """Return {name_without_extension: full_path} for every .accdb/.mdb file
    in ACCESS_FOLDER, re-scanned on every call so new files are picked up
    without restarting the server."""
    if not ACCESS_FOLDER or not os.path.isdir(ACCESS_FOLDER):
        return {}
    found = {}
    for ext in ("*.accdb", "*.mdb"):
        for path in glob.glob(os.path.join(ACCESS_FOLDER, ext)):
            name = os.path.splitext(os.path.basename(path))[0]
            found[name] = path
    return found


def _connect(db_name: str):
    databases = _discover_databases()
    if db_name not in databases:
        available = ", ".join(sorted(databases.keys())) or "(none found)"
        raise ValueError(f"Database '{db_name}' not found. Available: {available}")
    conn_str = (
        r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"Dbq={databases[db_name]};"
    )
    return pyodbc.connect(conn_str, autocommit=True)


@mcp.tool()
def list_databases() -> str:
    """List the Microsoft Access database files (.accdb/.mdb) available in the
    configured folder. Use the returned names (without file extension) as the
    db_name argument for other tools."""
    databases = _discover_databases()
    if not databases:
        return f"No .accdb/.mdb files found in {ACCESS_FOLDER}"
    lines = [f"- {name} ({path})" for name, path in sorted(databases.items())]
    return "Available Access databases:\n" + "\n".join(lines)


@mcp.tool()
def list_tables(db_name: str) -> str:
    """List all tables in the given Access database. db_name is the file name
    without extension, as returned by list_databases."""
    try:
        conn = _connect(db_name)
    except ValueError as e:
        return f"Error: {e}"
    try:
        cursor = conn.cursor()
        tables = [row.table_name for row in cursor.tables(tableType="TABLE")]
        if not tables:
            return f"No user tables found in '{db_name}'."
        return f"Tables in '{db_name}':\n" + "\n".join(f"- {t}" for t in tables)
    except Exception as e:
        return f"Error listing tables: {e}"
    finally:
        conn.close()


@mcp.tool()
def describe_table(db_name: str, table_name: str) -> str:
    """Describe the columns (name and data type) of a specific table in an
    Access database."""
    try:
        conn = _connect(db_name)
    except ValueError as e:
        return f"Error: {e}"
    try:
        cursor = conn.cursor()
        columns = cursor.columns(table=table_name)
        rows = [f"- {col.column_name} ({col.type_name})" for col in columns]
        if not rows:
            return f"Table '{table_name}' not found in '{db_name}', or it has no columns."
        return f"Columns in '{db_name}.{table_name}':\n" + "\n".join(rows)
    except Exception as e:
        return f"Error describing table: {e}"
    finally:
        conn.close()


@mcp.tool()
def execute_query(db_name: str, sql: str) -> str:
    """Execute a SQL statement (SELECT, INSERT, UPDATE, DELETE, or CREATE
    TABLE) against the given Access database using Access/Jet SQL syntax.
    For SELECT statements, returns the result rows as text. For other
    statements, returns the number of rows affected."""
    if _DISALLOWED_PATTERN.match(sql):
        return "Error: this statement type is not permitted on this server."

    try:
        conn = _connect(db_name)
    except ValueError as e:
        return f"Error: {e}"

    try:
        cursor = conn.cursor()
        cursor.execute(sql)

        if cursor.description is not None:
            # SELECT-style statement - format and return rows.
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()
            max_rows = 200
            truncated = len(rows) > max_rows
            rows = rows[:max_rows]

            lines = [" | ".join(columns)]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            result = "\n".join(lines)
            if truncated:
                result += f"\n\n[Truncated to first {max_rows} rows]"
            return result
        else:
            # INSERT/UPDATE/DELETE/CREATE - report rows affected.
            return f"Statement executed successfully. Rows affected: {cursor.rowcount}"
    except Exception as e:
        return f"Error executing SQL: {e}"
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", help="Folder containing .accdb/.mdb files")
    args = parser.parse_args()

    ACCESS_FOLDER = args.folder or os.getenv("ACCESS_MCP_FOLDER")
    if not ACCESS_FOLDER:
        raise SystemExit("Provide --folder or set ACCESS_MCP_FOLDER")

    mcp.run(transport="stdio")
