import uuid
from pathlib import Path
import aiohttp
import mimetypes

from maxo.bot import Bot

from config import BOT_TOKEN

bot = Bot(BOT_TOKEN)


async def download(attachment, path):
    url = attachment.payload.url
    unique_filename = str(uuid.uuid4())
    full_file_path = Path(path) / unique_filename
    full_file_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as s:
        async with s.get(url, ssl=False) as r:
            if r.status == 200:
                content_type = r.headers.get("Content-Type", "")
                file_extension = mimetypes.guess_extension(content_type)
                if not file_extension:
                    file_extension = Path(url.split('?')[0]).suffix or ".bin"

                final_path = full_file_path.with_suffix(file_extension)
                file_data = await r.read()
                final_path.write_bytes(file_data)

                return final_path
            else:
                return "api error"