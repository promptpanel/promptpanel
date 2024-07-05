import os
import json
import logging
import litellm
import mimetypes
import re
import requests
from panel.models import File, Message, Panel, Thread
from django.conf import settings as django_settings
from django.http import JsonResponse, StreamingHttpResponse
from unstructured.partition.auto import partition
from urllib.parse import urlencode

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
    ## 1. Check if the file is an audio or video file.
    ## 2. Prepare a message about how to use the file for transcription.

    try:
        yield "Processing"
        ## ----- 1. Check if the file is an audio or video file.
        mime_type, _ = mimetypes.guess_type(file.filepath)
        is_audio_video = mime_type and mime_type.startswith(("audio/", "video/"))

        ## ----- 2. Prepare a message about how to use the file for transcription.
        if is_audio_video:
            file_message_content = (
                f"Audio/video file uploaded successfully: {file.filename}\n"
                f"Use `/transcribe /file {file.filename}` to transcribe this file. "
                "Include `/diarize` if you'd like to include multi-speaker diarization."
            )
        else:
            file_message_content = (
                f"File uploaded successfully: {file.filename}\n"
                "Note: This file does not appear to be an audio or video file. "
                "Transcription is only available for audio and video files."
            )
        file_message = Message(
            content=file_message_content,
            thread=thread,
            panel=panel,
            created_by=file.created_by,
            meta={
                "sender": "info",
                "prompt": f"/transcribe /file {file.filename}",
                "file_type": "audio_video" if is_audio_video else "other",
            },
        )
        file_message.save()
        yield "Completed"
    except Exception as e:
        logger.error(f"Error in file_stream: {str(e)}", exc_info=True)
        yield f"Error: {str(e)}"


# Message Entrypoint
def message_handler(message, thread, panel):
    try:
        ## Function:
        ## 1. Routing to messaging functions.
        logger.info("** 1. Routing to messaging functions.")
        if message.content.startswith("/transcribe"):
            response = StreamingHttpResponse(
                streaming_content=message_transcribe(message, thread, panel),
                content_type="text/event-stream",
            )
        elif message.content.startswith("/speak"):
            response = StreamingHttpResponse(
                streaming_content=message_speak(message, thread, panel),
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


def message_transcribe(message, thread, panel):
    ## Function:
    ## 1. Get settings.
    ## 2. Parse incoming command
    ## 3. Get file
    ## 4. Transcribe file
    ## 5. Save JSON response and formatted transcript
    ## 6. Save transcription as user message

    try:
        ## ----- 1. Get settings.
        logger.info("** 1. Get file to transcribe and settings.")
        ## Save message as a command
        message.meta["sender"] = "user_command"
        message.save()
        settings = panel.meta

        ## Remove blank-string keys
        keys_to_remove = [k for k, v in settings.items() if v == ""]
        for key in keys_to_remove:
            del settings[key]

        ## ----- 2. Parse incoming command
        filename_pattern = r"/file\s+(\S+)"
        filename_match = re.search(filename_pattern, message.content)
        filename = filename_match.group(1) if filename_match else None
        enable_diarization = "/diarize" in message.content.lower()

        ## ----- 3. Get file
        file = File.objects.filter(
            filename=filename, created_by=message.created_by
        ).first()

        ## ----- 4. Transcribe file
        # Deepgram API settings
        deepgram_api_key = settings.get("Deepgram API Key")
        deepgram_base_endpoint = "https://api.deepgram.com/v1/listen"
        headers = {"Authorization": f"Token {deepgram_api_key}"}
        query_params = {
            "smart_format": "true",
            "punctuate": "true",
            "detect_language": "true",
            "model": settings.get("Deepgram Speech-to-Text Model", "nova-2"),
            "diarize": str(enable_diarization).lower(),
        }
        deepgram_endpoint = f"{deepgram_base_endpoint}?{urlencode(query_params)}"
        logger.info(str(deepgram_endpoint))
        # Open the audio file in binary mode
        with open(file.filepath, "rb") as audio_file:
            response = requests.post(
                deepgram_endpoint, headers=headers, data=audio_file
            )

        if response.status_code == 200:
            result = response.json()

            ## ----- 5. Save JSON response and formatted transcript
            media_root = django_settings.MEDIA_ROOT
            relative_path = f"{panel.id}/{thread.id}"
            full_path = os.path.join(media_root, relative_path)
            os.makedirs(full_path, exist_ok=True)

            # Save JSON response
            json_filename = f"{message.id}_transcription.json"
            json_filepath = os.path.join(full_path, json_filename)
            json_relative_url = f"/media/{relative_path}/{json_filename}"
            with open(json_filepath, "w") as json_file:
                json.dump(result, json_file, indent=4)
            # Create or update File object for JSON
            json_file_obj, created = File.objects.update_or_create(
                filename=json_filename,
                created_by=message.created_by,
                defaults={
                    "filepath": json_filepath,
                    "thread": thread,
                    "panel": panel,
                },
            )

            # Extract and format the transcript with timestamps
            paragraphs = result["results"]["channels"][0]["alternatives"][0][
                "paragraphs"
            ]["paragraphs"]
            formatted_transcript = ""
            for paragraph in paragraphs:
                sentences = paragraph["sentences"]
                text = " ".join([sentence["text"] for sentence in sentences])
                # Inline timestamp formatting
                start_seconds = paragraph["start"]
                end_seconds = paragraph["end"]
                start_time = f"{int(start_seconds // 3600):02d}:{int((start_seconds % 3600) // 60):02d}:{int(start_seconds % 60):02d}"
                end_time = f"{int(end_seconds // 3600):02d}:{int((end_seconds % 3600) // 60):02d}:{int(end_seconds % 60):02d}"
                if enable_diarization and "speaker" in paragraph:
                    formatted_transcript += f"[{start_time} - {end_time}] \n Speaker {paragraph['speaker']}:\n {text}\n\n"
                else:
                    formatted_transcript += f"[{start_time} - {end_time}]\n {text}\n\n"

            # Save formatted transcript
            transcript_filename = f"{message.id}_transcription.txt"
            transcript_filepath = os.path.join(full_path, transcript_filename)
            transcript_relative_url = f"/media/{relative_path}/{transcript_filename}"
            with open(transcript_filepath, "w") as transcript_file:
                transcript_file.write(formatted_transcript)
            # Create or update File object for transcript
            transcript_file_obj, created = File.objects.update_or_create(
                filename=transcript_filename,
                created_by=message.created_by,
                defaults={
                    "filepath": transcript_filepath,
                    "thread": thread,
                    "panel": panel,
                },
            )

            ## ----- 6. Save transcription as user message
            content = f"Transcription for {filename}:\n\n{formatted_transcript}"
            transcription_message = Message(
                content=content,
                thread=thread,
                panel=panel,
                created_by=message.created_by,
                meta={
                    "sender": "assistant",
                    "is_transcription": True,
                    "transcript_txt_path": transcript_relative_url,
                    "transcript_json_path": json_relative_url,
                },
            )
            transcription_message.save()
            yield f"Transcription of {filename} processed and saved successfully.\n"
        else:
            raise Exception(
                f"Transcription request failed: {response.status_code} - {response.text}"
            )
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


def message_speak(message, thread, panel):
    ## Function:
    ## 1. Get settings and parse the command
    ## 2. Prepare the request to Deepgram API
    ## 3. Send the request and get the audio
    ## 4. Save the audio file
    ## 5. Create a new message with the audio link
    try:
        ## ----- 1. Get settings and parse the command
        settings = panel.meta
        deepgram_api_key = settings.get("Deepgram API Key")

        # Remove "/speak" from the beginning of the message
        command_content = message.content.replace("/speak", "", 1).strip()

        # Split the command content
        parts = command_content.split()

        # Find the index of "/voice" if it exists
        voice_index = next(
            (i for i, part in enumerate(parts) if part.lower() == "/voice"), -1
        )

        if voice_index == -1:
            # If "/voice" is not found, use the entire content as text_to_speak
            text_to_speak = command_content
            tts_voice = settings.get("Deepgram Text-To-Speech Voice", "aura-asteria-en")
        else:
            # If "/voice" is found, split the content
            text_to_speak = " ".join(parts[:voice_index])
            if voice_index + 1 < len(parts):
                tts_voice = parts[voice_index + 1]
            else:
                tts_voice = settings.get(
                    "Deepgram Text-To-Speech Voice", "aura-asteria-en"
                )

        if not text_to_speak:
            raise Exception(f"Error: No text provided for text-to-speech conversion.")

        ## ----- 2. Prepare the request to Deepgram API
        url = f"https://api.deepgram.com/v1/speak?model={tts_voice}"
        headers = {
            "Authorization": f"Token {deepgram_api_key}",
            "Content-Type": "application/json",
        }
        data = {"text": text_to_speak}

        ## ----- 3. Send the request and get the audio
        response = requests.post(url, json=data, headers=headers)
        if response.status_code != 200:
            raise Exception(
                f"Error: Deepgram API request failed with status code {response.status_code}"
            )

        ## ----- 4. Save the audio file
        media_root = django_settings.MEDIA_ROOT
        relative_path = f"{panel.id}/{thread.id}"
        full_path = os.path.join(media_root, relative_path)
        os.makedirs(full_path, exist_ok=True)
        file_name = f"{message.id}_deepgram.mp3"
        file_path = os.path.join(full_path, file_name)
        with open(file_path, "wb") as audio_file:
            audio_file.write(response.content)
        # Save as File object
        file_obj = File(
            filename=file_name,
            filepath=file_path,
            created_by=message.created_by,
            thread=thread,
            panel=panel,
        )
        file_obj.save()

        ## ----- 5. Create a new message with the audio link
        relative_url = f"/media/{relative_path}/{file_name}"
        audio_message_content = f"Text-to-speech audio generated using voice '{tts_voice}':\n > {text_to_speak}"
        audio_message = Message(
            content=audio_message_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={
                "sender": "assistant",
                "is_audio": True,
                "audio_file": relative_url,
                "original_text": text_to_speak,
                "tts_voice": tts_voice,
            },
        )
        audio_message.save()
        yield f"Text-to-speech audio generated using voice '{tts_voice}':\n > {text_to_speak}"
    except Exception as e:
        logger.error(f"Error in message_speak: {str(e)}", exc_info=True)
        yield f"Error: {str(e)}"
        # Save error as message
        error_message = Message(
            content=f"Error in text-to-speech conversion: {str(e)}",
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "error"},
        )
        error_message.save()


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
            "api_key": settings.get("API Key"),
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
