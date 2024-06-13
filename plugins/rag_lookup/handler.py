import os
import itertools
import json
import logging
import litellm
import pickle
import re
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse
from nltk.tokenize import sent_tokenize
from scipy.spatial.distance import cosine
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

    try:
        yield "Processing"
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        embedding_api_key = settings.get("Embedding API Key")
        embedding_model = settings.get("Embedding Model")

        ## ----- 2. Parse file and save embeddings.
        logger.info("** 2. Parse file and save embeddings.")
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
        embedded_response = litellm.embedding(
            model=embedding_model,
            api_key=embedding_api_key,
            input=sentences,
        )
        sentence_embeddings = [
            sentence["embedding"] for sentence in embedded_response.data
        ]
        pickle_path = f"{file.filepath}.pkl"
        pickle_data = (sentences, page_numbers, sentence_embeddings)
        with open(pickle_path, "wb") as f:
            pickle.dump(pickle_data, f)
        file.meta.update({"enabled": True, "pickle_file_path": pickle_path})
        file.save()
        ## ----- 3. Add file upload message / hinting for usage.
        logger.info("** 3. Add file upload message / hinting for usage.")
        file_message_content = f"File uploaded successfully.\n To summarize, message `/lookup {file.filename} [question*]`"
        file_message = Message(
            content=file_message_content,
            thread=thread,
            panel=panel,
            created_by=file.created_by,
            meta={
                "sender": "info",
                "prompt": f"/lookup {file.filename}",
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


def document_lookup(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Get max context and system message.
    ## 3. Build document context.
    ## 4. Build message history.
    ## 5. Execute chat.
    ## 6. Enrich with citations and save.
    ## 7. Enrich / append a title to the chat.

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        settings = panel.meta
        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]
        completion_model = settings.get("Model")
        temp__token_model = None
        if completion_model == "gpt-4o":
            temp__token_model = "gpt-4-turbo"
        token_model = temp__token_model if temp__token_model else completion_model
        embedding_model = settings["Embedding Model"]

        ## ----- 2. Get max context and system message.
        logger.info("** 2. Get max context and system message.")
        context_size = int(settings.get("Context Size"))
        system_message_text = settings.get("System Message", "")
        system_message_instruct = """
        \n\nPlease use the following format for citing document context if it is used in your answer:\n
        This is my example answer {file: 1, index: 1, page: 1}. This is another part of my answer {file: 1, index: 4, page: 10}. This is a final part of my answer {file: 2, index: 12, page: 4}.\n
        It is important that the citations MUST match this format, do not format the objects any other way.
        """.strip()
        system_message = {
            "role": "system",
            "content": system_message_text + system_message_instruct,
        }
        system_message_token_count = litellm.token_counter(
            model=token_model, messages=[system_message]
        )
        if settings.get("Max Tokens to Generate") is not None:
            remaining_tokens = (
                context_size
                - system_message_token_count
                - int(settings.get("Max Tokens to Generate"))
            )
        else:
            remaining_tokens = context_size - system_message_token_count

        ## ----- 3. Build document context.
        logger.info("** 3. Build document context.")
        thread_files = File.objects.filter(thread=thread, meta__enabled=True)
        # Check if any files are active first
        if thread_files.exists():
            # Create embedding incoming message
            embedding_settings = {
                "model": embedding_model,
                "api_key": settings.get("Embedding API Key"),
                "input": [message.content],
            }
            embedding_settings_trimmed = {
                key: value
                for key, value in embedding_settings.items()
                if value is not None
            }
            embedded_response = litellm.embedding(**embedding_settings_trimmed)
            embedded_message = [
                sentence["embedding"] for sentence in embedded_response.data
            ][0]

            # Get file embeddings
            sentences = []
            page_numbers = []
            embedded_sentences = []
            associated_files = []
            for file in thread_files:
                pickle_path = file.meta.get("pickle_file_path")
                with open(pickle_path, "rb") as f:
                    (
                        sentences_data,
                        page_numbers_data,
                        embedded_sentences_data,
                    ) = pickle.load(f)
                sentences.extend(sentences_data)
                page_numbers.extend(page_numbers_data)
                embedded_sentences.extend(embedded_sentences_data)
                associated_files.extend([file.id] * len(sentences_data))

            # Calculate scoring of sentence vs. message + sort
            similarities = [
                1 - cosine(embedded_message, embedded_sentence)
                for embedded_sentence in embedded_sentences
            ]
            combined_results = list(
                itertools.zip_longest(
                    sentences,
                    page_numbers,
                    associated_files,
                    similarities,
                    fillvalue="Missing",
                )
            )
            sorted_similarity = sorted(
                combined_results, key=lambda x: x[3], reverse=True
            )

            # Build up document context
            doc_token_limit = int(settings.get("Document Context Size"))
            doc_current_tokens = 0
            doc_context = ""
            for index, (sentence, page_number, file, similarity) in enumerate(
                sorted_similarity[:20]
            ):
                # Using the top 20 > can be extended
                sentence_to_add = ""
                if doc_context == "":
                    sentence_to_add += "Please use the following document context to help inform your answer: \n\n"
                sentence_to_add += f"From File ID: {file}, Index ID: {index}, On Page Number: {page_number}, Context: {sentence} \n\n"
                doc_msg = {
                    "role": "user",
                    "content": sentence_to_add,
                }
                doc_msg_token_count = litellm.token_counter(
                    model=token_model, messages=[doc_msg]
                )
                if doc_msg_token_count + doc_current_tokens <= doc_token_limit:
                    doc_current_tokens = doc_current_tokens + doc_msg_token_count
                    doc_context += sentence_to_add
                else:
                    break
                remaining_tokens = remaining_tokens - doc_msg_token_count
        else:
            logger.info("No documents uploaded or selected.")
            doc_context = False

        ## ----- 4. Build message history.
        logger.info("** 4. Build message history.")
        messages = Message.objects.filter(
            created_by=message.created_by, thread_id=thread.id
        ).order_by("-created_on")
        message_history = []
        message_history_token_count = 0
        user_message_count = 0  # Counter for titling
        for msg in messages:
            role = msg.meta.get("sender", "user")
            if role == "user" or role == "assistant":
                msg_content_row = [{"role": role, "content": msg.content}]
                msg_token_count = litellm.token_counter(
                    model=token_model, messages=msg_content_row
                )
            if msg_token_count + message_history_token_count <= remaining_tokens:
                # Container for message
                if role == "user":
                    user_message_count += 1
                    message_history_token_count += msg_token_count
                    message_history.append(
                        {
                            "role": "user",
                            "content": msg.content,
                        }
                    )
                if role == "assistant":
                    message_history_token_count += msg_token_count
                    message_history.append(
                        {
                            "role": "assistant",
                            "content": msg.content,
                        }
                    )
            else:
                break
        if doc_context:
            message_history.append(
                {
                    "role": "user",
                    "content": doc_context,
                }
            )
        message_history.append(system_message)
        message_history.reverse()

        ## ----- 5. Execute chat.
        logger.info("** 5. Execute chat.")
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
        logger.info("Raw Response: " + str(response))
        response_content = ""
        for part in response:
            try:
                delta = part.choices[0].delta.content or ""
                response_content += delta
                yield delta
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass

        ## ----- 6. Enrich with citations and save.
        logger.info("** 6. Enrich with citations and save")
        citation_pattern = r"\{file: (\d+), index: (\d+), page: (\d+)\}"
        response_sentences = sent_tokenize(response_content)
        file_with_filepath = (
            {
                file.id: {
                    "filepath": file.filepath.replace("/app/", "/"),
                    "filename": file.filename,
                }
                for file in thread_files
            }
            if thread_files.exists()
            else {}
        )
        sorted_sentences = [x[0] for x in sorted_similarity]
        sentences = []
        previous_sentence_obj = None

        # Breakdown citations and nest them under sentences
        for sentence in response_sentences:
            matches = list(re.finditer(citation_pattern, sentence))
            stripped_sentence = re.sub(citation_pattern, "", sentence).strip()
            sentence_obj = (
                {"sentence": stripped_sentence, "citations": []}
                if stripped_sentence
                else None
            )

            # Handle citations that belong to the previous sentence
            if matches and previous_sentence_obj is not None:
                for match in matches:
                    file_id, index, page = map(int, match.groups())
                    file_info = file_with_filepath.get(file_id)
                    filepath = file_info.get("filepath") if file_info else None
                    filename = file_info.get("filename") if file_info else None
                    citation_excerpt = (
                        sorted_sentences[index] if index < len(sorted_sentences) else ""
                    )
                    previous_sentence_obj["citations"].append(
                        {
                            "filepath": filepath,
                            "filename": filename,
                            "citation_excerpt": citation_excerpt,
                            "page_num": page,
                        }
                    )
                if sentence_obj is not None:
                    sentences.append(sentence_obj)
            elif sentence_obj is not None:
                sentences.append(sentence_obj)
            previous_sentence_obj = sentence_obj

        # Check for dangling citations
        if previous_sentence_obj is not None and previous_sentence_obj["citations"]:
            sentences.append(previous_sentence_obj)

        # Save message
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "assistant", "sentences": sentences},
        )
        response_message.save()

        ## ----- 7. Enrich / append a title to the chat.
        logger.info("** 7. Enrich / append a title to the chat.")
        if user_message_count == 1:
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


def chat_stream(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Enrich incoming message with token_count.
    ## 3. Get max context and system message.
    ## 4. Build message history.
    ## 5. Execute chat.
    ## 6. Save warnings as needed.
    ## 7. Cleanup message text, enrich with token count, and save.
    ## 8. Enrich / append a title to the chat.

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
        ## ----- 4. Build message history.
        logger.info("** 4. Build message history.")
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
        message_history.append(system_message)
        message_history.reverse()

        ## ----- 5. Execute chat.
        logger.info("** 5. Execute chat.")
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
        if skipped_images:
            yield "> Vision is not available with this model.\n\n"
        for part in response:
            try:
                delta = part.choices[0].delta.content or ""
                response_content += delta
                yield delta
            except Exception as e:
                logger.info("Skipped chunk: " + str(e))
                pass

        ## ----- 6. Save warnings as needed.
        logger.info("** 6. Save warnings as needed.")
        if skipped_images:
            warning_images = Message(
                content="Vision is not available with this model.",
                thread=thread,
                panel=panel,
                created_by=message.created_by,
                meta={"sender": "warning"},
            )
            warning_images.save()

        ## ----- 7. Cleanup message text, enrich with token count, and save.
        logger.info("** 7. Cleanup message text, enrich with token count, and save.")
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
