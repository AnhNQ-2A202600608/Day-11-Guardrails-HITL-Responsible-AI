"""
Lab 11 — Helper Utilities
"""
from google.genai import types


import asyncio
import time
from google.genai.errors import ClientError, ServerError

async def chat_with_agent(agent, runner, user_message: str, session_id=None):
    """Send a message to the agent and get the response.

    Args:
        agent: The LlmAgent instance
        runner: The InMemoryRunner instance
        user_message: Plain text message to send
        session_id: Optional session ID to continue a conversation

    Returns:
        Tuple of (response_text, session)
    """
    user_id = "student"
    app_name = runner.app_name

    session = None
    if session_id is not None:
        try:
            session = await runner.session_service.get_session(
                app_name=app_name, user_id=user_id, session_id=session_id
            )
        except (ValueError, KeyError):
            pass

    if session is None:
        try:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )
        except Exception:
            session = await runner.session_service.create_session(
                app_name=app_name, user_id=user_id
            )

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_message)],
    )

    for attempt in range(6):
        try:
            final_response = ""
            async for event in runner.run_async(
                user_id=user_id, session_id=session.id, new_message=content
            ):
                if hasattr(event, "content") and event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            final_response += part.text
            return final_response, session
        except (ClientError, ServerError) as e:
            status_code = getattr(e, "code", None)
            if status_code in [429, 503] or any(err in str(e) for err in ["429", "503"]):
                wait_time = 65 if status_code == 429 or "429" in str(e) else 10 + attempt * 5
                print(f"Temporary API error {status_code or 'UNKNOWN'}. Waiting {wait_time}s before retrying...")
                await asyncio.sleep(wait_time)
            else:
                raise e
        except Exception as e:
            if any(err in str(e) for err in ["429", "503"]):
                wait_time = 65 if "429" in str(e) else 10 + attempt * 5
                print(f"Temporary API error. Waiting {wait_time}s before retrying...")
                await asyncio.sleep(wait_time)
            else:
                raise e

    raise Exception("Failed to call agent due to persistent temporary rate limits/server errors")


async def generate_content_with_retry(client, model, contents, config=None):
    """Call generate_content with exponential backoff on 429/503 limits."""
    for attempt in range(6):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            return response
        except (ClientError, ServerError) as e:
            status_code = getattr(e, "code", None)
            if status_code in [429, 503] or any(err in str(e) for err in ["429", "503"]):
                wait_time = 65 if status_code == 429 or "429" in str(e) else 10 + attempt * 5
                print(f"Temporary generate_content error {status_code or 'UNKNOWN'}. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise e
        except Exception as e:
            if any(err in str(e) for err in ["429", "503"]):
                wait_time = 65 if "429" in str(e) else 10 + attempt * 5
                print(f"Temporary generate_content error. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise e
    raise Exception("Failed to call generate_content due to persistent temporary rate limits/server errors")
