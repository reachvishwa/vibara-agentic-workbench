import os
import sys
from dotenv import load_dotenv
load_dotenv()

import logging
import json
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from pydantic import BaseModel, Field
import aiohttp
import asyncio
import base64
import io
import csv
from pypdf import PdfReader
import openpyxl
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat.db")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_API_BASE = os.getenv("NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Power BI Modeling MCP server (local, stdio-based)
POWERBI_MCP_PATH = os.getenv("POWERBI_MCP_PATH", "")

# Filesystem MCP server (official reference server, via npx, stdio-based).
# Comma-separated list of directories the AI is allowed to access.
FILESYSTEM_MCP_ALLOWED_DIRS = os.getenv("FILESYSTEM_MCP_ALLOWED_DIRS", os.getcwd()).split(",")

# DuckDB MCP server (motherduckdb/mcp-server-motherduck, via uvx, stdio-based).
# Defaults to an in-memory database so CSV/Parquet files can be queried directly
# via read_csv()/read_parquet() without needing a persistent .duckdb file. Set
# DUCKDB_MCP_DB_PATH to a real .duckdb file path for a persistent database instead.
DUCKDB_MCP_DB_PATH = os.getenv("DUCKDB_MCP_DB_PATH", ":memory:")

# Custom MS Access MCP server (this project's own server.py, via pyodbc).
# Folder is scanned for .accdb/.mdb files each time list_databases is called,
# so new files are picked up without restarting the server.
ACCESS_MCP_SERVER_PATH = os.getenv(
    "ACCESS_MCP_SERVER_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "access_mcp_server", "server.py")
)
ACCESS_MCP_FOLDER = os.getenv(
    "ACCESS_MCP_FOLDER",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
)

# Native bash tool: sandboxed to one working directory, with a strict
# allow-list of permitted command names. The first token of any command is
# checked against this list; anything not on it is rejected before execution.
BASH_TOOL_WORKDIR = os.getenv("BASH_TOOL_WORKDIR", FILESYSTEM_MCP_ALLOWED_DIRS[0])
BASH_TOOL_ALLOWED_COMMANDS = set(os.getenv(
    "BASH_TOOL_ALLOWED_COMMANDS",
    "git,python,pip,node,npm,npx,dir,type,findstr,where,echo,cd"
).split(","))
BASH_TOOL_TIMEOUT_SECONDS = int(os.getenv("BASH_TOOL_TIMEOUT_SECONDS", "30"))

# Web search tool (Tavily API).
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE MODELS
# ============================================================================

Base = declarative_base()

class ConversationDB(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MessageDB(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SettingsDB(Base):
    __tablename__ = "settings"
    
    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(Text)
    default_model = Column(String(255), default="nvidia/nemotron-3-ultra-550b-a55b")
    temperature = Column(String(10), default="0.3")
    max_tokens = Column(Integer, default=32000)
    system_prompt = Column(Text, default="You are a helpful AI assistant.")
    theme = Column(String(20), default="dark")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# PYDANTIC MODELS (API SCHEMAS)
# ============================================================================

class ConversationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class ConversationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class ConversationResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    conversation_id: int
    role: str
    content: str

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]

class SettingsResponse(BaseModel):
    api_key: Optional[str] = None
    default_model: str
    temperature: str
    max_tokens: int
    system_prompt: str
    theme: str

    class Config:
        from_attributes = True

class SettingsUpdate(BaseModel):
    api_key: Optional[str] = None
    default_model: Optional[str] = None
    temperature: Optional[str] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    theme: Optional[str] = None

class ImageAttachment(BaseModel):
    # Base64-encoded image data (no data: prefix) and its mime type.
    data: str
    media_type: str = "image/png"

class DocumentAttachment(BaseModel):
    # Base64-encoded file data (no data: prefix), original filename, and mime type.
    data: str
    filename: str
    media_type: str = "application/octet-stream"

class ChatMessage(BaseModel):
    conversation_id: int
    message: str
    model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    temperature: float = 0.3
    max_tokens: int = 32000
    image: Optional[ImageAttachment] = None
    document: Optional[DocumentAttachment] = None
    use_mcp: bool = False

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    description: Optional[str] = None
    multimodal: bool = False

# ============================================================================
# NVIDIA API CLIENT
# ============================================================================

def extract_document_text(doc: DocumentAttachment, max_chars: int = 2800000) -> str:
    """Extract plain text from an uploaded PDF, XLSX, CSV, or TXT file so it can
    be included in the prompt for any model, regardless of vision support."""
    try:
        raw = base64.b64decode(doc.data)
    except Exception as e:
        return f"[Could not decode uploaded file '{doc.filename}': {e}]"

    name_lower = doc.filename.lower()
    text = ""

    try:
        if name_lower.endswith(".pdf") or "pdf" in doc.media_type:
            reader = PdfReader(io.BytesIO(raw))
            pages_text = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
            text = "\n\n".join(pages_text)

        elif name_lower.endswith((".xlsx", ".xlsm")) or "sheet" in doc.media_type:
            wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
            sheets_text = []
            for sheet in wb.worksheets:
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    rows.append(", ".join("" if v is None else str(v) for v in row))
                sheets_text.append(f"[Sheet: {sheet.title}]\n" + "\n".join(rows))
            text = "\n\n".join(sheets_text)

        elif name_lower.endswith(".csv") or "csv" in doc.media_type:
            decoded = raw.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(decoded))
            text = "\n".join(", ".join(row) for row in reader)

        else:
            # Treat anything else (.txt, .md, unknown) as plain text
            text = raw.decode("utf-8", errors="replace")

    except Exception as e:
        return f"[Failed to parse uploaded file '{doc.filename}': {e}]"

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[Truncated - file was longer than {max_chars} characters]"

    return f"[Content of uploaded file '{doc.filename}']:\n{text}"


class NativeTool:
    """A single locally-implemented tool: name, description, JSON schema for its
    arguments, and an async execution function taking (**arguments) -> str."""

    def __init__(self, name: str, description: str, parameters: dict, handler):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler


class NativeToolManager:
    """Exposes the same interface as MCPManager (get_openai_tools, call_tool,
    is_connected) so native, in-process tools can be merged into the same
    tool-calling loop as MCP-backed tools with no changes to that loop.

    Tools are registered dynamically via register_tool(), so adding a new
    native tool never requires touching the agent loop itself."""

    def __init__(self, name: str):
        self.name = name
        self._tools: dict[str, NativeTool] = {}
        self._enabled = True  # toggled via connect()/disconnect() for UI parity

    def register_tool(self, tool: NativeTool):
        self._tools[tool.name] = tool
        logger.info(f"Registered native tool '{tool.name}' in manager '{self.name}'")

    async def connect(self):
        self._enabled = True

    async def disconnect(self):
        self._enabled = False

    def is_connected(self) -> bool:
        return self._enabled and len(self._tools) > 0

    def get_openai_tools(self) -> list[dict]:
        if not self._enabled:
            return []
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            }
            for tool in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"[Native tool '{name}' is not registered]"
        try:
            return await tool.handler(**arguments)
        except Exception as e:
            logger.error(f"Native tool '{name}' failed: {e}")
            return f"[Tool '{name}' failed: {e}]"


def _is_path_within_workdir(path: str, workdir: str) -> bool:
    """Guard against directory-escape attempts (absolute paths outside the
    sandbox, or .. traversal) when a command references a specific path."""
    try:
        resolved = os.path.abspath(os.path.join(workdir, path))
        return os.path.commonpath([resolved, os.path.abspath(workdir)]) == os.path.abspath(workdir)
    except (ValueError, OSError):
        return False


async def _bash_tool_handler(command: str) -> str:
    """Execute a shell command, restricted to an allow-listed set of command
    names and sandboxed to a single working directory. This is the async
    handler registered as the 'bash' native tool."""
    stripped = command.strip()
    if not stripped:
        return "[Error: empty command]"

    first_token = stripped.split()[0].lower()
    # Strip a possible .exe suffix so "git.exe" and "git" are treated the same.
    first_token = first_token[:-4] if first_token.endswith(".exe") else first_token

    if first_token not in BASH_TOOL_ALLOWED_COMMANDS:
        logger.warning(f"bash tool blocked disallowed command: {stripped!r}")
        return (
            f"[Blocked: '{first_token}' is not in the allowed command list. "
            f"Allowed commands: {', '.join(sorted(BASH_TOOL_ALLOWED_COMMANDS))}]"
        )

    # Basic directory-escape guard: block obvious attempts to leave the sandbox
    # via absolute paths or '..' segments referencing outside BASH_TOOL_WORKDIR.
    if ".." in stripped or (":\\" in stripped and BASH_TOOL_WORKDIR.lower() not in stripped.lower()):
        logger.warning(f"bash tool blocked possible sandbox escape: {stripped!r}")
        return "[Blocked: command appears to reference a path outside the allowed working directory]"

    logger.info(f"bash tool executing: {stripped!r} (cwd={BASH_TOOL_WORKDIR})")

    try:
        proc = await asyncio.create_subprocess_shell(
            stripped,
            cwd=BASH_TOOL_WORKDIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=BASH_TOOL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return f"[Command timed out after {BASH_TOOL_TIMEOUT_SECONDS}s and was killed]"

        stdout_text = stdout.decode(errors="replace")[:5000]
        stderr_text = stderr.decode(errors="replace")[:2000]
        result = f"Exit code: {proc.returncode}\n\nSTDOUT:\n{stdout_text}"
        if stderr_text.strip():
            result += f"\n\nSTDERR:\n{stderr_text}"
        return result
    except Exception as e:
        logger.error(f"bash tool execution error: {e}")
        return f"[Execution error: {e}]"


async def _web_search_handler(query: str, max_results: int = 5) -> str:
    """Search the web via the Tavily API and return structured results as text."""
    if not TAVILY_API_KEY:
        return "[web_search is not configured: TAVILY_API_KEY is not set on the backend]"

    max_results = max(1, min(int(max_results), 10))

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic"
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Tavily search error: {response.status} - {error_text}")
                    return f"[web_search failed: {response.status} - {error_text}]"
                data = await response.json()
    except Exception as e:
        logger.error(f"web_search error: {e}")
        return f"[web_search failed: {e}]"

    results = data.get("results", [])
    if not results:
        return f"No results found for query: {query}"

    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "(no title)")
        url = r.get("url", "")
        snippet = (r.get("content", "") or "")[:400]
        lines.append(f"{i}. {title}\n   URL: {url}\n   {snippet}\n")

    return "\n".join(lines)


# Native (non-MCP) tool manager. bash is the first registered tool; future
# native tools (glob, grep, read_file, git_*, curl, web_search, ...) register
# into this same manager without touching the agent loop.
native_tools = NativeToolManager(name="native")
native_tools.register_tool(NativeTool(
    name="bash",
    description=(
        "Execute a shell command in a sandboxed working directory. Only a "
        "fixed allow-list of command names is permitted (e.g. git, python, "
        "pip, node, npm, dir, type, findstr, echo); anything else is blocked. "
        "Use this for tasks like running scripts, checking git status, "
        "installing packages, or inspecting files via allowed commands."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute, e.g. 'git status' or 'python script.py'"
            }
        },
        "required": ["command"]
    },
    handler=_bash_tool_handler
))
native_tools.register_tool(NativeTool(
    name="web_search",
    description=(
        "Search the internet for current information. Use this when the "
        "question may be about recent events, information that could have "
        "changed since training, current documentation, or anything that "
        "needs external verification. Returns a list of results with "
        "titles, URLs, and snippets."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 10)"
            }
        },
        "required": ["query"]
    },
    handler=_web_search_handler
))


class MCPManager:
    """Manages a connection to a local stdio-based MCP server (e.g. the Power BI
    Modeling MCP server) and exposes its tools in OpenAI-compatible format."""

    def __init__(self, command: str, args: list[str] = None, env: dict = None):
        self.command = command
        self.args = args or ["--start"]
        self.env = env
        self._exit_stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None
        self._tools_cache: list = []
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self):
        """Launch the MCP server subprocess and initialize the session, if not already connected."""
        async with self._lock:
            if self._connected:
                return
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=self.env
            )
            self._exit_stack = AsyncExitStack()
            read, write = await self._exit_stack.enter_async_context(stdio_client(server_params))
            self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            tools_result = await self.session.list_tools()
            self._tools_cache = tools_result.tools
            self._connected = True
            logger.info(f"MCP server connected: {len(self._tools_cache)} tools discovered")

    async def disconnect(self):
        async with self._lock:
            if self._exit_stack:
                await self._exit_stack.aclose()
            self._exit_stack = None
            self.session = None
            self._connected = False
            self._tools_cache = []

    def is_connected(self) -> bool:
        return self._connected

    def get_openai_tools(self) -> list[dict]:
        """Convert cached MCP tool definitions into OpenAI-style function tool schemas."""
        openai_tools = []
        for tool in self._tools_cache:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema or {"type": "object", "properties": {}}
                }
            })
        return openai_tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call an MCP tool by name and return a plain-text result for feeding back to the model."""
        if not self._connected or not self.session:
            return "[MCP server is not connected]"
        try:
            result = await self.session.call_tool(name, arguments=arguments)
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            text = "\n".join(parts)
            if result.isError:
                return f"[Tool '{name}' returned an error]: {text}"
            return text
        except Exception as e:
            logger.error(f"MCP tool call '{name}' failed: {e}")
            return f"[Tool '{name}' failed: {e}]"


# Single shared instance for the Power BI Modeling MCP server.
powerbi_mcp = MCPManager(command=POWERBI_MCP_PATH, args=["--start"])

# Official filesystem MCP server, launched via npx. On Windows, npx must be run
# through cmd /c since it's a .cmd shim, not a directly executable binary.
filesystem_mcp = MCPManager(
    command="cmd",
    args=["/c", "npx", "-y", "@modelcontextprotocol/server-filesystem"] + FILESYSTEM_MCP_ALLOWED_DIRS
)

# DuckDB MCP server (motherduckdb/mcp-server-motherduck), launched via uvx.
# Read-write so it can create tables and persist query results within a session.
duckdb_mcp = MCPManager(
    command="uvx",
    args=["mcp-server-motherduck", "--db-path", DUCKDB_MCP_DB_PATH, "--read-write"]
)

# Custom MS Access MCP server (this project's own server.py). Uses sys.executable
# so it launches with the same Python interpreter/venv as this backend, where
# pyodbc and mcp are installed.
access_mcp = MCPManager(
    command=sys.executable,
    args=[ACCESS_MCP_SERVER_PATH, "--folder", ACCESS_MCP_FOLDER]
)


class NVIDIAClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = NVIDIA_API_BASE
        self.models = {
            "nvidia/nemotron-3-ultra-550b-a55b": {
                "name": "Nemotron 3 Ultra 550B",
                "provider": "NVIDIA",
                "description": "A high-capacity reasoning model that is currently reachable through the NVIDIA chat completions endpoint.",
                "max_doc_chars": 2800000,
            },
            "deepseek-ai/deepseek-v4-pro": {
                "name": "DeepSeek V4 Pro",
                "provider": "DeepSeek",
                "description": "A verified NVIDIA-compatible model that responds successfully through the OpenAI-compatible endpoint.",
                "max_doc_chars": 2800000,
            },
            "qwen/qwen3.5-397b-a17b": {
                "name": "Qwen 3.5 397B A17B",
                "provider": "Alibaba",
                "description": "A large mixture-of-experts model with confirmed vision support for image understanding.",
                "multimodal": True,
                "max_doc_chars": 700000,
            },
            "z-ai/glm-5.2": {
                "name": "GLM 5.2",
                "provider": "Z.ai",
                "description": "A general-purpose chat and reasoning model from a different provider for redundancy.",
                # NVIDIA's hosted GLM-5.2 deployment has been reported (NVIDIA dev forums,
                # July 2026) to return 500 errors above ~202K tokens despite the model's
                # advertised 1M window, so we cap well under that reported ceiling.
                "max_doc_chars": 650000,
            },
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning": {
                "name": "Nemotron 3 Nano Omni 30B (Reasoning)",
                "provider": "NVIDIA",
                "description": "A multimodal reasoning model with adjustable reasoning budget, useful for image understanding plus step-by-step reasoning.",
                "multimodal": True,
                "max_doc_chars": 700000,
                "extra_params": {"reasoning_budget": 16384},
            },
            "nvidia/nemotron-3-nano-30b-a3b": {
                "name": "Nemotron 3 Nano 30B",
                "provider": "NVIDIA",
                "description": "A smaller, faster reasoning model with adjustable reasoning budget, useful as a lightweight text-only option.",
                "max_doc_chars": 700000,
                "extra_params": {"reasoning_budget": 16384},
            },
            "nvidia/nvidia-nemotron-nano-9b-v2": {
                "name": "Nemotron Nano 9B v2",
                "provider": "NVIDIA",
                "description": "A very small, very fast reasoning model with an adjustable thinking-token budget, best for quick everyday questions.",
                "max_doc_chars": 400000,
                "extra_params": {"min_thinking_tokens": 1024, "max_thinking_tokens": 2048},
            },
            "nvidia/nemotron-mini-4b-instruct": {
                "name": "Nemotron Mini 4B Instruct",
                "provider": "NVIDIA",
                "description": "A very small, very fast instruct model, useful for quick simple tasks.",
            },
            "minimaxai/minimax-m3": {
                "name": "MiniMax M3",
                "provider": "MiniMax AI",
                "description": "A general-purpose chat model from MiniMax AI.",
            },
            "mistralai/mistral-medium-3.5-128b": {
                "name": "Mistral Medium 3.5 128B",
                "provider": "Mistral AI",
                "description": "A mid-size Mistral reasoning model with adjustable reasoning effort.",
                "extra_params": {"reasoning_effort": "high"},
            },
            "deepseek-ai/deepseek-v4-flash": {
                "name": "DeepSeek V4 Flash",
                "provider": "DeepSeek",
                "description": "A faster, lighter DeepSeek V4 variant with adjustable thinking/reasoning effort.",
                "extra_params": {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
            },
            "nvidia/nemotron-3-super-120b-a12b": {
                "name": "Nemotron 3 Super 120B",
                "provider": "NVIDIA",
                "description": "A mid-large Nemotron reasoning model with adjustable thinking budget, between Nano and Ultra in scale.",
                "max_doc_chars": 1500000,
                "extra_params": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
            },
            "meta/llama-3.3-70b-instruct": {
                "name": "Llama 3.3 70B Instruct",
                "provider": "Meta",
                "description": "A stable, widely-used general-purpose chat and reasoning model.",
            },
            "thinkingmachines/inkling": {
                "name": "Inkling",
                "provider": "Thinking Machines",
                "description": "A general-purpose chat model from Thinking Machines.",
            },
            "openai/gpt-oss-120b": {
                "name": "GPT-OSS 120B",
                "provider": "OpenAI",
                "description": "OpenAI's open-weight reasoning model.",
            },
            "nvidia/nemotron-3.5-lightning-30b-a3b": {
                "name": "Nemotron 3.5 Lightning 30B",
                "provider": "NVIDIA",
                "description": "A fast Nemotron reasoning model with adjustable thinking budget.",
                "max_doc_chars": 700000,
                "extra_params": {"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
            },
        }

    def max_doc_chars_for(self, model: str, default: int = 700000) -> int:
        return self.models.get(model, {}).get("max_doc_chars", default)

    def _build_messages(self, messages: list[dict], image: Optional[dict] = None) -> list[dict]:
        """Attach an image to the last user message using OpenAI-style vision content, if provided."""
        if not image:
            return messages

        messages = [dict(m) for m in messages]  # shallow copy to avoid mutating caller's list
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                text_content = messages[i]["content"]
                messages[i]["content"] = [
                    {"type": "text", "text": text_content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image['media_type']};base64,{image['data']}"
                        }
                    }
                ]
                break
        return messages

    async def chat_completion(self, model: str, messages: list[dict], temperature: float = 0.3, max_tokens: int = 32000, image: Optional[dict] = None):
        """Send a message to NVIDIA API and return response."""
        if model not in self.models:
            logger.info(f"Model {model} is not in the local catalog; attempting request via NVIDIA endpoint")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": self._build_messages(messages, image),
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "stream": False
        }
        payload.update(self.models.get(model, {}).get("extra_params", {}))

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]
                    elif response.status == 401:
                        raise HTTPException(status_code=401, detail="Invalid NVIDIA API key")
                    else:
                        error_text = await response.text()
                        logger.error(f"NVIDIA API error: {response.status} - {error_text}")
                        raise HTTPException(status_code=response.status, detail=f"NVIDIA API error: {error_text}")
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="NVIDIA API request timeout")
        except Exception as e:
            logger.error(f"Error calling NVIDIA API: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calling NVIDIA API: {str(e)}")

    async def _single_completion_with_tools(self, model: str, messages: list[dict], tools: list[dict], temperature: float, max_tokens: int) -> dict:
        """One non-streaming call to NVIDIA with tools attached. Returns the raw message dict."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "tools": tools,
            "tool_choice": "auto",
            "stream": False
        }
        payload.update(self.models.get(model, {}).get("extra_params", {}))

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]
                elif response.status == 401:
                    raise HTTPException(status_code=401, detail="Invalid NVIDIA API key")
                else:
                    error_text = await response.text()
                    logger.error(f"NVIDIA API error: {response.status} - {error_text}")
                    raise HTTPException(status_code=response.status, detail=f"NVIDIA API error: {error_text}")

    async def chat_completion_with_tools(self, model: str, messages: list[dict], mcp_managers: list, temperature: float = 0.3, max_tokens: int = 32000, max_rounds: int = 12):
        """Run a tool-calling loop across one or more MCP-backed tool sets. Yields (kind, text)
        tuples where kind is 'tool' for a tool-call notice or 'text' for model-generated content,
        so the caller can stream both to the UI."""
        # Merge tools from every connected manager, and remember which manager owns each tool name.
        tools = []
        tool_owner = {}
        for manager in mcp_managers:
            for tool in manager.get_openai_tools():
                name = tool["function"]["name"]
                if name in tool_owner:
                    # Name collision across servers - keep the first, skip the duplicate.
                    continue
                tool_owner[name] = manager
                tools.append(tool)

        working_messages = [dict(m) for m in messages]

        for round_num in range(max_rounds):
            # Small delay between rounds (skip on the very first) to avoid bursting
            # past NVIDIA's per-account concurrent request limit.
            if round_num > 0:
                await asyncio.sleep(2)

            try:
                message = await self._single_completion_with_tools(model, working_messages, tools, temperature, max_tokens)
            except HTTPException as e:
                if e.status_code == 503:
                    yield ("text", "\n\n[NVIDIA's API is temporarily rate-limited (503). Please wait a few seconds and try again.]")
                    return
                raise
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                content = message.get("content") or message.get("reasoning_content") or ""
                yield ("text", content)
                return

            working_messages.append({
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": tool_calls
            })

            for call in tool_calls:
                fn_name = call["function"]["name"]
                try:
                    fn_args = json.loads(call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                yield ("tool", f"\n\n*Calling tool: `{fn_name}`({json.dumps(fn_args)})*\n\n")

                manager = tool_owner.get(fn_name)
                if manager is None:
                    tool_result_text = f"[No connected MCP server owns tool '{fn_name}']"
                else:
                    tool_result_text = await manager.call_tool(fn_name, fn_args)

                preview = tool_result_text[:1500] + ("... [truncated]" if len(tool_result_text) > 1500 else "")
                yield ("tool", f"*Result:*\n```\n{preview}\n```\n\n")

                working_messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": tool_result_text
                })

        yield ("text", "\n\n[Stopped after reaching the maximum number of tool-call rounds]")

    async def chat_completion_stream(self, model: str, messages: list[dict], temperature: float = 0.3, max_tokens: int = 32000, image: Optional[dict] = None):
        """Stream a message from NVIDIA API."""
        if model not in self.models:
            logger.info(f"Model {model} is not in the local catalog; attempting request via NVIDIA endpoint")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": self._build_messages(messages, image),
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "stream": True
        }
        payload.update(self.models.get(model, {}).get("extra_params", {}))

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as response:
                    if response.status == 200:
                        async for line in response.content:
                            if line:
                                try:
                                    text = line.decode().strip()
                                    if text.startswith("data: "):
                                        chunk_text = text[6:]
                                        if chunk_text == "[DONE]":
                                            break
                                        chunk = json.loads(chunk_text)
                                        if "choices" in chunk and chunk["choices"]:
                                            delta = chunk["choices"][0].get("delta", {})
                                            if delta.get("content"):
                                                yield delta["content"]
                                            elif delta.get("reasoning_content"):
                                                yield delta["reasoning_content"]
                                except json.JSONDecodeError:
                                    pass
                    elif response.status == 401:
                        raise HTTPException(status_code=401, detail="Invalid NVIDIA API key")
                    else:
                        error_text = await response.text()
                        logger.error(f"NVIDIA API error: {response.status} - {error_text}")
                        raise HTTPException(status_code=response.status, detail=f"NVIDIA API error: {error_text}")
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="NVIDIA API request timeout")
        except Exception as e:
            logger.error(f"Error calling NVIDIA API: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calling NVIDIA API: {str(e)}")
# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_settings(db: Session = Depends(get_db)) -> SettingsDB:
    """Get or create settings."""
    settings = db.query(SettingsDB).first()
    if not settings:
        settings = SettingsDB()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings

async def get_nvidia_client(settings: SettingsDB = Depends(get_settings)) -> NVIDIAClient:
    """Get NVIDIA API client with API key from settings or env."""
    api_key = settings.api_key or NVIDIA_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="NVIDIA API key not configured")
    return NVIDIAClient(api_key)

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting NVIDIA LLM Chat Backend ({ENVIRONMENT})")
    yield
    logger.info("Shutting down NVIDIA LLM Chat Backend")

app = FastAPI(
    title="NVIDIA LLM Chat API",
    description="API for chatting with NVIDIA-hosted LLMs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# API ROUTES - CONVERSATIONS
# ============================================================================

@app.post("/api/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(conversation: ConversationCreate, db: Session = Depends(get_db)):
    """Create a new conversation."""
    db_conversation = ConversationDB(name=conversation.name)
    db.add(db_conversation)
    db.commit()
    db.refresh(db_conversation)
    logger.info(f"Created conversation: {db_conversation.id}")
    return db_conversation

@app.get("/api/conversations", response_model=list[ConversationResponse])
async def list_conversations(db: Session = Depends(get_db)):
    """List all conversations."""
    conversations = db.query(ConversationDB).order_by(ConversationDB.updated_at.desc()).all()
    return conversations

@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get a conversation with all its messages."""
    conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = db.query(MessageDB).filter(MessageDB.conversation_id == conversation_id).order_by(MessageDB.created_at).all()
    
    return {
        "id": conversation.id,
        "name": conversation.name,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": messages
    }

@app.put("/api/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(conversation_id: int, conversation: ConversationUpdate, db: Session = Depends(get_db)):
    """Update a conversation name."""
    db_conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
    if not db_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db_conversation.name = conversation.name
    db_conversation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_conversation)
    logger.info(f"Updated conversation: {conversation_id}")
    return db_conversation

@app.delete("/api/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation."""
    db_conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
    if not db_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.delete(db_conversation)
    db.commit()
    logger.info(f"Deleted conversation: {conversation_id}")

@app.delete("/api/conversations/{conversation_id}/messages", status_code=204)
async def clear_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    """Clear all messages in a conversation, keeping the conversation itself."""
    db_conversation = db.query(ConversationDB).filter(ConversationDB.id == conversation_id).first()
    if not db_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db.query(MessageDB).filter(MessageDB.conversation_id == conversation_id).delete()
    db_conversation.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"Cleared messages for conversation: {conversation_id}")

# ============================================================================
# API ROUTES - MESSAGES
# ============================================================================

@app.post("/api/messages", response_model=MessageResponse)
async def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    """Create a message (store user message only)."""
    conversation = db.query(ConversationDB).filter(ConversationDB.id == message.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    db_message = MessageDB(
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

@app.post("/api/chat/stream")
async def chat_stream(
    chat: ChatMessage,
    db: Session = Depends(get_db),
    nvidia_client: NVIDIAClient = Depends(get_nvidia_client)
):
    """Stream a chat response from NVIDIA API."""
    conversation = db.query(ConversationDB).filter(ConversationDB.id == chat.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages_db = db.query(MessageDB).filter(MessageDB.conversation_id == chat.conversation_id).order_by(MessageDB.created_at).all()
    
    settings = await get_settings(db)
    
    effective_system_prompt = settings.system_prompt
    if chat.use_mcp:
        effective_system_prompt += (
            "\n\nYou have access to filesystem, Power BI, DuckDB, MS Access, bash, and/or web_search "
            "tools. Before calling any tool that deletes, overwrites, or irreversibly modifies a file, "
            "folder, database table, or runs a bash command that changes state (e.g. git commit, "
            "pip install, file writes), first list exactly what will be affected and ask the user "
            "to confirm in plain language (e.g. 'This will delete X, Y, Z \u2014 confirm?'). Only "
            "proceed with the destructive tool call after the user replies with a clear yes in a "
            "follow-up message. Read-only operations (listing, reading, searching, SELECT queries, "
            "git status, git diff, git log, web_search) do not need confirmation. The bash tool only "
            "runs a fixed set of allowed commands and is sandboxed to one working directory - if it "
            "is blocked, explain this to the user rather than retrying with a different phrasing of "
            "the same disallowed command. "
            "Use web_search when the question concerns recent events, information that may have "
            "changed since your training data, current documentation or version numbers, or "
            "anything that benefits from external verification. Do not use web_search for questions "
            "already answered by the conversation so far, or that local files or database tools are "
            "better suited to answer. "
            "When you run a SQL query via a DuckDB or MS Access tool, always show the exact SQL you "
            "executed in a code block before or alongside the results, so the user can see exactly "
            "what was run. When the user refines a request (e.g. 'only Germany', 'sort descending'), "
            "treat it as a modification of the most recent query rather than starting over, and show "
            "the updated SQL."
        )

    api_messages = [
        {"role": "system", "content": effective_system_prompt}
    ]
    for msg in messages_db:
        api_messages.append({"role": msg.role, "content": msg.content})

    effective_message = chat.message
    if chat.document:
        doc_cap = nvidia_client.max_doc_chars_for(chat.model)
        doc_text = extract_document_text(chat.document, max_chars=doc_cap)
        effective_message = f"{doc_text}\n\n{chat.message}".strip()

    api_messages.append({"role": "user", "content": effective_message})
    
    # Store user message (text only; image attachments are not persisted to keep the DB small)
    attachment_note = ""
    if chat.image:
        attachment_note += " [image attached]"
    if chat.document:
        attachment_note += f" [file attached: {chat.document.filename}]"
    user_message = MessageDB(
        conversation_id=chat.conversation_id,
        role="user",
        content=chat.message + attachment_note
    )
    db.add(user_message)
    db.commit()

    image_dict = chat.image.dict() if chat.image else None

    async def generate():
        full_response = ""
        try:
            if chat.use_mcp:
                active_mcp_managers = [m for m in (powerbi_mcp, filesystem_mcp, duckdb_mcp, access_mcp, native_tools) if m.is_connected()]
                if not active_mcp_managers:
                    yield f"data: {json.dumps({'error': 'No MCP server is connected. Connect one first from Chat Options.'})}\n\n"
                    return
                async for kind, text in nvidia_client.chat_completion_with_tools(
                    model=chat.model,
                    messages=api_messages,
                    mcp_managers=active_mcp_managers,
                    temperature=chat.temperature,
                    max_tokens=chat.max_tokens
                ):
                    full_response += text
                    yield f"data: {json.dumps({'chunk': text})}\n\n"
            else:
                async for chunk in nvidia_client.chat_completion_stream(
                    model=chat.model,
                    messages=api_messages,
                    temperature=chat.temperature,
                    max_tokens=chat.max_tokens,
                    image=image_dict
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
        
        # Store assistant response (skip empty responses to avoid
        # "Empty content is not allowed for assistant messages" on retry)
        if full_response.strip():
            assistant_message = MessageDB(
                conversation_id=chat.conversation_id,
                role="assistant",
                content=full_response
            )
            db.add(assistant_message)
            db.commit()
        else:
            logger.error(f"Model {chat.model} returned empty content; not saving assistant message")
            yield f"data: {json.dumps({'error': 'Model returned empty response'})}\n\n"
            return
        
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/api/chat/complete")
async def chat_complete(
    chat: ChatMessage,
    db: Session = Depends(get_db),
    nvidia_client: NVIDIAClient = Depends(get_nvidia_client)
):
    """Send a message and get a complete response (non-streaming)."""
    conversation = db.query(ConversationDB).filter(ConversationDB.id == chat.conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages_db = db.query(MessageDB).filter(MessageDB.conversation_id == chat.conversation_id).order_by(MessageDB.created_at).all()
    
    settings = await get_settings(db)
    
    api_messages = [
        {"role": "system", "content": settings.system_prompt}
    ]
    for msg in messages_db:
        api_messages.append({"role": msg.role, "content": msg.content})

    effective_message = chat.message
    if chat.document:
        doc_cap = nvidia_client.max_doc_chars_for(chat.model)
        doc_text = extract_document_text(chat.document, max_chars=doc_cap)
        effective_message = f"{doc_text}\n\n{chat.message}".strip()

    api_messages.append({"role": "user", "content": effective_message})
    
    attachment_note = ""
    if chat.image:
        attachment_note += " [image attached]"
    if chat.document:
        attachment_note += f" [file attached: {chat.document.filename}]"
    user_message = MessageDB(
        conversation_id=chat.conversation_id,
        role="user",
        content=chat.message + attachment_note
    )
    db.add(user_message)
    db.commit()
    
    try:
        response_content = await nvidia_client.chat_completion(
            model=chat.model,
            messages=api_messages,
            temperature=chat.temperature,
            max_tokens=chat.max_tokens,
            image=chat.image.dict() if chat.image else None
        )
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise
    
    assistant_message = MessageDB(
        conversation_id=chat.conversation_id,
        role="assistant",
        content=response_content
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    
    return MessageResponse.from_orm(assistant_message)

# ============================================================================
# API ROUTES - SETTINGS
# ============================================================================

@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings_endpoint(settings: SettingsDB = Depends(get_settings)):
    """Get current settings."""
    return settings

@app.put("/api/settings", response_model=SettingsResponse)
async def update_settings(
    settings_update: SettingsUpdate,
    settings: SettingsDB = Depends(get_settings),
    db: Session = Depends(get_db)
):
    """Update settings."""
    if settings_update.api_key is not None:
        settings.api_key = settings_update.api_key
    if settings_update.default_model is not None:
        settings.default_model = settings_update.default_model
    if settings_update.temperature is not None:
        settings.temperature = settings_update.temperature
    if settings_update.max_tokens is not None:
        settings.max_tokens = settings_update.max_tokens
    if settings_update.system_prompt is not None:
        settings.system_prompt = settings_update.system_prompt
    if settings_update.theme is not None:
        settings.theme = settings_update.theme
    
    settings.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings)
    logger.info("Updated settings")
    return settings

# ============================================================================
# API ROUTES - MODELS
# ============================================================================

@app.get("/api/models", response_model=list[ModelInfo])
async def list_models(settings: SettingsDB = Depends(get_settings)):
    """List available NVIDIA models."""
    nvidia_client = NVIDIAClient(settings.api_key or NVIDIA_API_KEY)
    models = []
    for model_id, info in nvidia_client.models.items():
        models.append(ModelInfo(
            id=model_id,
            name=info["name"],
            provider=info["provider"],
            description=info.get("description"),
            multimodal=info.get("multimodal", False)
        ))
    return models

# ============================================================================
# API ROUTES - MCP (Power BI Modeling MCP server)
# ============================================================================

@app.post("/api/mcp/powerbi/connect")
async def mcp_powerbi_connect():
    """Launch and connect to the local Power BI Modeling MCP server."""
    try:
        await powerbi_mcp.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Power BI MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Power BI MCP server: {e}")
    tools = powerbi_mcp.get_openai_tools()
    return {"connected": True, "tool_count": len(tools), "tools": [t["function"]["name"] for t in tools]}

@app.post("/api/mcp/powerbi/disconnect")
async def mcp_powerbi_disconnect():
    """Disconnect from the local Power BI Modeling MCP server."""
    await powerbi_mcp.disconnect()
    return {"connected": False}

@app.get("/api/mcp/powerbi/status")
async def mcp_powerbi_status():
    """Check whether the Power BI Modeling MCP server is connected, and list its tools."""
    tools = powerbi_mcp.get_openai_tools() if powerbi_mcp.is_connected() else []
    return {
        "connected": powerbi_mcp.is_connected(),
        "tool_count": len(tools),
        "tools": [t["function"]["name"] for t in tools]
    }

# ============================================================================
# API ROUTES - MCP (Filesystem MCP server)
# ============================================================================

@app.post("/api/mcp/filesystem/connect")
async def mcp_filesystem_connect():
    """Launch and connect to the local Filesystem MCP server."""
    try:
        await filesystem_mcp.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Filesystem MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Filesystem MCP server: {e}")
    tools = filesystem_mcp.get_openai_tools()
    return {"connected": True, "tool_count": len(tools), "tools": [t["function"]["name"] for t in tools]}

@app.post("/api/mcp/filesystem/disconnect")
async def mcp_filesystem_disconnect():
    """Disconnect from the local Filesystem MCP server."""
    await filesystem_mcp.disconnect()
    return {"connected": False}

@app.get("/api/mcp/filesystem/status")
async def mcp_filesystem_status():
    """Check whether the Filesystem MCP server is connected, and list its tools."""
    tools = filesystem_mcp.get_openai_tools() if filesystem_mcp.is_connected() else []
    return {
        "connected": filesystem_mcp.is_connected(),
        "tool_count": len(tools),
        "tools": [t["function"]["name"] for t in tools],
        "allowed_directories": FILESYSTEM_MCP_ALLOWED_DIRS
    }

# ============================================================================
# API ROUTES - MCP (DuckDB MCP server)
# ============================================================================

@app.post("/api/mcp/duckdb/connect")
async def mcp_duckdb_connect():
    """Launch and connect to the local DuckDB MCP server."""
    try:
        await duckdb_mcp.connect()
    except Exception as e:
        logger.error(f"Failed to connect to DuckDB MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to DuckDB MCP server: {e}")
    tools = duckdb_mcp.get_openai_tools()
    return {"connected": True, "tool_count": len(tools), "tools": [t["function"]["name"] for t in tools]}

@app.post("/api/mcp/duckdb/disconnect")
async def mcp_duckdb_disconnect():
    """Disconnect from the local DuckDB MCP server."""
    await duckdb_mcp.disconnect()
    return {"connected": False}

@app.get("/api/mcp/duckdb/status")
async def mcp_duckdb_status():
    """Check whether the DuckDB MCP server is connected, and list its tools."""
    tools = duckdb_mcp.get_openai_tools() if duckdb_mcp.is_connected() else []
    return {
        "connected": duckdb_mcp.is_connected(),
        "tool_count": len(tools),
        "tools": [t["function"]["name"] for t in tools],
        "db_path": DUCKDB_MCP_DB_PATH
    }

# ============================================================================
# API ROUTES - MCP (Custom MS Access MCP server)
# ============================================================================

@app.post("/api/mcp/access/connect")
async def mcp_access_connect():
    """Launch and connect to the custom MS Access MCP server."""
    try:
        await access_mcp.connect()
    except Exception as e:
        logger.error(f"Failed to connect to Access MCP server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to connect to Access MCP server: {e}")
    tools = access_mcp.get_openai_tools()
    return {"connected": True, "tool_count": len(tools), "tools": [t["function"]["name"] for t in tools]}

@app.post("/api/mcp/access/disconnect")
async def mcp_access_disconnect():
    """Disconnect from the custom MS Access MCP server."""
    await access_mcp.disconnect()
    return {"connected": False}

@app.get("/api/mcp/access/status")
async def mcp_access_status():
    """Check whether the Access MCP server is connected, and list its tools."""
    tools = access_mcp.get_openai_tools() if access_mcp.is_connected() else []
    return {
        "connected": access_mcp.is_connected(),
        "tool_count": len(tools),
        "tools": [t["function"]["name"] for t in tools],
        "folder": ACCESS_MCP_FOLDER
    }

# ============================================================================
# API ROUTES - Native tools (bash, and future non-MCP tools)
# ============================================================================

@app.post("/api/tools/native/connect")
async def native_tools_connect():
    """Enable the native tool set (currently: bash)."""
    await native_tools.connect()
    tools = native_tools.get_openai_tools()
    return {"connected": True, "tool_count": len(tools), "tools": [t["function"]["name"] for t in tools]}

@app.post("/api/tools/native/disconnect")
async def native_tools_disconnect():
    """Disable the native tool set."""
    await native_tools.disconnect()
    return {"connected": False}

@app.get("/api/tools/native/status")
async def native_tools_status():
    """Check whether native tools are enabled, and list them plus the bash sandbox config."""
    tools = native_tools.get_openai_tools() if native_tools.is_connected() else []
    return {
        "connected": native_tools.is_connected(),
        "tool_count": len(tools),
        "tools": [t["function"]["name"] for t in tools],
        "bash_workdir": BASH_TOOL_WORKDIR,
        "bash_allowed_commands": sorted(BASH_TOOL_ALLOWED_COMMANDS)
    }

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}

# ============================================================================
# ROOT
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "NVIDIA LLM Chat API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
