# processor/queue_manager.py

import asyncio
import time
import threading
from collections import deque
from datetime import datetime

class QueueManager:
    def __init__(self, interval_seconds=60, mode="simple", ai_grade_callback=None, threshold=70):
        """
        Initialize the Queue Manager.

        Args:
            interval_seconds (int): Interval between posts in seconds.
            mode (str): 'simple' or 'ai_grade'.
            ai_grade_callback (callable, optional): Function to score a text.
            threshold (int): Minimum score for AI mode reposting.
        """
        self.queue = deque()
        self.interval = interval_seconds
        self.mode = mode
        self.ai_grade_callback = ai_grade_callback
        self.threshold = threshold
        self.running = False
        self.thread = None

    def add_to_queue(self, text, media_paths, post_callback):
        """
        Add a task to the queue.

        Args:
            text (str): Text to post.
            media_paths (list): Media file paths.
            post_callback (coroutine): Async function to post content.
        """
        self.queue.append((text, media_paths, post_callback))
        if not self.running:
            self.start_worker()

    def add_bulk_history(self, history_items, post_callback, start_date=None):
        """
        Add a bulk list of history items to the queue starting from a certain date.

        Args:
            history_items (list): List of tuples (date, text, media_paths).
            post_callback (coroutine): Async function to post content.
            start_date (datetime, optional): Only add items after this date.
        """
        for item_date, text, media_paths in history_items:
            if start_date is None or item_date >= start_date:
                self.queue.append((text, media_paths, post_callback))
        if not self.running and self.queue:
            self.start_worker()

    def start_worker(self):
        """
        Start the background worker thread.
        """
        self.running = True
        self.thread = threading.Thread(target=self.worker, daemon=True)
        self.thread.start()

    def worker(self):
        """
        Worker that posts items from the queue at intervals.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.process_queue())

    async def process_queue(self):
        """
        Process the queue asynchronously.
        """
        while self.running:
            if self.queue:
                text, media_paths, post_callback = self.queue.popleft()
                try:
                    if self.mode == "simple":
                        await post_callback(text, media_paths)
                        print(f"[QueueManager] Posted from queue: {text[:30]}...")
                    elif self.mode == "ai_grade" and self.ai_grade_callback:
                        score = await self.ai_grade_callback(text)
                        print(f"[QueueManager] AI Score: {score} for text: {text[:30]}...")
                        if score >= self.threshold:
                            await post_callback(text, media_paths)
                            print(f"[QueueManager] Posted based on AI grading.")
                        else:
                            print(f"[QueueManager] Skipped posting based on AI grading.")
                except Exception as e:
                    print(f"[QueueManager] Error posting from queue: {e}")
                await asyncio.sleep(self.interval)
            else:
                await asyncio.sleep(5)

    def stop(self):
        """
        Stop the queue processing.
        """
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()