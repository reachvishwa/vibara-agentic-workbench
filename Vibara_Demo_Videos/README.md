# Demo Videos

Short screen recordings demonstrating the agentic capabilities of the app — an NVIDIA NIM-powered chat application extended with MCP (Model Context Protocol) tool integrations and native tools, allowing the connected LLM to autonomously read, write, and reason over local files, databases, and live applications.

> **Note:** GitHub does not preview `.mp4` files inline for files of this size. Click **"Download raw file"** (top-right of the file view) to watch each video.

## Videos

| File | Description |
|---|---|
| `FileSystem_MCP_PDF_CONVERSION_TO_MD.mp4` | The agent autonomously installs a Python PDF-to-Markdown conversion tool, locates the target PDF, runs the conversion, and saves the output — all from a single natural-language request, using the Filesystem MCP and Bash tools together. |
| `FileSystem_MCP_FILE_MANIPULATION.mp4` | Demonstrates file operations via the Filesystem MCP server — listing, reading, creating, and editing files in an authorised project directory, with confirmation required before any destructive action. |
| `Web_Search_Tool_Calling_Check_Next_Week_Weather_Forecast.mp4` | Shows the agent recognising a question needs current, real-world information and autonomously calling the web search tool to retrieve and summarise it. |
| `DuckDB_MCP_Database_Operations.mp4` | Natural-language SQL: the agent connects to a DuckDB database, inspects the schema, and answers questions by generating and executing SQL — with the generated SQL shown for transparency. |
| `PowerBI_MCP_SEMANTIC_MODEL_INTERACTION.mp4` | The agent connects live to a Power BI Desktop session via the Power BI Modeling MCP server, browses the semantic model (tables, measures), and writes DAX — reasoning over a real, open Power BI report. |

## What this demonstrates

Each video shows the same underlying pattern: a user request in plain English, the model deciding which tool(s) it needs, executing them, observing the results, and continuing to reason until the task is complete — the core agentic loop, applied across five very different data sources (filesystem, shell, web, a local analytical database, and a live BI application).
