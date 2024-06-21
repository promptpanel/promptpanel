import os
import json
import logging
import litellm
import re
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse
from unstructured.partition.auto import partition

logger = logging.getLogger("app")


# File Entrypoint
def file_handler(file, thread, panel):
    try:
        response = StreamingHttpResponse(
            streaming_content=file_stream(file, thread, panel),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


def file_stream(file, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Parse file and save to .txt file.
    ## 3. Enrich file metadata with token_count.
    ## 4. Add file upload message / hinting for usage.

    try:
        yield "Processing"
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        model_selected = settings.get("Model", "Haiku")
        completion_model = model_selected
        max_tokens = 8192
        if model_selected == "Sonnet 3.5":
            completion_model = "claude-3-5-sonnet-20240620"
            max_tokens = 200000
        if model_selected == "Opus":
            completion_model = "claude-3-opus-20240229"
            max_tokens = 200000
        if model_selected == "Sonnet":
            completion_model = "claude-3-sonnet-20240229"
            max_tokens = 200000
        if model_selected == "Haiku":
            completion_model = "claude-3-haiku-20240307"
            max_tokens = 200000

        ## ----- 2. Parse file and save to .txt file.
        logger.info("** 2. Parse file and save to .txt file.")
        elements = partition(filename=file.filepath, strategy="fast")
        output_filepath = file.filepath + ".txt"
        with open(output_filepath, "w", encoding="utf-8") as output_file:
            for element in elements:
                output_file.write(str(element) + "\n")

        ## ----- 3. Enrich file metadata with token_count / text_file_path.
        logger.info("** 3. Enrich file metadata with token_count / text_file_path.")
        with open(output_filepath, "r", encoding="utf-8") as input_file:
            output_text = input_file.read()
        output_text_formatted = f"{file.filename} Context:\n {output_text} \n\n"
        new_file = [{"role": "user", "content": output_text_formatted}]
        token_count = litellm.token_counter(model=completion_model, messages=new_file)
        file.meta.update(
            {
                "enabled": True,
                "upload_status": "success",
                "token_count": token_count,
                "text_file_path": output_filepath,
            }
        )
        file.save()
        ## ----- 4. Add file upload message / hinting for usage.
        logger.info("** 3. Add file upload message / hinting for usage.")
        file_message_content = f"File uploaded successfully.\n To append the file to your message send `/append /file {file.filename} [message*]`"
        file_message = Message(
            content=file_message_content,
            thread=thread,
            panel=panel,
            created_by=file.created_by,
            meta={
                "sender": "info",
                "prompt": f"/append /file {file.filename} [message*]",
            },
        )
        file_message.save()
        yield "Completed"
    except Exception as e:
        logger.info("** Upload failed:" + str(e))
        logger.error(e, exc_info=True)
        file.meta.update(
            {"enabled": False, "upload_status": "failed", "fail_reason": str(e)}
        )
        file.save()
        yield "Error"


# Message Entrypoint
def message_handler(message, thread, panel):
    try:
        ## Function:
        ## 1. Routing to messaging functions.
        logger.info("** 1. Routing to messaging functions.")
        if message.content.startswith("/append"):
            response = StreamingHttpResponse(
                streaming_content=message_append(message, thread, panel),
                content_type="text/event-stream",
            )
        else:
            response = StreamingHttpResponse(
                streaming_content=chat_stream(message, thread, panel),
                content_type="text/event-stream",
            )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


def message_append(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Get max context and system message.
    ## 3. Build message history.
    ## 3.1 Get appended file(s).
    ## 4. Execute chat.
    ## 5. Cleanup message text, and save.
    ## 6. Save warnings as needed.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get files to append and settings.")
        ## Save message as a command
        message.meta["sender"] = "user_command"
        message.save()
        ## Parse incoming command
        filename_pattern = r"/file\s+(\S+)"
        command_pattern = r"^/append\s+(?:/file\s+\S+\s+)*(.*)"
        filenames_find = re.findall(filename_pattern, message.content)
        command_message_match = re.match(command_pattern, message.content)
        command_message = (
            command_message_match.group(1).strip() if command_message_match else ""
        )
        command_filenames = [
            filename.strip() for filename in filenames_find if filename.strip()
        ]
        logger.info("Command message: " + command_message)
        logger.info("Command filenames: " + str(command_filenames))
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]
        model_selected = settings.get("Model", "Haiku")
        completion_model = model_selected
        max_tokens = 8192
        if model_selected == "Sonnet 3.5":
            completion_model = "claude-3-5-sonnet-20240620"
            max_tokens = 200000
        if model_selected == "Opus":
            completion_model = "claude-3-opus-20240229"
            max_tokens = 200000
        if model_selected == "Sonnet":
            completion_model = "claude-3-sonnet-20240229"
            max_tokens = 200000
        if model_selected == "Haiku":
            completion_model = "claude-3-haiku-20240307"
            max_tokens = 200000

        ## ----- 2. Get max context and system message.
        logger.info("** 2. Get max context and system message.")
        system_message = {
            "role": "system",
            "content": settings.get("System Message", ""),
        }
        system_message_token_count = litellm.token_counter(
            model=completion_model, messages=[system_message]
        )
        if settings.get("Max Tokens to Generate") is not None:
            remaining_tokens = (
                max_tokens
                - system_message_token_count
                - int(settings.get("Max Tokens to Generate"))
            )
        else:
            remaining_tokens = max_tokens - system_message_token_count

        ## ----- 3. Build message history.
        logger.info("** 3. Build message history.")
        messages = Message.objects.filter(
            created_by=message.created_by, thread_id=thread.id
        ).order_by("-created_on")
        message_history = []
        message_history_token_count = 0

        # > Current message
        current_content_row = {"role": "user", "content": command_message}
        current_token_count = litellm.token_counter(
            model=completion_model, messages=[current_content_row]
        )
        message_history_token_count += current_token_count
        message_history.append(current_content_row)

        ## ----- 3.1 Get files + append to history.
        logger.info("** 3. Get files + append to history.")
        file_appended_text = ""
        file_context_size_warn = False
        for filename in command_filenames:
            file_obj = File.objects.filter(
                filename=filename, thread_id=thread.id
            ).first()
            filepath = file_obj.meta.get("text_file_path", "")
            logger.info("Filepath: " + filepath)
            if filepath:
                with open(filepath, "r", encoding="utf-8") as f:
                    file_content = f.read()
                file_tokens_count = litellm.token_counter(
                    model=completion_model,
                    messages=[
                        {
                            "role": "user",
                            "content": "Document Context:\n" + file_content,
                        }
                    ],
                )
                if file_tokens_count + message_history_token_count < remaining_tokens:
                    message_history_token_count += file_tokens_count
                    file_appended_text += file_content + "\n"
                else:
                    logger.info("File context warning triggered. Skipping...")
                    file_context_size_warn = True
                    pass
            else:
                logger.info("Text filepath not found in metadata. Skipping...")
        logger.info("Appended Content: " + file_appended_text)
        file_content_row = {
            "role": "user",
            "content": "Document Context:\n" + file_content,
        }
        message_history.append(file_content_row)

        # Append previous messages
        for msg in messages:
            role = msg.meta.get("sender", "user")
            if role == "user" or role == "assistant":
                msg_content_row = {"role": role, "content": msg.content}
                msg_token_count = litellm.token_counter(
                    model=completion_model, messages=[msg_content_row]
                )
                if msg_token_count + message_history_token_count <= remaining_tokens:
                    message_history_token_count += msg_token_count
                    message_history.append(msg_content_row)
                else:
                    break
        message_history.append(system_message)
        message_history.reverse()

        ## ----- 4. Execute chat.
        logger.info("** 4. Execute chat.")
        logger.info("Message history: " + str(message_history))
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

        ## ----- 5. Cleanup message text, and save.
        logger.info("** 5. Cleanup message text, and save.")
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
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "assistant"},
        )
        response_message.save()

        ## ----- 6. Save warnings as needed.
        logger.info("** 6. Save warnings as needed.")
        if file_context_size_warn:
            warning_docs = Message(
                content="Some of your documents exceeded the context window (text size). We recommend using a retrieval-augmented generation (RAG) based solution [such as the `Document Lookup` plugin] to surface only the relevant information when querying your AI.",
                thread=thread,
                panel=panel,
                created_by=message.created_by,
                meta={"sender": "warning"},
            )
            warning_docs.save()

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


def chat_stream(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Get max context and system message.
    ## 3. Build message history.
    ## 4. Execute chat.
    ## 5. Cleanup message text, and save.
    ## 6. Save warnings as needed
    ## 7. Enrich / append a title to the chat.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]
        model_selected = settings.get("Model", "Haiku")
        completion_model = model_selected
        max_tokens = 8192
        if model_selected == "Sonnet 3.5":
            completion_model = "claude-3-5-sonnet-20240620"
            max_tokens = 200000
        if model_selected == "Opus":
            completion_model = "claude-3-opus-20240229"
            max_tokens = 200000
        if model_selected == "Sonnet":
            completion_model = "claude-3-sonnet-20240229"
            max_tokens = 200000
        if model_selected == "Haiku":
            completion_model = "claude-3-haiku-20240307"
            max_tokens = 200000

        ## ----- 2. Get max context and system message.
        logger.info("** 2. Get max context and system message.")
        system_message = {
            "role": "system",
            "content": settings.get("System Message", ""),
        }
        system_message_token_count = litellm.token_counter(
            model=completion_model, messages=[system_message]
        )
        if settings.get("Max Tokens to Generate") is not None:
            remaining_tokens = (
                max_tokens
                - system_message_token_count
                - int(settings.get("Max Tokens to Generate"))
            )
        else:
            remaining_tokens = max_tokens - system_message_token_count

        ## ----- 3. Build message history.
        logger.info("** 3. Build message history.")
        messages = Message.objects.filter(
            created_by=message.created_by, thread_id=thread.id
        ).order_by("-created_on")
        message_history = []
        message_history_token_count = 0
        for msg in messages:
            role = msg.meta.get("sender", "user")
            if role == "user" or role == "assistant":
                msg_content_row = {"role": role, "content": msg.content}
                msg_token_count = litellm.token_counter(
                    model=completion_model, messages=[msg_content_row]
                )
                if msg_token_count + message_history_token_count <= remaining_tokens:
                    message_history_token_count += msg_token_count
                    message_history.append(msg_content_row)
                else:
                    break
        message_history.append(system_message)
        message_history.reverse()

        ## ----- 4. Execute chat.
        logger.info("** 4. Execute chat.")
        logger.info("Message history: " + str(message_history))
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

        ## ----- 5. Cleanup message text, and save.
        logger.info("** 5. Cleanup message text, and save.")
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
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "assistant"},
        )
        response_message.save()

        ## ----- 6. Save warnings as needed.
        logger.info("** 6. Save warnings as needed.")

        ## ----- 7. Enrich / append a title to the chat.
        logger.info("** 7. Enrich / append a title to the chat")
        if thread.title == "New Thread":
            title_enrich = []
            title_content = """
You are an assistant who writes informative titles based on questions which are asked by the user. 
Please only provide a summary, do not provide the answer to the question.
Examples:
```
Solution to the fizz buzz problem.
Winner of the 1998 NBA Finals.
Ordering food in Japanese.
```
            """.strip()
            title_enrich.append({"role": "system", "content": title_content})
            title_enrich.append(
                {
                    "role": "user",
                    "content": f"Please create a title for the following content: {message.content}",
                }
            )
            title_settings = {
                "stream": False,
                "model": completion_model,
                "messages": title_enrich,
                "api_key": settings.get("API Key"),
                "api_base": (
                    settings.get("URL Base", "").rstrip("/")
                    if settings.get("URL Base") is not None
                    else None
                ),
                "api_version": settings.get("API Version"),
                "organization": settings.get("Organization ID"),
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
            meta={"sender": "error"},
        )
        response_message.save()
