import json
import logging
import re
import requests
import litellm
from django.http import JsonResponse, StreamingHttpResponse
from jinja2 import Template
from panel.models import File, Message, Panel, Thread
from openai import OpenAI

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
        if settings.get("Token Counter") == "openai":
            completion_model = "gpt-3.5-turbo"
        else:
            completion_model = "huggingface/meta-llama/Llama-2-7b"
        token_count = len(litellm.encode(model=completion_model, text=message.content))
        new_metadata = dict(message.meta)
        new_metadata["token_count"] = token_count
        message.meta = new_metadata
        message.save()

        ## ----- 3. Build message history.
        logger.info("** 3. Building message history")
        system_message = settings.get("System Message")
        system_message_token_count = len(
            litellm.encode(model=completion_model, text=system_message)
        )

        # Load jinja template for prompt
        prompt_template = settings.get("Prompt Template")
        prompt_template_token_count = len(
            litellm.encode(model=completion_model, text=prompt_template)
        )

        # Get remaining tokens
        if settings.get("Max Tokens to Generate") is not None:
            remaining_tokens = (
                int(settings.get("Context Size"))
                - prompt_template_token_count
                - system_message_token_count
                - int(settings.get("Max Tokens to Generate"))
            )
        else:
            remaining_tokens = (
                int(settings.get("Context Size"))
                - prompt_template_token_count
                - system_message_token_count
            )

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
        message_history.reverse()
        logger.info("Message history: " + str(message_history))

        # Create chat
        message_context = {
            "system_message": system_message,
            "message_history": message_history,
        }
        template = Template(prompt_template, trim_blocks=True, lstrip_blocks=True)
        message_prepped = template.render(message_context)

        ## ----- 4. Execute chat in a StreamingHttpResponse.
        logger.info("** 4. Sending message")
        logger.info("Message history: " + str(message_prepped))
        client_settings = {
            "api_key": settings.get("API Key"),
            "base_url": (
                settings.get("URL Base", "").rstrip("/")
                if settings.get("URL Base") is not None
                else None
            ),
            "organization": settings.get("Organization ID"),
        }
        client_settings_trimmed = {
            key: value for key, value in client_settings.items() if value is not None
        }
        openai_client = OpenAI(**client_settings_trimmed)
        completion_settings = {
            "stream": True,
            "model": settings.get("Model"),
            "prompt": message_prepped,
            "stop": settings.get("Stop Sequence"),
            "temperature": (
                float(settings.get("Temperature"))
                if settings.get("Temperature") is not None
                else None
            ),
            "max_tokens": (
                int(settings.get("Max Tokens to Generate"))
                if settings.get("Max Tokens to Generate") is not None
                else None
            ),
            "top_p": (
                float(settings.get("Top P"))
                if settings.get("Top P") is not None
                else None
            ),
            "presence_penalty": (
                float(settings.get("Presence Penalty"))
                if settings.get("Presence Penalty") is not None
                else None
            ),
            "frequency_penalty": (
                float(settings.get("Frequency Penalty"))
                if settings.get("Frequency Penalty") is not None
                else None
            ),
        }
        completion_settings_trimmed = {
            key: value
            for key, value in completion_settings.items()
            if value is not None
        }
        response_content = ""
        for part in openai_client.completions.create(**completion_settings_trimmed):
            try:
                delta = part.choices[0].text or ""
                response_content += delta
                yield delta
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass
        logger.info("response_content: " + str(response_content))
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
        if settings.get("Token Counter") == "openai":
            completion_model = "gpt-3.5-turbo"
        else:
            completion_model = "huggingface/meta-llama/Llama-2-7b"
        token_count = len(litellm.encode(model=completion_model, text=response_content))
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
            title_enrich = (
                "## Context: "
                + "You are a bot which condenses text into a succinct and informative title. Please only provide a summary title, do not provide the answer to the question."
                + "\n"
                + "## To summarize: "
                + message.content
                + "\n"
            )
            logger.info("title_enrich: " + str(title_enrich))
            title_settings = {
                "stream": False,
                "model": settings.get("Model"),
                "prompt": title_enrich,
            }
            title_settings_trimmed = {
                key: value for key, value in title_settings.items() if value is not None
            }
            response = openai_client.completions.create(**title_settings_trimmed)
            thread.title = response.choices[0].text.strip('"\n')  # Clean extra quotes
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
