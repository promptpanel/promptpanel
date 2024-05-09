import os
import logging
import litellm
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse
from unstructured.partition.auto import partition

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
        model_selected = settings.get("Model", "Haiku")
        if model_selected == "Opus":
            completion_model = "claude-3-opus-20240229"
        elif model_selected == "Sonnet":
            completion_model = "claude-3-sonnet-20240229"
        else:
            completion_model = "claude-3-haiku-20240307"

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
        model_selected = settings.get("Model", "Haiku")
        if model_selected == "Opus":
            completion_model = "claude-3-opus-20240229"
        elif model_selected == "Sonnet":
            completion_model = "claude-3-sonnet-20240229"
        else:
            completion_model = "claude-3-haiku-20240307"

        token_count = litellm.token_counter(
            model=completion_model,
            messages=[{"role": "user", "content": message.content}],
        )
        message.meta.update({"token_count": token_count})
        message.save()

        ## ----- 3. Get max context and system message.
        max_tokens = 200000
        system_message = {
            "role": "system",
            "content": settings.get("System Message", ""),
        }
        system_message_token_count = litellm.token_counter(
            model=completion_model, messages=[system_message]
        )
        remaining_tokens = max_tokens - system_message_token_count

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
                "content": [{"type": "text", "text": doc_context}],
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
                role = msg.meta.get("sender", "user")
                if role == "user":
                    # Increment if role user (for title later)
                    user_message_count = user_message_count + 1
                    message_history_token_count += msg.meta.get("token_count", 0)
                    message_history.append(
                        {
                            "role": "user",
                            "content": msg.content,
                        }
                    )
                if role == "assistant":
                    message_history_token_count += msg.meta.get("token_count", 0)
                    message_history.append(
                        {
                            "role": "assistant",
                            "content": msg.content,
                        }
                    )
            else:
                break
        if thread_files.exists():
            message_history.append(document_context)
        message_history.append(system_message)
        message_history.reverse()

        ## ----- 6. Execute chat.
        logger.info("** 6. Execute chat.")
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
        if skipped_images:
            yield "> Vision is not available with this model.\n\n"
        if skipped_docs:
            yield "> Some of your documents exceeded the context window (text size) for your AI. We recommend using a retrieval-augmented generation (RAG) based solution to surface only the relevant information when querying your AI.\n\n"
        for part in response:
            try:
                delta = part.choices[0].delta.content or ""
                response_content += delta
                yield delta
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass

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
            title_enrich = []
            title_enrich.append(
                {
                    "role": "system",
                    "content": "You are an assistant who writes titles based on questions which are asked by the user. Please only provide a summary, do not provide the answer to the question.",
                }
            )
            title_enrich.append(
                {
                    "role": "user",
                    "content": f"Please create a title for the following content: {message.content} \n\n Title:",
                }
            )
            title_settings = {
                "stream": False,
                "model": "claude-3-haiku-20240307",
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
            meta={"sender": "error"},
        )
        response_message.save()
