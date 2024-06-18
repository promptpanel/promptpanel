import logging
import litellm
import pickle
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
    ## 1. Parse file and save page content as chunks.
    ## 2. Add file upload message / hinting for usage.
    try:
        yield "Processing"
        ## ----- 1. Parse file and save page content as chunks.
        logger.info("** 1. Parse file and save page content as chunks.")
        elements = partition(filename=file.filepath, chunking_strategy="by_title")
        sentences = []
        page_numbers = []
        for el in elements:
            if str(el):
                sentences.append(str(el))
                if el.metadata.page_number:
                    page_numbers.append(el.metadata.page_number)
                else:
                    page_numbers.append(1)
        pickle_path = f"{file.filepath}.pkl"
        pickle_data = (sentences, page_numbers)
        with open(pickle_path, "wb") as f:
            pickle.dump(pickle_data, f)
        file.meta.update({"enabled": True, "pickle_file_path": pickle_path})
        file.save()
        ## ----- 2. Add file upload message / hinting for usage.
        logger.info("** 2. Add file upload message / hinting for usage.")
        file_message_content = f"File uploaded successfully.\n To summarize, message `/summarize /file {file.filename} [question]`"
        file_message = Message(
            content=file_message_content,
            thread=thread,
            panel=panel,
            created_by=file.created_by,
            meta={
                "sender": "info",
                "prompt": f"/summarize /file {file.filename} [question]",
            },
        )
        file_message.save()
        yield "Completed"
    except Exception as e:
        logger.info("** Upload failed")
        yield "File upload and parsing failed..."
        file.delete()
        logger.error(e, exc_info=True)
        yield "Error"


# Message Entrypoint
def message_handler(message, thread, panel):
    try:
        ## Function:
        ## 1. Routing to messaging functions.
        logger.info("** 1. Routing to messaging functions.")
        if message.content.startswith("/summarize"):
            response = StreamingHttpResponse(
                streaming_content=summarize_stream(message, thread, panel),
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


def summarize_stream(message, thread, panel):
    ## Function:
    ## 1. Get settings / check incoming command + file.
    ## 2. Batch up summarization by document context size.
    ## 3. Run batched content for summary.
    ## 4. Create response message with citations.
    ## ----- Leftover parts
    ## 5. Run batched content for summary.
    ## 6. Create response message with citations.
    try:
        ## ----- 1. Get settings / check incoming command + file.
        logger.info("** 1. Get settings / check incoming command + file.")
        message.meta["sender"] = "user_command"
        message.save()
        settings = panel.meta
        filename_pattern = r"/file\s+(\S+)"
        command_pattern = r"^/lookup\s+(?:/file\s+\S+\s+)*(.*)"
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
        command_filename = command_filenames[0] if command_filenames else None

        selected_file = File.objects.filter(
            thread=thread, meta__enabled=True, filename__iexact=command_filename
        ).first()
        if not selected_file:
            yield f"Error: File '{command_filename}' not found in the current thread."
            return
        pickle_path = selected_file.meta.get("pickle_file_path")
        with open(pickle_path, "rb") as f:
            sentences, page_numbers = pickle.load(f)
        completion_model = settings.get("Model")
        context_size = int(settings.get("Document Context Size"))

        ## ----- 2. Batch up summarization by document context size.
        logger.info("** 2. Batch up summarization by document context size.")
        summarize_prompt = "Summarize the following text provided in the next message. Only provide a summary no additional commentary. No yapping please."
        if command_message:
            summarize_prompt += f" Also, {command_message}."
        summarize_prompt_tokens = litellm.token_counter(
            model=completion_model,
            messages=[{"role": "system", "content": summarize_prompt}],
        )
        current_tokens = 0
        batched_sentences = []
        batched_page_numbers = []

        all_summaries = []
        all_citations = []

        for sentence, page_number in zip(sentences, page_numbers):
            current_length = litellm.token_counter(
                model=completion_model, messages=[{"role": "user", "content": sentence}]
            )
            if (
                summarize_prompt_tokens + current_tokens + current_length
                <= context_size
            ):
                batched_sentences.append(sentence)
                batched_page_numbers.append(page_number)
                current_tokens += current_length
            else:
                batch_summary = ""
                batch_citations = []

                ## ----- 3. Run batched content for summary.
                logger.info("** 3. Run batched content for summary.")
                batched_content = "\n".join(batched_sentences)
                messages = [
                    {"role": "system", "content": summarize_prompt},
                    {"role": "user", "content": batched_content},
                ]
                completion_settings = {
                    "stream": True,
                    "model": completion_model,
                    "messages": messages,
                    "api_key": settings.get("LLM Model API Key"),
                    "api_base": (
                        settings.get("URL Base", "").rstrip("/")
                        if settings.get("URL Base") is not None
                        else None
                    ),
                    "api_version": settings.get("API Version"),
                    "organization": settings.get("Organization ID"),
                    "stop": settings.get("Stop Sequence"),
                    "temperature": (
                        float(settings.get("Temperature"))
                        if settings.get("Temperature") is not None
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
                litellm.drop_params = True
                completion_settings_trimmed = {
                    key: value
                    for key, value in completion_settings.items()
                    if value is not None
                }
                response = litellm.completion(**completion_settings_trimmed)
                for part in response:
                    try:
                        delta = part.choices[0].delta.content or ""
                        batch_summary += delta
                        yield delta
                    except Exception as e:
                        logger.info("Skipped chunk: " + str(e))
                        pass

                ## ----- 4. Create response message with citations.
                logger.info("** 4. Create response message with citations.")
                sentences_with_citations = [
                    {"sentence": batch_summary.strip(), "citations": []}
                ]
                # Tracking
                min_page = float("inf")
                max_page = float("-inf")
                combined_sentence = ""
                for sentence, page_number in zip(
                    batched_sentences, batched_page_numbers
                ):
                    min_page = min(min_page, page_number)
                    max_page = max(max_page, page_number)
                    combined_sentence += (
                        sentence + " "
                    )  # Add sentence to combined excerpt
                sentences_with_citations[0]["citations"].append(
                    {
                        "filepath": selected_file.filepath,
                        "filename": selected_file.filename,
                        "citation_excerpt": combined_sentence.strip(),
                        "page_num": (
                            f"{int(min_page)} - {int(max_page)}"
                            if min_page != max_page
                            else f"{int(min_page)}"
                        ),  # Format as "2-4" or just "2"
                    }
                )

                for citation in sentences_with_citations:
                    batch_citations.append(citation)

                all_summaries.append(batch_summary)
                all_citations.extend(batch_citations)

                # Reset after run
                batched_sentences = []
                batched_page_numbers = []
                current_tokens = 0

        if batched_sentences:
            batch_summary = ""
            batch_citations = []

            ## ----- 5. Run batched content for summary.
            logger.info("** 1. Run batched content for summary.")
            batched_content = "\n".join(batched_sentences)
            messages = [
                {"role": "system", "content": summarize_prompt},
                {"role": "user", "content": batched_content},
            ]
            completion_settings = {
                "stream": True,
                "model": completion_model,
                "messages": messages,
                "api_key": settings.get("LLM Model API Key"),
                "api_base": (
                    settings.get("URL Base", "").rstrip("/")
                    if settings.get("URL Base") is not None
                    else None
                ),
                "api_version": settings.get("API Version"),
                "organization": settings.get("Organization ID"),
                "stop": settings.get("Stop Sequence"),
                "temperature": (
                    float(settings.get("Temperature"))
                    if settings.get("Temperature") is not None
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
            litellm.drop_params = True
            completion_settings_trimmed = {
                key: value
                for key, value in completion_settings.items()
                if value is not None
            }
            response = litellm.completion(**completion_settings_trimmed)
            for part in response:
                try:
                    delta = part.choices[0].delta.content or ""
                    batch_summary += delta
                    yield delta
                except Exception as e:
                    logger.info("Skipped chunk: " + str(e))
                    pass

            ## ----- 6. Create response message with citations.
            logger.info("** 6. Create response message with citations.")
            sentences_with_citations = [
                {"sentence": batch_summary.strip(), "citations": []}
            ]
            # Tracking
            min_page = float("inf")
            max_page = float("-inf")
            combined_sentence = ""
            for sentence, page_number in zip(batched_sentences, batched_page_numbers):
                min_page = min(min_page, page_number)
                max_page = max(max_page, page_number)
                combined_sentence += sentence + " "
            # Add single citation
            sentences_with_citations[0]["citations"].append(
                {
                    "filepath": selected_file.filepath,
                    "filename": selected_file.filename,
                    "citation_excerpt": combined_sentence.strip(),
                    "page_num": (
                        f"{int(min_page)} - {int(max_page)}"
                        if min_page != max_page
                        else f"{int(min_page)}"
                    ),  # Format as "2-4" or just "2"
                }
            )

            for citation in sentences_with_citations:
                batch_citations.append(citation)
            all_summaries.append(batch_summary)
            all_citations.extend(batch_citations)
        # Combine all summaries and citations into a single response
        combined_summary = " ".join(all_summaries)
        response_message = Message(
            content=combined_summary,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={
                "sender": "assistant",
                "sentences": all_citations,
            },
        )
        response_message.save()

    except Exception as e:
        logger.error(e, exc_info=True)
        yield "Error: " + str(e)
        response_message = Message(
            content="Error Summarizing: " + str(e),
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
    ## 6. Enrich / append a title to the chat.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]
        completion_model = settings.get("Model")

        ## ----- 2. Get max context and system message.
        logger.info("** 2. Get max context and system message.")
        max_tokens = int(settings.get("Context Size"))
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
            "api_key": settings.get("LLM Model API Key"),
            "api_base": (
                settings.get("URL Base", "").rstrip("/")
                if settings.get("URL Base") is not None
                else None
            ),
            "api_version": settings.get("API Version"),
            "organization": settings.get("Organization ID"),
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

        ## ----- 6. Enrich / append a title to the chat.
        logger.info("** 6. Enrich / append a title to the chat")
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
                "model": settings.get("Simple Model"),
                "messages": title_enrich,
                "api_key": settings.get("LLM Model API Key"),
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
