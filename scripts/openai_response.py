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
import textwrap
import re
from dotenv import load_dotenv
from contextlib import AsyncExitStack
from openai import AsyncOpenAI
from rich.console import Console

# allow importing from lib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.file_utils import safe_read, safe_write, queue_push
from lib.mcp_loader import load_and_register_mcp_servers

load_dotenv()
console = Console()

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
EVENTS_FILE = os.path.join(STATE_DIR, "events.txt")
RESPONSE_FILE = os.path.join(STATE_DIR, "response.txt")
LISTEN_FILE = os.path.join(STATE_DIR, "listen.txt")
HISTORY_FILE = os.path.join(STATE_DIR, "history.txt")

# read system prompt
prompt_path = os.path.join(BASE_DIR, "config", "system_prompt.md")
SYSTEM_PROMPT = safe_read(prompt_path)
if "{CONTEXT_DIR}" in SYSTEM_PROMPT:
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{CONTEXT_DIR}", os.path.join(BASE_DIR, "context"))

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
    for f in [TRANSCRIPTION_FILE, RESPONSE_FILE, EVENTS_FILE]:
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
        console.print(f"[bold red][[ Error parsing history file: {e} ]][/]")
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

    wrapped_user = textwrap.fill(text, width=90)
    if text.startswith("[SYSTEM EVENT]"):
        console.print(f"\n[dim white]{wrapped_user}[/]")
    else:
        console.print(f"\n[bold cyan][[USER]]:[/] {wrapped_user}")
    
    start_time = time.time()

    try:
        CAMERA_TOOL = {
            "type": "function",
            "function": {
                "name": "take_picture",
                "description": "Take a photo through your eyes. If you can't see the target clearly, you MUST use 'look_around' to move your head and then call 'take_picture' again to check the new view. Remember to use toggle_awareness(True) when you are completely finished looking around so you can track the user again."
            }
        }
        
        # inject it into the tools list we give to openai
        active_tools = tools_list + [CAMERA_TOOL] if tools_list else [CAMERA_TOOL]

        completion_args = {"model": MODEL, "messages": messages, "timeout": 60.0}
        if text.startswith("[SYSTEM EVENT]"):
            completion_args["max_completion_tokens"] = 60
        if USE_LOCAL_LLM:
            completion_args["extra_body"] = {"options": {"num_ctx": 4096}}
        if active_tools:
            completion_args["tools"] = active_tools

        # helper function to stream speech output sentence-by-sentence
        async def stream_final_response(args):
            s_args = dict(args)
            s_args.pop("tools", None)
            s_args["stream"] = True

            stream = await client.chat.completions.create(**s_args)
            buf = ""
            full_text = ""
            first_voice_time = None

            console.print(f"\n[bold plum2][[NAO]]:[/]")

            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    if first_voice_time is None:
                        first_voice_time = time.time() - start_time
                    buf += delta
                    full_text += delta
                    sys.stdout.write(delta)
                    sys.stdout.flush()

                    # check if we have a complete sentence ready to push to tts
                    open_paren = buf.count("(") - buf.count(")")
                    open_slash = buf.count("\\") % 2

                    if open_paren <= 0 and open_slash == 0 and len(buf.strip()) >= 15:
                        match = re.search(r'([.!?]+(?:\s+|$))', buf)
                        if match:
                            end_pos = match.end()
                            sentence = buf[:end_pos].strip()
                            buf = buf[end_pos:]
                            if sentence:
                                queue_push(RESPONSE_FILE, sentence)

            remaining = buf.strip()
            if remaining:
                queue_push(RESPONSE_FILE, remaining)
            queue_push(RESPONSE_FILE, "[END_OF_TURN]")
            sys.stdout.write("\n")
            sys.stdout.flush()

            return full_text, first_voice_time

        # single-stream execution: stream the initial completion directly!
        # if the model emits tool calls, we accumulate them and execute.
        # if the model emits words, sentence 1 is pushed to the tts queue in ~300ms!
        stream_completion_args = dict(completion_args)
        stream_completion_args["stream"] = True

        response_stream = await client.chat.completions.create(**stream_completion_args)

        collected_content = ""
        collected_tool_calls = {}
        t_first_voice = None

        iterations = 0
        total_tools_time = 0
        SILENT_TOOLS = {"save_name", "set_eye_color", "toggle_awareness", "set_posture"}

        buffer = ""
        is_tool_call_turn = False
        printed_header = False

        async for chunk in response_stream:
            delta = chunk.choices[0].delta

            # check for tool calls
            if delta.tool_calls:
                is_tool_call_turn = True
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in collected_tool_calls:
                        collected_tool_calls[idx] = {
                            "id": tc.id or "",
                            "type": "function",
                            "function": {"name": tc.function.name or "", "arguments": tc.function.arguments or ""}
                        }
                    else:
                        if tc.id:
                            collected_tool_calls[idx]["id"] += tc.id
                        if tc.function.name:
                            collected_tool_calls[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            collected_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

            # check for text content
            if delta.content:
                if not printed_header:
                    console.print(f"\n[bold plum2][[NAO]]:[/]")
                    printed_header = True
                if t_first_voice is None:
                    t_first_voice = time.time() - start_time
                delta_text = delta.content
                buffer += delta_text
                collected_content += delta_text
                sys.stdout.write(delta_text)
                sys.stdout.flush()

                # push complete sentences to tts queue immediately for sub-second voice onset
                open_paren = buffer.count("(") - buffer.count(")")
                open_slash = buffer.count("\\") % 2
                if open_paren <= 0 and open_slash == 0 and len(buffer.strip()) >= 15:
                    match = re.search(r'([.!?]+(?:\s+|$))', buffer)
                    if match:
                        end_pos = match.end()
                        sentence = buffer[:end_pos].strip()
                        buffer = buffer[end_pos:]
                        if sentence:
                            queue_push(RESPONSE_FILE, sentence)

        if printed_header:
            remaining = buffer.strip()
            if remaining:
                queue_push(RESPONSE_FILE, remaining)
            queue_push(RESPONSE_FILE, "[END_OF_TURN]")
            sys.stdout.write("\n")
            sys.stdout.flush()

        tool_calls_list = list(collected_tool_calls.values())

        # if no tools were called, this conversation turn is complete!
        if not is_tool_call_turn or not tool_calls_list:
            final_text = collected_content
            total_time = time.time() - start_time

            if t_first_voice is not None:
                console.print(
                    f"  [bright_yellow]-> [Metrics] Total: {total_time:.2f}s | First Voice Out: {t_first_voice:.2f}s (Streamed)[/]"
                )
            else:
                console.print(
                    f"  [bright_yellow]-> [Metrics] Total: {total_time:.2f}s (No Tools)[/]"
                )

            chat_history.append({"role": "assistant", "content": final_text})
            if text.startswith("[SYSTEM EVENT]") and "room is now empty." in text:
                save_history([])
            else:
                save_history(chat_history)

            safe_write(TRANSCRIPTION_FILE, "")
            while safe_read(LISTEN_FILE) != "yes":
                await asyncio.sleep(0.02)
            return

        # otherwise, handle multi-turn tool execution loop
        while is_tool_call_turn and tool_calls_list and iterations < 5:
            assistant_msg = {"role": "assistant"}
            if collected_content:
                assistant_msg["content"] = collected_content
            assistant_msg["tool_calls"] = tool_calls_list

            tool_names = {tc["function"]["name"] for tc in tool_calls_list}
            is_silent_batch = tool_names.issubset(SILENT_TOOLS)
            t_llm1 = time.time() - start_time

            if iterations == 0 and not text.startswith("[SYSTEM EVENT]") and not is_silent_batch:
                filler_phrase = random.choice(FILLER_PHRASES)
                filler = "[INTERMEDIATE] " + filler_phrase
                safe_write(RESPONSE_FILE, filler)

                console.print(f"\n[bold plum2][[NAO]]:[/]")
                wrapped_filler = textwrap.fill(filler_phrase, width=90)
                console.print(f"{wrapped_filler}")
                console.print(f"  [bright_yellow]-> [Metrics] First LLM Response (Filler Sent): {t_llm1:.2f}s[/]\n")

            messages.append(assistant_msg)

            t_tools_start = time.time()

            async def execute_tool(tool_call):
                name = tool_call["function"]["name"]
                tool_id = tool_call["id"]
                
                if name == "take_picture":
                    console.print(f"  [dim white][[SYSTEM: Executing Tool -> take_picture (Native)]][/]")
                    
                    # brief 0.15s buffer to grab the latest camera frame
                    await asyncio.sleep(0.15)
                    
                    frame_path = os.path.join(STATE_DIR, "latest_frame.jpg")
                    
                    if os.path.exists(frame_path):
                        with open(frame_path, "rb") as f:
                            import base64
                            b64_data = base64.b64encode(f.read()).decode("utf-8")
                        
                        return [
                            {"role": "tool", "tool_call_id": tool_id, "name": name, "content": "Camera frame captured successfully."},
                            {
                                "role": "user", 
                                "content": [
                                    {"type": "text", "text": "[System Image Injection] Here is the live view from your camera:"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}", "detail": "low"}}
                                ]
                            }
                        ]
                    else:
                        return [{"role": "tool", "tool_call_id": tool_id, "name": name, "content": "Error: Camera feed is offline."}]

                console.print(f"  [dim white][[SYSTEM: Executing Tool -> {name}]][/]")
                try:
                    args_data = tool_call["function"]["arguments"]
                    if isinstance(args_data, dict):
                        arguments = args_data
                    else:
                        arguments = json.loads(args_data)
                except Exception:
                    arguments = {}

                msgs = []
                texts = []
                images = []

                try:
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
                except Exception as e:
                    texts.append(f"Error executing tool {name}: {str(e)}")

                tool_str = "\n".join(texts) if texts else ""
                if images and not tool_str:
                    tool_str = "Media file processed successfully. The image data has been injected into your vision system in the following message."
                elif not tool_str and not images:
                    tool_str = "Tool executed successfully with no output."

                # tool response message
                msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_id,
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
                *(execute_tool(tc) for tc in tool_calls_list)
            )

            # separate tool role messages from injected user media messages.
            # the openai api strictly requires that all tool messages corresponding
            # to tool_calls appear immediately after the assistant message before any user message.
            pending_tool_msgs = []
            pending_user_msgs = []

            for msgs in tool_messages_lists:
                for m in msgs:
                    if m.get("role") == "tool":
                        pending_tool_msgs.append(m)
                    else:
                        pending_user_msgs.append(m)

            # append all tool responses first, then any image injections
            messages.extend(pending_tool_msgs)
            messages.extend(pending_user_msgs)

            total_tools_time += time.time() - t_tools_start
            iterations += 1

            # check if the model wants another tool call or is ready to synthesize speech
            next_resp = await client.chat.completions.create(**completion_args)
            next_msg = next_resp.choices[0].message
            if next_msg.tool_calls:
                tool_calls_list = [tc.model_dump() for tc in next_msg.tool_calls]
                collected_content = next_msg.content or ""
                is_tool_call_turn = True
            else:
                is_tool_call_turn = False
                tool_calls_list = []

        # stream the final post-tool synthesis so the first sentence speaks immediately!
        final_text, t_first_voice = await stream_final_response(completion_args)

        total_time = time.time() - start_time
        t_final_llm = total_time - t_llm1 - total_tools_time

        if t_first_voice is not None:
            console.print(
                f"  [bright_yellow]-> [Metrics] Total: {total_time:.2f}s (LLM Initial: {t_llm1:.2f}s | Tools: {total_tools_time:.2f}s | LLM Final: {t_final_llm:.2f}s | First Voice Out: {t_first_voice:.2f}s)[/]"
            )
        else:
            console.print(
                f"  [bright_yellow]-> [Metrics] Total: {total_time:.2f}s (LLM Initial: {t_llm1:.2f}s | Tools: {total_tools_time:.2f}s | LLM Final: {t_final_llm:.2f}s)[/]"
            )

        # save history
        chat_history.append({"role": "assistant", "content": final_text})
        
        # only wipe context clean when the room is completely empty, not when one of multiple people leaves
        if text.startswith("[SYSTEM EVENT]") and "room is now empty." in text:
            save_history([])
        else:
            save_history(chat_history)

        # clear transcription queue
        safe_write(TRANSCRIPTION_FILE, "")

        while safe_read(LISTEN_FILE) != "yes":
            await asyncio.sleep(0.02)

    except Exception as e:
        console.print(f"[bold red][[ OpenAI API Error: {e} ]][/]")
        safe_write(TRANSCRIPTION_FILE, "")
        safe_write(LISTEN_FILE, "yes")


async def main():
    if not USE_LOCAL_LLM and not OPENAI_API_KEY:
        console.print("[bold red][[ Error: OPENAI_API_KEY environment variable not set! ]][/]")
        return

    init_files()

    async with AsyncExitStack() as stack:
        try:
            console.print("[dim white][[ SYSTEM: Connecting to MCP servers... ]][/]")
            mcp_config_path = os.path.join(BASE_DIR, "mcp_config.json")
            tools_list, tool_router = await load_and_register_mcp_servers(
                stack, mcp_config_path
            )

            console.print("[dim white][[ SYSTEM: MCP tools ready. ]][/]")
            safe_write(LISTEN_FILE, "yes")
        except Exception as e:
            console.print(f"[bold red][[ Error initializing MCP: {e} ]][/]")
            tools_list = []
            tool_router = {}
            safe_write(LISTEN_FILE, "yes")

        try:
            while True:
                event_text = safe_read(EVENTS_FILE)
                if event_text:
                    safe_write(EVENTS_FILE, "")
                    await process_chat_turn(event_text, tools_list, tool_router)
                    continue

                text = safe_read(TRANSCRIPTION_FILE)
                if text:
                    await process_chat_turn(text, tools_list, tool_router)

                await asyncio.sleep(0.02)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    asyncio.run(main())
