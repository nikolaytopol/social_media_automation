# processor/processing_engine.py

import asyncio
import threading
import time

from processor.telegram_listener import TelegramListener
from processor.twitter_utils import TwitterPoster
from processor.instagram_utils import InstagramReader
from processor.queue_manager import QueueManager
from processor.openai_utils import OpenAIUtils

class Processor:
    def __init__(self, workflow_config):
        self.workflow_id = workflow_config['_id']
        self.user_id = workflow_config['user_id']
        self.sources = workflow_config['sources']
        self.destinations = workflow_config['destinations']
        self.filter_prompt = workflow_config.get('filter_prompt', '')
        self.mod_prompt = workflow_config.get('mod_prompt', '')
        self.duplicate_check = workflow_config.get('duplicate_check', False)
        self.mode = workflow_config.get('repost_method', 'immediate')  # 'immediate' or 'queue'

        self.telegram_listener = None
        self.twitter_poster = TwitterPoster()
        self.instagram_reader = InstagramReader()
        self.queue_manager = QueueManager() if self.mode == 'queue' else None
        self.openai_utils = OpenAIUtils()

        self.running = False

    async def setup_sources(self):
        """Initialize source listeners."""
        telegram_channels = [src['name'] for src in self.sources if src['type'] == 'telegram']
        if telegram_channels:
            self.telegram_listener = TelegramListener(telegram_channels, self)
            await self.telegram_listener.connect()

    async def handle_new_content(self, text, media_paths, source_type, source_name):
        """Handle incoming content from a source."""
        # Optionally apply OpenAI filter
        if self.filter_prompt:
            passed = await self.openai_utils.filter_content(text, self.filter_prompt)
            if not passed:
                print(f"[Workflow {self.workflow_id}] Content filtered out.")
                return

        # Optionally modify text
        if self.mod_prompt:
            text = await self.openai_utils.modify_content(text, self.mod_prompt)

        # Send to destinations
        if self.mode == 'immediate':
            await self._post_immediate(text, media_paths)
        elif self.mode == 'queue' and self.queue_manager:
            self.queue_manager.add_to_queue(text, media_paths, self._post_immediate)

    async def _post_immediate(self, text, media_paths):
        """Immediately post content to all destinations."""
        for dest in self.destinations:
            if dest == 'twitter':
                await self.twitter_poster.post(text, media_paths)
            elif dest == 'telegram' and self.telegram_listener:
                await self.telegram_listener.post_to_channel(text, media_paths)

    async def run(self):
        """Main processor loop."""
        self.running = True
        await self.setup_sources()

        if self.telegram_listener:
            telegram_task = asyncio.create_task(self.telegram_listener.listen())

        # Placeholder for future Instagram or other source listeners
        # instagram_task = asyncio.create_task(self.instagram_reader.listen())

        while self.running:
            await asyncio.sleep(5)

    def stop(self):
        self.running = False

# --- Threaded Runner ---
def start_processor_in_thread(workflow_config):
    """Utility to run a Processor in a separate thread."""
    processor = Processor(workflow_config)

    def thread_target():
        asyncio.run(processor.run())

    thread = threading.Thread(target=thread_target, daemon=True)
    thread.start()
    return processor, thread
