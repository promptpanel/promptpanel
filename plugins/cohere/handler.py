import json
import logging
import re
import requests
import litellm
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse

logger = logging.getLogger("app")


# File Entrypoint
def file_handler(file, thread, panel):
    ## Function:
    ## 1. Unused, we'll provide a message and an error state if the upload endpoint fails.

    try:
        return JsonResponse(
            {
                "status": "success",
                "message": "File upload is not enabled for this plugin.",
            },
            status=200,
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


# Message Entrypoint
def message_handler(message, thread, panel):
    try:
        return StreamingHttpResponse(
            chat_stream(message, thread, panel), content_type="text/plain"
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


def chat_stream(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Enrich incoming message with token_count.
    ## 3. Build message history.
    ## 4. Execute chat in a StreamingHttpResponse.
    ## 5. Enrich response message with token_count.
    ## 6. Enrich / append a title to the chat.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Preparing settings")
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]

        ## ----- 2. Enrich incoming message with token_count.
        logger.info("** 2. Enriching incoming message with token_count")
        model_selected = settings.get("Model", "command-r")
        if model_selected == "Command R+":
            completion_model = "command-r-plus"
        else:
            completion_model = "command-r"

        new_message = [{"role": "user", "content": message.content}]
        token_count = litellm.token_counter(
            model=completion_model, messages=new_message
        )
        new_metadata = dict(message.meta)
        new_metadata["token_count"] = token_count
        message.meta = new_metadata
        message.save()

        ## ----- 3. Build message history.
        logger.info("** 3. Building message history")
        system_message = [
            {"role": "system", "content": settings.get("System Message", "")}
        ]
        system_message_token_count = litellm.token_counter(
            model=completion_model, messages=system_message
        )

        # Get remaining tokens
        remaining_tokens = 128000 - system_message_token_count

        # Get Message History
        messages = Message.objects.filter(
            created_by=message.created_by, thread_id=thread.id
        ).order_by("-created_on")
        message_history = []
        message_history_token_count = 0
        user_message_count = 0

        # Prep chat
        for msg in messages:
            if (
                msg.meta.get("token_count", 0) + message_history_token_count
                <= remaining_tokens
            ):
                if msg.meta.get("sender", "user") == "user":
                    user_message_count = user_message_count + 1
                    message_history.append({"role": "user", "content": msg.content})
                if msg.meta.get("sender", "user") == "assistant":
                    message_history.append(
                        {"role": "assistant", "content": msg.content}
                    )
                message_history_token_count += msg.meta.get("token_count", 0)
            else:
                break
        message_history.extend(system_message)
        message_history.reverse()

        ## ----- 4. Execute chat in a StreamingHttpResponse.
        logger.info("** 4. Sending message")
        logger.info("Message history: " + str(message_history))
        # Preparing completion settings for call
        completion_settings = {
            "stream": True,
            "model": completion_model,
            "messages": message_history,
            "api_key": settings.get("API Key"),
        }
        litellm.drop_params = True
        completion_settings_trimmed = {
            key: value
            for key, value in completion_settings.items()
            if value is not None
        }
        response = litellm.completion(**completion_settings_trimmed)
        response_content = ""
        for part in response:
            try:
                delta = part.choices[0].delta.content or ""
                response_content += delta
                yield delta
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass
        # Clean hanging sentences
        last_period_pos = response_content.rfind(".")
        last_question_mark_pos = response_content.rfind("?")
        last_exclamation_mark_pos = response_content.rfind("!")
        last_quote_period_pos = response_content.rfind('."')
        last_quote_question_mark_pos = response_content.rfind('?"')
        last_quote_exclamation_mark_pos = response_content.rfind('!"')
        last_sentence_end_pos = max(
            last_period_pos,
            last_question_mark_pos,
            last_exclamation_mark_pos,
            last_quote_period_pos,
            last_quote_question_mark_pos,
            last_quote_exclamation_mark_pos,
        )
        if last_sentence_end_pos != -1:
            response_content = response_content[: last_sentence_end_pos + 1]

        ## ----- 5. Enrich response message with token_count.
        logger.info("** 5. Encoding response")
        new_message = [{"role": "assistant", "content": response_content}]
        token_count = litellm.token_counter(
            model=completion_model, messages=new_message
        )
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            metadata={"sender": "assistant", "token_count": token_count},
        )
        response_message.save()

        ## ----- 6. Enrich / append a title to the chat.
        # Only add title if first message (+ system message) in history
        logger.info("** 6. Enriching and appending title")
        if user_message_count == 1:
            title_enrich = []
            title_enrich.append(
                {
                    "role": "system",
                    "content": "You are a bot which condenses text into a succinct and informative title. Please only provide a summary, do not provide the answer to the question.",
                }
            )
            title_enrich.append({"role": "user", "content": message.content})
            title_settings = {
                "stream": False,
                "model": "command-r",
                "messages": title_enrich,
                "api_key": settings.get("API Key"),
                "max_tokens": 34,
            }
            litellm.drop_params = True
            title_settings_trimmed = {
                key: value for key, value in title_settings.items() if value is not None
            }
            response = litellm.completion(**title_settings_trimmed)
            thread.title = response.choices[0].message.content.strip(
                '"\n'
            )  # Clean extra quotes
            thread.save()
    except Exception as e:
        logger.error(e, exc_info=True)
        yield "Error: " + str(e)
        # Save error as message
        response_message = Message(
            content="Error: " + str(e),
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            metadata={"sender": "error"},
        )
        response_message.save()
