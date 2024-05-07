import logging
import time
from django.http import JsonResponse, StreamingHttpResponse
from panel.models import File, Message, Panel, Thread

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
    try:
        yield "File processing..."
        filepath_split = file.filepath.split("/")[-1]
        file_message_status = Message(
            content="<strong>{filepath_split}</strong> uploaded and processed successfully. The document context will now be available for use in the chat.".format(
                filepath_split=filepath_split
            ),
            thread=thread,
            panel=panel,
            created_by=file.created_by,
            metadata={
                "sender": "file_upload",
                "file_id": file.id,
                "file_path": file.filepath,
            },
        )
        file_message_status.save()
    except Exception as e:
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
            metadata={"sender": "assistant", "token_count": len(response_content)},
        )
        response_message.save()
    except Exception as e:
        logger.error(e, exc_info=True)
