# Vibara Agentic Workbench

**One agent. Any model. Any tool. Real enterprise data.**

Vibara is a personal, NIM-powered agentic development environment inspired by modern coding agents. It separates the agent/tool environment from the underlying model provider and exposes a unified tool layer to the model.

## Highlights

- NVIDIA NIM as the model/inference layer
- Model-agnostic chat and agent workflow
- MCP and native tools presented through one unified tool layer
- Microsoft Access database discovery, schema inspection and SQL execution
- Filesystem MCP
- DuckDB MCP for CSV/Parquet data
- Power BI Modeling MCP integration
- Sandboxed Bash execution with an allow-list
- Tavily web search
- PDF, Excel and CSV extraction
- Visible tool calls in the UI
- Confirmation before destructive operations

## Project structure

```text
vibara-agentic-workbench/
├── backend/
│   ├── access_mcp_server/
│   │   └── server.py
│   ├── .env.example
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── package.json
│   └── ...
├── .gitignore
├── Launch_Vibara.bat
└── README.md
```

## Setup

### 1. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Add your own NVIDIA API key and any optional tool configuration to `backend/.env`.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

### 3. Run the backend

```powershell
cd backend
venv\Scripts\python.exe main.py
```

Or, on Windows, use `Launch_Vibara.bat` after completing the setup above.

## Local data and integrations

Vibara is designed to connect to user-authorized local data and tools. Local databases, datasets, virtual environments, API keys, and provider-specific executables are intentionally excluded from this repository.

For Microsoft Access, configure `ACCESS_MCP_FOLDER` to a directory containing your own `.accdb` or `.mdb` files. The custom Access MCP server is included in `backend/access_mcp_server/server.py`.

For Power BI Modeling MCP, configure `POWERBI_MCP_PATH` to the executable installed in your own environment.

## Security

Do not commit API keys, `.env` files, local databases, datasets, virtual environments, or private corporate data. The repository's `.gitignore` excludes these local artifacts.

## Contest note

Vibara was independently conceived, architected and developed as a personal project. AI-assisted software engineering was used to accelerate implementation, debugging and iteration.
