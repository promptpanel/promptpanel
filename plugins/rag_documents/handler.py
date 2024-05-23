import os
import itertools
import json
import logging
import litellm
import pickle
from panel.models import File, Message, Panel, Thread
from django.http import JsonResponse, StreamingHttpResponse
from scipy.spatial.distance import cosine
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
        yield "Upload and parsing complete"
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
        completion_model = settings.get("Model")
        temp__token_model = None
        if completion_model == "gpt-4o":
            temp__token_model = "gpt-4-turbo"
        token_model = temp__token_model if temp__token_model else completion_model

        embedding_model = settings["Embedding Model"]

        ## ----- 2. Get max context and system message.
        context_size = int(settings.get("Context Size"))
        system_message = {
            "role": "system",
            "content": settings.get("System Message", ""),
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
        logger.info("** 4. Build document context.")
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
                    sentence_to_add += "Please use the following document context to help inform your answer. Include multiple answers if they come from different citations. \n\n"
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
        logger.info("** 5. Build message history.")
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
        logger.info("** 6. Execute chat.")
        logger.info("Message history: " + str(message_history))
        answer_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_answer",
                    "description": "Answer the question and add citations from document context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "answers": {
                                "description": "Include multiple answers if they come from different citations.",
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "question_answer": {
                                            "description": "Answer to the question which was asked. Do not add citations here.",
                                            "type": "string",
                                        },
                                        "citation_file": {
                                            "type": "number",
                                        },
                                        "citation_index": {
                                            "type": "number",
                                        },
                                        "citation_page": {
                                            "type": "number",
                                        },
                                    },
                                },
                            }
                        },
                    },
                },
            }
        ]
        completion_settings = {
            "stream": False,
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
        if doc_context:
            completion_settings["tools"] = answer_tools
            completion_settings["tool_choice"] = "required"
        litellm.drop_params = True
        completion_settings_trimmed = {
            key: value
            for key, value in completion_settings.items()
            if value is not None
        }
        response = litellm.completion(**completion_settings_trimmed)
        if doc_context:
            answer_response = []
            for tool_call in response.choices[0].message.tool_calls:
                try:
                    response_data = json.loads(tool_call.function.arguments)
                    answer_response.extend(response_data["answers"])
                except Exception as e:
                    logger.info("Could not parse answer parts from response.")
                    try:
                        answer_response = [
                            {"question_answer": response.choices[0].message.content}
                        ]
                    except Exception as e:
                        logger.info("Could not fallback to plain message response.")
                        raise Exception(
                            "Could not parse document context citations, could not fallback to plain message response."
                        )
        else:
            answer_response = [{"question_answer": response.choices[0].message.content}]
        question_answer_textonly = ""
        for item in answer_response:
            question_answer_textonly += item.get("question_answer", "") + " "
        yield question_answer_textonly
        logger.info(answer_response)

        ## ----- 5. Execute chat.
        logger.info("** 6. Enrich response with context content. Save.")
        if thread_files.exists():
            file_id_to_filepath = {
                file.id: file.filepath.replace("/app/", "/") for file in thread_files
            }
            sorted_sentences = [x[0] for x in sorted_similarity]
            for entry in answer_response:
                # Enrich / replace file
                citation_file_id = entry.get("citation_file")
                if citation_file_id is not None:
                    file_path = file_id_to_filepath.get(citation_file_id)
                    if file_path:
                        entry["citation_file"] = file_path

                # Enrich / replace citation
                citation_index = entry.get("citation_index")
                if citation_index is not None:
                    if citation_index < len(sorted_sentences):
                        entry["citation_index"] = sorted_sentences[citation_index]
                    else:
                        entry["citation_index"] = "Index out of range"

        # Save message
        response_message = Message(
            content=question_answer_textonly,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"answers": answer_response, "sender": "assistant"},
        )
        response_message.save()

        ## ----- 6. Enrich / append a title to the chat.
        logger.info("** 9. Enrich / append a title to the chat")
        if user_message_count == 1:
            title_enrich = []
            title_content = """
                You are an assistant who writes informative titles based on questions which are asked by the user. 
                Please only provide a summary, do not provide the answer to the question.
                Title Examples:
                Code: Solution to the fizz buzz problem
                History: Who won the 1998 NBA Finals?
                Brainstorm: New ideas for blog posts
                Translate: Ordering food in Japanese 
            """
            title_enrich.append(
                {
                    "role": "system",
                    "content": title_content,
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
