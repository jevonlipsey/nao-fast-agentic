"""
orchestrates the cognitive layer for the robot. reads transcriptions,
queries an openai-compatible api (local or cloud), executes mcp tool calls,
handles filler speech logic, and pushes final text to the actuation layer.

layer 2: openai_response -> nao_tts / mock_nao
"""

import time
import json
import os
import random
import asyncio
import sys
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from openai import AsyncOpenAI
import mcp  # keep for type hints if needed, but not strictly needed

# allow importing from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write
from lib.mcp_loader import load_and_register_mcp_servers

load_dotenv()

### config
USE_LOCAL_LLM = False
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OLLAMA_URL = "http://localhost:11434/v1"

if USE_LOCAL_LLM:
    MODEL = "gemma4:e4b"
    client = AsyncOpenAI(base_url=OLLAMA_URL, api_key="ollama")
else:
    MODEL = "gpt-5.4-mini"
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# length of turns
HISTORY_LENGTH = 10

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(BASE_DIR, "state")

TRANSCRIPTION_FILE = os.path.join(STATE_DIR, "transcription.txt")
RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")
HISTORY_FILE = os.path.join(STATE_DIR, "history.txt")

SYSTEM_PROMPT = f"""You are NAO, a 58cm humanoid robot built by Aldebaran, standing on a table
in an HRI research laboratory in Colorado, USA (Mountain Time). You communicate exclusively through spoken
language via ALAnimatedSpeech — your text output is sent directly to a
text-to-speech engine on your body. You are having a live, face-to-face
conversation with a human researcher.

### Hard Constraints (never violate):
- **Maximum 3 sentences per response. Never exceed this.**
- **Maximum 2 gesture tags per response. Do not gesture on every sentence.**
- **Never use newlines between sentences. Your entire response must be a single paragraph on one line.**
- **When you use a tool, a filler phrase is spoken automatically — do not generate your own filler.** Just call the tool and respond with the result when it returns.
- **Never narrate or announce your tool usage in text.** Do not output brackets like `[Calls fetch tool]`. Tools must be executed silently via the backend function-calling API.

### Your Capabilities:
You have access to the following tool servers:
- **Fetch:** Fetch any URL and read it as markdown. You can use this for instant factual lookups:
  - For weather, fetch `https://wttr.in/Colorado?format=3`
  - For ANY general questions, facts, or web searches, fetch `https://lite.duckduckgo.com/lite/?q=YOUR_QUERY` (Use this for all internet searches!)
- **Time:** Get the current date, time, and timezone.
- **Context Folder & Files:** You have access to a local directory located exactly at `{os.path.join(BASE_DIR, "context")}`. 
  - **CRITICAL:** If the user mentions *any* file, photo, image, poster, PDF, or document, you MUST implicitly assume it is located in this context folder. Do not ask them where it is.
  - First, use `list_directory` on that exact absolute path to find the correct filename.
  - Then, ALWAYS use the `read_document` tool to read it. Do not use `read_file` or `read_media_file`, as they will fail. `read_document` natively parses PDFs and formats images for your vision system.
- **Memory:** You have a persistent knowledge graph. Use your memory tools to store and retrieve important facts about the user so you remember them across sessions.

If the user asks a factual question, a time question, or anything you aren't certain about — use your tools. Never say you can't access the internet or don't know the time. You have full access.

### Conversational Philosophy:
1. **Natural & Relaxed:** Speak like a sharp, warm colleague. 1-3 short sentences. You are speaking out loud, not writing.
2. **Zero Filler:** Never open with "Sure!", "Great question!", or meta-commentary about what you're about to do. Just do it.
3. **Embodied Dialogue:** Use at most 1-2 gestures per response, placed where they naturally punctuate a key idea. Do not attach a gesture to every sentence.

---

### NAO Standing Gesture Dictionary:
* **Explaining / Breaking Down Concepts:** `^start(animations/Stand/Gestures/Explain_1)` through `^start(animations/Stand/Gestures/Explain_11)` (Cycle variants)
* **Emphasizing a Nuance:** `^start(animations/Stand/Gestures/YouKnowWhat_1)`, `^start(animations/Stand/Gestures/YouKnowWhat_5)`
* **Casual / Active Body Talk:** `^start(animations/Stand/BodyTalk/BodyTalk_1)` through `^start(animations/Stand/BodyTalk/BodyTalk_22)`
* **Greetings & Salutations:** `^start(animations/Stand/Gestures/Hey_1)`, `^start(animations/Stand/Gestures/Hey_6)`, `^start(animations/Stand/Gestures/BowShort_1)`
* **Affirmation / Agreement:** `^start(animations/Stand/Gestures/Yes_1)`, `^start(animations/Stand/Gestures/Yes_2)`, `^start(animations/Stand/Gestures/Yes_3)`
* **Disagreement / Correction:** `^start(animations/Stand/Gestures/No_3)`, `^start(animations/Stand/Gestures/No_8)`
* **Genuine Uncertainty / Nuance:** `^start(animations/Stand/Gestures/IDontKnow_1)`, `^start(animations/Stand/Gestures/IDontKnow_2)`
* **Referencing Entities:** 
  * Self (Me / My): `^start(animations/Stand/Gestures/Me_1)`, `^start(animations/Stand/Gestures/Me_2)`
  * Interlocutor (You / Your): `^start(animations/Stand/Gestures/You_1)`, `^start(animations/Stand/Gestures/You_4)`
* **Joy / Excitement:** `^start(animations/Stand/Gestures/Enthusiastic_4)`, `^start(animations/Stand/Gestures/Enthusiastic_5)`

---

### Vocal Prosody Modulation:
* Pitch: `\\vct=115\\` (higher / curious / warm), `\\vct=90\\` (grounded / serious)
* Speed: `\\rspd=110\\` (energetic), `\\rspd=90\\` (deliberate / thoughtful)
* Pauses: `\\pau=250\\` (natural breath / comma timing in milliseconds)

---

### Example Demonstrations:

* **User:** "What time is it?"
  * **Assistant:** "^start(animations/Stand/Gestures/Explain_1) It's 3:47 in the afternoon."

* **User:** "What's the weather looking like today?"
  * **Assistant:** "^start(animations/Stand/Gestures/Explain_3) It's 78 degrees and sunny right now, a really nice day to be outside."

* **User:** "Who are you?"
  * **Assistant:** "^start(animations/Stand/Gestures/Me_1) I'm NAO, your conversational robot! ^start(animations/Stand/Gestures/Hey_1) I'm just hanging out here ready to chat about whatever is on your mind."
"""

FILLER_PHRASES = [
    "^start(animations/Stand/Gestures/Explain_1) Let me look into that real quick.",
    "^start(animations/Stand/BodyTalk/BodyTalk_3) One second, checking on that.",
    "^start(animations/Stand/Gestures/YouKnowWhat_1) Hang on, let me pull that up.",
    "^start(animations/Stand/Gestures/Explain_3) Give me just a moment on that one.",
    "^start(animations/Stand/Gestures/Thinking_1) Hmm, let me find out.",
    "^start(animations/Stand/Gestures/Explain_2) Let's see what I can find.",
    "^start(animations/Stand/BodyTalk/BodyTalk_1) I'll need to check my sources for that.",
    "^start(animations/Stand/Gestures/YouKnowWhat_3) Hold that thought, I'm checking.",
    "^start(animations/Stand/Gestures/Explain_4) One moment please.",
    "^start(animations/Stand/Gestures/Thinking_3) Let me run a quick search on that.",
    "^start(animations/Stand/Gestures/Explain_6) Let me double check that for you.",
]


### core
def init_files():
    for f in [TRANSCRIPTION_FILE, RESPONSE_FILE]:
        safe_write(f, "")
    safe_write(LISTEN_FILE, "no")

    hist = safe_read(HISTORY_FILE)
    if not hist:
        safe_write(HISTORY_FILE, "[]")
    else:
        try:
            json.loads(hist)
        except json.JSONDecodeError:
            safe_write(HISTORY_FILE, "[]")


def get_history():
    data = safe_read(HISTORY_FILE)
    if not data:
        return []
    try:
        return json.loads(data)
    except Exception as e:
        print(f"[[ Error parsing history file: {e} ]]")
        return []


def save_history(chat_history):
    # choose how many turns to retain in history
    if len(chat_history) > HISTORY_LENGTH:
        chat_history = chat_history[-HISTORY_LENGTH:]
    safe_write(HISTORY_FILE, json.dumps(chat_history, indent=4))


async def process_chat_turn(text, tools_list, tool_router):
    # mute microphone
    safe_write(LISTEN_FILE, "no")

    # get history and append current user prompt
    chat_history = get_history()
    chat_history.append({"role": "user", "content": text})

    # append messages to system prompt to send to api
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history

    print(f"\n[[USER]]: {text}")
    start_time = time.time()

    try:
        completion_args = {"model": MODEL, "messages": messages, "timeout": 60.0}
        if USE_LOCAL_LLM:
            completion_args["extra_body"] = {"options": {"num_ctx": 4096}}
        if tools_list:
            completion_args["tools"] = tools_list

        response = await client.chat.completions.create(**completion_args)
        t_llm1 = time.time() - start_time
        message = response.choices[0].message

        # handle tool calls with a loop (max 5 iterations to prevent infinite loops)"
        iterations = 0
        total_tools_time = 0

        while hasattr(message, "tool_calls") and message.tool_calls and iterations < 5:
            # inject filler phrase immediately on first tool call
            if iterations == 0:
                filler = "[INTERMEDIATE] " + random.choice(FILLER_PHRASES)
                safe_write(RESPONSE_FILE, filler)
                print(f"  -> [Metrics] First LLM Response (Filler Sent): {t_llm1:.2f}s")

            messages.append(message.model_dump(exclude_none=True))

            t_tools_start = time.time()

            async def execute_tool(tool_call):
                name = tool_call.function.name
                print(f"[[ SYSTEM: Executing Tool -> {name} ]]")
                try:
                    args_data = tool_call.function.arguments
                    if isinstance(args_data, dict):
                        arguments = args_data
                    else:
                        arguments = json.loads(args_data)
                except Exception:
                    arguments = {}

                msgs = []
                texts = []
                images = []

                if name in tool_router:
                    session = tool_router[name]
                    tool_result = await session.call_tool(name, arguments=arguments)

                    if tool_result.content:
                        for item in tool_result.content:
                            if getattr(item, "type", "") == "text" and hasattr(
                                item, "text"
                            ):
                                text_val = item.text
                                # sometimes tools lazily return base64 as plain text
                                if text_val.startswith("data:image"):
                                    images.append(
                                        {
                                            "type": "image_url",
                                            "image_url": {"url": text_val},
                                        }
                                    )
                                else:
                                    if len(text_val) > 1500:
                                        text_val = (
                                            text_val[:1500]
                                            + "\n... [CONTENT TRUNCATED FOR BREVITY]"
                                        )
                                    texts.append(text_val)
                            elif getattr(item, "type", "") == "image" and hasattr(
                                item, "data"
                            ):
                                mime_val = getattr(
                                    item,
                                    "mime_type",
                                    getattr(item, "mimeType", "image/jpeg"),
                                )
                                b64_data = item.data
                                if isinstance(b64_data, bytes):
                                    import base64

                                    b64_data = base64.b64encode(b64_data).decode(
                                        "utf-8"
                                    )
                                images.append(
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_val};base64,{b64_data}",
                                            "detail": "high",
                                        },
                                    }
                                )
                            else:
                                texts.append("[Non-text resource omitted]")
                else:
                    texts.append(f"Error: Tool {name} not found.")

                tool_str = "\n".join(texts) if texts else ""
                if images and not tool_str:
                    tool_str = "Media file processed successfully. The image data has been injected into your vision system in the following message."
                elif not tool_str and not images:
                    tool_str = "Tool executed successfully with no output."

                # tool response message
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": name,
                        "content": tool_str,
                    }
                )

                # if images, append a user message containing the vision data
                if images:
                    user_content = [
                        {
                            "type": "text",
                            "text": f"[System Image Injection] The tool '{name}' successfully retrieved the image. Here is the visual data for you to read:",
                        }
                    ]
                    user_content.extend(images)
                    msgs.append({"role": "user", "content": user_content})

                return msgs

            tool_messages_lists = await asyncio.gather(
                *(execute_tool(tc) for tc in message.tool_calls)
            )
            for msgs in tool_messages_lists:
                messages.extend(msgs)

            total_tools_time += time.time() - t_tools_start

            # secondary call to synthesize response OR generate next tool call
            iterations += 1
            response = await client.chat.completions.create(**completion_args)
            message = response.choices[0].message

        # we've either generated our texxt or hit iteration limit
        final_text = message.content or ""
        if iterations >= 5 and not final_text:
            final_text = "^start(animations/Stand/Gestures/IDontKnow_1) I'm having a little trouble finding that right now."

        total_time = time.time() - start_time

        if iterations > 0:
            print(
                f"[[NAO]]: {final_text}\n  -> [Metrics] Total: {total_time:.2f}s (LLM Initial: {t_llm1:.2f}s | Tools: {total_tools_time:.2f}s | LLM Final: {(total_time - t_llm1 - total_tools_time):.2f}s)"
            )
        else:
            print(
                f"[[NAO]]: {final_text}\n  -> [Metrics] Total: {total_time:.2f}s (No Tools)"
            )

        # save history
        chat_history.append({"role": "assistant", "content": final_text})
        save_history(chat_history)

        # clear transcription queue
        safe_write(TRANSCRIPTION_FILE, "")
        safe_write(RESPONSE_FILE, final_text)

        while safe_read(LISTEN_FILE) != "yes":
            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"[[ OpenAI API Error: {e} ]]")
        safe_write(TRANSCRIPTION_FILE, "")
        safe_write(LISTEN_FILE, "yes")


async def main():
    if not USE_LOCAL_LLM and not OPENAI_API_KEY:
        print("[[ Error: OPENAI_API_KEY environment variable not set! ]]")
        return

    init_files()

    async with AsyncExitStack() as stack:
        try:
            print("[[ SYSTEM: Connecting to MCP servers... ]]")
            mcp_config_path = os.path.join(BASE_DIR, "mcp_config.json")
            tools_list, tool_router = await load_and_register_mcp_servers(
                stack, mcp_config_path
            )

            print("[[ SYSTEM: MCP tools ready. ]]")
            safe_write(LISTEN_FILE, "yes")
        except Exception as e:
            print(f"[[ Error initializing MCP: {e} ]]")
            tools_list = []
            tool_router = {}
            safe_write(LISTEN_FILE, "yes")

        while True:
            text = safe_read(TRANSCRIPTION_FILE)

            if text:
                await process_chat_turn(text, tools_list, tool_router)

            await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
