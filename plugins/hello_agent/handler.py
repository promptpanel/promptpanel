import os
import json
import logging
import litellm
import time
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

    try:
        yield "Processing"
        ## ----- 1. Get settings.
        logger.info("** 1. Get settings.")
        completion_model = "gpt-3.5-turbo"
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


def chat_stream(message, thread, panel):
    try:
        response_content = "The message you uploaded was: " + message.content
        # Simulating chat by dripping out characters
        for char in response_content:
            yield char
            time.sleep(0.025)
        response_message = Message(
            content=response_content,
            thread=thread,
            panel=panel,
            created_by=message.created_by,
            meta={"sender": "assistant", "token_count": len(response_content)},
        )
        response_message.save()
    except Exception as e:
        logger.error(e, exc_info=True)
