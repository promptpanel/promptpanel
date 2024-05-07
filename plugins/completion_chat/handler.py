import os
import logging
import litellm
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse
from unstructured.partition.auto import partition
from openai import OpenAI
from jinja2 import Template

logger = logging.getLogger("app")


# File Entrypoint
def file_handler(file, thread, panel):
    try:
        return StreamingHttpResponse(
            file_stream(file, thread, panel), content_type="text/plain"
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


def file_stream(file, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Parse file and save to .txt file.
    ## 3. Enrich file metadata with token_count.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        completion_model = settings.get("Model")

        ## ----- 2. Parse file and save to .txt file.
        logger.info("** 2. Parse file and save to .txt file.")
        yield "Parsing file to text..."
        elements = partition(filename=file.filepath, strategy="fast")
        output_filepath = file.filepath + ".txt"
        with open(output_filepath, "w", encoding="utf-8") as output_file:
            for element in elements:
                output_file.write(str(element) + "\n")

        ## ----- 3. Enrich file metadata with token_count / text_file_path.
        logger.info("** 2. Enrich file metadata with token_count / text_file_path.")
        yield "Counting tokens..."
        with open(output_filepath, "r", encoding="utf-8") as input_file:
            output_text = input_file.read()
        output_text_formatted = f"{file.filename} Context:\n {output_text} \n\n"
        new_file = [{"role": "user", "content": output_text_formatted}]
        token_count = litellm.token_counter(model=completion_model, messages=new_file)
        file.meta.update(
            {"token_count": token_count, "text_file_path": output_filepath}
        )
        file.save()
        yield "File upload and parsing complete..."

    except Exception as e:
        logger.info("** Upload failed")
        yield "File upload and parsing failed..."
        file.delete()
        logger.error(e, exc_info=True)


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
    ## 3. Get max context and system message.
    ## 4. Build document context.
    ## 5. Build message history.
    ## 6. Execute chat.
    ## 7. Save warnings as needed.
    ## 8. Cleanup message text, enrich with token count, and save.
    ## 9. Enrich / append a title to the chat.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]

        ## ----- 2. Enrich incoming message with token_count.
        logger.info("** 2. Enrich incoming message with token_count.")
        completion_model = settings.get("Model")
        token_count = litellm.token_counter(
            model=completion_model,
            messages=[{"role": "user", "content": message.content}],
        )
        message.meta.update({"token_count": token_count})
        message.save()

        ## ----- 3. Get max context and system message.
        max_tokens = int(settings.get("Context Size"))
        system_message = settings.get("System Message", "")
        system_message_token_count = litellm.token_counter(
            model=completion_model,
            messages=[{"role": "system", "content": system_message}],
        )
        prompt_template = settings.get("Prompt Template", "")
        prompt_template_token_count = litellm.token_counter(
            model=completion_model,
            messages=[{"role": "user", "content": prompt_template}],
        )
        if settings.get("Max Tokens to Generate") is not None:
            remaining_tokens = (
                max_tokens
                - system_message_token_count
                - prompt_template_token_count
                - int(settings.get("Max Tokens to Generate"))
            )
        else:
            remaining_tokens = (
                max_tokens - prompt_template_token_count - system_message_token_count
            )

        ## ----- 4. Build document context.
        logger.info("** 4. Build document context.")
        # Allow 80% of context to be filled
        doc_token_limit = remaining_tokens * 0.8
        doc_current_tokens = 0
        doc_context = ""
        skipped_docs = False
        thread_files = File.objects.filter(thread=thread, meta__enabled=True)
        if thread_files.exists():
            for file in thread_files:
                doc_token_count = file.meta.get("token_count", 0)
                if doc_current_tokens + doc_token_count <= doc_token_limit:
                    doc_current_tokens += doc_token_count
                    doc_file_path = file.meta.get("text_file_path", "")
                    try:
                        if os.path.exists(doc_file_path):
                            with open(doc_file_path, "r") as f:
                                doc_text = f.read()
                            doc_context += f"{file.filename} Context:\n{doc_text}\n\n"
                    except Exception as e:
                        logger.error(e, exc_info=True)
                else:
                    skipped_docs = True
                    break
            document_context = {
                "role": "user",
                "content": doc_context,
            }
            # Set tokens after adding docs
            remaining_tokens = remaining_tokens - doc_current_tokens

        ## ----- 5. Build message history.
        logger.info("** 5. Build message history.")
        messages = Message.objects.filter(
            created_by=message.created_by, thread_id=thread.id
        ).order_by("-created_on")
        message_history = []
        message_history_token_count = 0
        user_message_count = 0
        for msg in messages:
            if (
                msg.meta.get("token_count", 0) + message_history_token_count
                <= remaining_tokens
            ):
                # Container for message
                skipped_images = False
                if msg.meta.get("images"):
                    skipped_images = True
                # Append if user or assistant
                role = msg.meta.get("sender", "user")
                message_history_token_count += msg.meta.get("token_count", 0)
                if role == "user":
                    user_message_count = user_message_count + 1
                    message_history.append({"role": "user", "content": msg.content})
                if role == "assistant":
                    message_history.append(
                        {"role": "assistant", "content": msg.content}
                    )
            else:
                break
        if thread_files.exists():
            message_history.append(document_context)
        message_history.reverse()
        # Create chat template
        message_context = {
            "system_message": system_message,
            "message_history": message_history,
        }
        template = Template(prompt_template, trim_blocks=True, lstrip_blocks=True)
        message_prepped = template.render(message_context)

        ## ----- 6. Execute chat.
        logger.info("** 6. Execute chat.")
        logger.info("Message history: " + str(message_history))
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
        response_display = ""
        if skipped_images:
            response_display += "> Vision is not available with this model.\n\n"
        if skipped_docs:
            response_display += "> Some of your documents exceeded the context window (text size) for your AI. We recommend using a retrieval-augmented generation (RAG) based solution to surface only the relevant information when querying your AI.\n\n"
        for part in openai_client.completions.create(**completion_settings_trimmed):
            try:
                delta = part.choices[0].text or ""
                response_content += delta
                response_display += delta
                yield response_display
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass
        logger.info("response_content: " + str(response_content))

        ## ----- 7. Save warnings as needed.
        logger.info("** 7. Save warnings as needed.")
        if skipped_docs:
            warning_docs = Message(
                content="Some of your documents exceeded the context window (text size) for your AI. We recommend using a retrieval-augmented generation (RAG) based solution to surface only the relevant information when querying your AI.",
                thread=thread,
                panel=panel,
                created_by=message.created_by,
                meta={"sender": "warning"},
            )
            warning_docs.save()
        if skipped_images:
            warning_images = Message(
                content="Vision is not available with this model.",
                thread=thread,
                panel=panel,
                created_by=message.created_by,
                meta={"sender": "warning"},
            )
            warning_images.save()

        ## ----- 8. Cleanup message text, enrich with token count, and save.
        logger.info("** 8. Cleanup message text, enrich with token count, and save.")
        # Cleanup
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

        # Save message
        new_message = [{"role": "assistant", "content": response_content}]
        token_count = litellm.token_counter(
            model=completion_model, messages=new_message
        )
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "assistant", "token_count": token_count},
        )
        response_message.save()

        ## ----- 9. Enrich / append a title to the chat.
        logger.info("** 9. Enrich / append a title to the chat")
        if user_message_count == 1:
            title_enrich = (
                "## Context: "
                + "You are an assistant who writes titles based on questions which are asked by the user. Please only provide a summary, do not provide the answer to the question."
                + "\n"
                + "Please create a title for the following content: "
                + "\n"
                + message.content
                + "\n\n"
                + "Title: "
            )
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
            meta={"sender": "error"},
        )
        response_message.save()
