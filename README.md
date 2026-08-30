# nao-fast-agentic

<img width="1387" height="540" alt="image" src="https://ray.so/LSCtX0c" />


This project extends the [Nao-ChatGPT](https://github.com/MIRRORLab-Summer-Interns-2024/Nao-ChatGPT) repository built by the MIRRORLab Summer 2024 interns. That project connected the Aldebaran Nao robot to ChatGPT so it could listen to speech, generate a response, and speak it back with gestures. This project builds on that foundation with two goals:

1. **Improve the robot's capabilities.** The robot now features native multimodal vision and external tool calling. It can actively see you during a conversation using its built-in camera, read and summarize local documents (PDFs, PNGs, TXT), and browse the web using the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). While tools are running, the robot speaks a filler phrase like "Let me look that up" so the conversation doesn't stall. It also supports local LLMs via [Ollama](https://ollama.com/) as an alternative to the OpenAI API.

2. **Simplify the setup process.** The original project required a Windows VM and complicated pathing to run the Nao SDK (on Mac). This project eliminates that requirement. Automated setup scripts (`setup.sh` / `setup.bat`) handle the SDK installation across Mac, Linux, and Windows. A single `python main.py` command boots the entire pipeline, including the legacy Python 2.7 robot layer.

---

## How It Works

The pipeline runs four processes in parallel, coordinated through text/jpg files in the `state/` directory:

| Process                      | Role                                                                   | Environment                       |
| ---------------------------- | ---------------------------------------------------------------------- | --------------------------------- |
| `whisper_stt.py`             | Listens to the microphone and writes transcriptions                    | Python 3.10+                      |
| `openai_response.py`         | Sends transcriptions to the LLM, executes tool calls, writes responses | Python 3.10+                      |
| `nao_tts.py` / `mock_nao.py` | Reads responses and makes the robot speak and gesture                  | Python 2.7 (Conda) / Python 3.10+ |
| `nao_vision.py`              | Polls the robot's top camera at 1 FPS and saves the frame              | Python 2.7 (Conda)                |

On macOS, speech-to-text uses a compiled Swift CoreML worker for fast local transcription. On Windows and Linux, it falls back to Python Whisper.

---

## 1. Prerequisites

You will need the following installed on your machine before running the setup scripts.

### All Platforms

| Tool                                                   | What it does here                                          | Install                                                                                                                                                                                                               |
| ------------------------------------------------------ | ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [Conda](https://docs.conda.io/en/latest/)              | Creates an isolated Python 2.7 environment for the Nao SDK | Mac/Linux: [Miniforge](https://github.com/conda-forge/miniforge#download). Windows: [Miniconda](https://docs.anaconda.com/miniconda/install/). If you already have Anaconda or another Conda variant, that works too. |
| [Node.js & npm](https://nodejs.org/)                   | Runs the JavaScript-based MCP tool servers                 | Download from [nodejs.org](https://nodejs.org/)                                                                                                                                                                       |
| [uv](https://docs.astral.sh/uv/)                       | Runs the Python-based MCP tool servers                     | See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/)                                                                                                                                   |
| [OpenAI API Key](https://platform.openai.com/api-keys) | Authenticates requests to the LLM                          | Create an account at [platform.openai.com](https://platform.openai.com/) and generate an API key                                                                                                                      |

### Mac Only

| Tool                         | What it does here                                                                       | Install                                       |
| ---------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------- |
| Xcode Command Line Tools     | Provides `install_name_tool`, needed to patch the SDK's C++ libraries for Apple Silicon | Run `xcode-select --install` in your terminal |
| [Homebrew](https://brew.sh/) | Package manager used to install PortAudio                                               | See [brew.sh](https://brew.sh/)               |
| PortAudio                    | Audio library required by the `PyAudio` Python package for microphone access            | Run `brew install portaudio`                  |

### Linux Only

| Tool      | What it does here                                                            | Install                                    |
| --------- | ---------------------------------------------------------------------------- | ------------------------------------------ |
| PortAudio | Audio library required by the `PyAudio` Python package for microphone access | Run `sudo apt-get install portaudio19-dev` |

### Windows

No additional platform-specific tools are needed beyond the ones listed under "All Platforms."

---

## 2. Nao SDK Setup (Python 2.7)

The Nao robot's SDK only runs on Python 2.7. The setup scripts automate the process of creating an isolated Conda environment, extracting the SDK into it, and configuring all the necessary paths.

1. Go to the [Maxtronics Developer Center](https://maxtronics.com/en/software-development-kit/) and download the Python 2.7 SDK for your operating system.
2. **Leave the downloaded file in your `~/Downloads` folder.** Do not rename or extract it. The script will find and extract it automatically.
   - Mac/Linux: The file should be a `.tar.gz` archive. If you use Safari, check that it did not auto-extract into a folder.
   - Windows: The file should be a `.zip` archive.
3. Open your terminal (Mac/Linux) or Miniconda Prompt (Windows) and navigate to this repository.
4. Run the setup script:

   ```bash
   # Mac / Linux
   ./setup/setup.sh

   # Windows
   setup\setup.bat
   ```

The script will create a Conda environment called `nao`, install Python 2.7, extract the SDK, set environment variables, and (on Mac) patch the C++ libraries to work on Apple Silicon.

---

## 3. Python Environment Setup (Python 3.10+)

The AI components (speech recognition, LLM communication, MCP tools) run on your standard modern Python. We recommend **Python 3.10 or higher** to ensure compatibility with modern AI libraries and `uv`.

1. Make sure you are **not** in the `nao` Conda environment. If you are, run `conda deactivate`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file at the root of this project and add your OpenAI API key:
   ```
   OPENAI_API_KEY="sk-..."
   ```

---

## 4. Running the Pipeline

Everything is launched from a single command:

```bash
python main.py
```

This starts the STT listener, the LLM cognitive layer, and the robot actuation layer. Once you see `[[LISTENING]]` in the terminal, the robot is ready to talk.

### Mock Mode vs. Physical Robot

By default, `main.py` runs in mock mode (`USE_MOCK_NAO = True`).

**What to expect in the terminal:**

- **Mock Mode:** You will see the transcriptions and the robot's generated responses (e.g., `[[NAO]]: Hello there!`) printed directly in the terminal. The system simulates the physical actuation delays so the pipeline continues seamlessly without hardware.
- **Physical Hardware:** You will see the exact same terminal output, but the physical robot will simultaneously speak the responses and perform the requested gestures.

To connect to a real Nao robot:

1. Open `scripts/nao_tts.py` and `scripts/test_connection.py` and set the `IP` variable to your robot's IP address. You can find this by pressing the robot's chest button.
2. In `main.py`, set `USE_MOCK_NAO = False`.
3. Run `python main.py`. The orchestrator will automatically use `conda run` to launch the actuation script inside the Python 2.7 environment.

---

## Troubleshooting

### Safari Auto-Extracting SDK Files (Mac)

If you download the Mac SDK via Safari, it may automatically unzip the `.tar.gz` file into a folder, which will break the setup script. Go to Safari **Settings > General** and uncheck "Open 'safe' files after downloading", then download the SDK again so it remains a `.tar.gz`.

### Conda Environment Fails to Build

If `./setup.sh` or `setup.bat` fails, you may have a conflicting Conda installation. Try running `conda clean --all` or completely removing your old Conda installation and installing a fresh copy of Miniforge/Miniconda.

### Windows PowerShell Issues (VS Code / Standard Terminal)

If you are trying to run the pipeline inside standard Windows PowerShell or the VS Code terminal and it fails, you likely need to configure PowerShell to allow Conda and script execution.

**Fix 1: Allow Script Execution**
By default, Windows blocks terminal scripts for security. If you see a red error when running Conda, `uv`, or `npm`:

1. Open PowerShell as an **Administrator**.
2. Run this command to safely allow local scripts:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

**Fix 2: Initialize Conda for PowerShell**
If PowerShell says the `conda` command is not recognized, you need to link them:

1. Open the **Anaconda Prompt** or **Miniconda Prompt** from your Start menu.
2. Run:
   ```cmd
   conda init powershell
   ```
3. Close the prompt and restart your normal PowerShell or VS Code terminal.

### Testing the Robot Connection

If the pipeline boots but the robot isn't responding, you can verify your IP address and connection using the standalone test script:

```bash
conda activate nao
python scripts/test_connection.py
```

---

## Configuration

### Microphone Selection

To change which microphone the system listens on, open `scripts/whisper_stt.py` and update the `MICROPHONE_INDEX` variable. There is a commented-out code block in the `main()` function that lists all available audio devices and their indexes when uncommented.

### Adding Native Tools

The robot's tool capabilities are defined primarily via MCP servers, but some tightly coupled hardware features (like the `take_picture` tool) are implemented natively inside `scripts/openai_response.py`.

The `take_picture` tool interacts with `scripts/nao_vision.py` (which runs in Python 2.7 and grabs a frame every second, saving it to `state/latest_frame.jpg`). The LLM reads this file when using the tool, creating an ultra-fast, low-latency live vision pipeline without the overhead of an MCP server. (Note: When running in Mock mode, `scripts/mock_vision.py` captures frames from your computer's webcam instead, allowing you to test the full vision pipeline without the robot).d

Additionally, `mcp-servers/` has one custom local MCP called `vision-reader`. This tool allows PDFs and images to get piped cleanly through OpenAi's API endpoint.

### Adding MCP Tools

The robot's tool capabilities are defined in `mcp_config.json` at the project root. To add a new tool server, add a new entry following the existing format:

```json
{
  "mcpServers": {
    "your_server_name": {
      "command": "uvx",
      "args": ["your-mcp-server-package"]
    }
  }
}
```

The system will automatically discover and register the new tools on next boot. No code changes are needed.

### Local LLM (Ollama)

To use a local model instead of the OpenAI API, install [Ollama](https://ollama.com/), pull a model (e.g. `ollama pull gemma3:4b`), and set `USE_LOCAL_LLM = True` in `scripts/openai_response.py`.

---

## Project Structure

```
nao-fast-agentic/
  main.py                  # orchestrator, launches all processes
  mcp_config.json          # MCP tool server configuration
  requirements.txt         # Python 3.10+ dependencies
  .env                     # API keys (not checked in)
  setup/
    setup.sh               # automated Mac/Linux SDK setup
    setup.bat              # automated Windows SDK setup
  scripts/
    whisper_stt.py          # speech-to-text (CoreML on Mac, Whisper fallback elsewhere)
    openai_response.py      # LLM communication and MCP tool execution
    nao_tts.py              # robot actuation (Python 2.7, runs in the nao Conda env)
    mock_nao.py             # terminal-based mock of the robot for testing
    test_connection.py      # standalone script to verify robot IP (Python 2.7)
    lib/
      file_utils.py         # shared file I/O with retry logic (Python 2/3 compatible)
      mcp_loader.py         # dynamic MCP server loader
  stt-coreml/               # Swift CoreML speech-to-text worker (macOS)
  state/                    # IPC text files (listen, response, transcription, history)
```
