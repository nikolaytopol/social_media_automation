import argparse
import asyncio
from processor.queue_manager import QueueManager

async def main():
    parser = argparse.ArgumentParser(description="Launch a workflow.")
    parser.add_argument("--channels", type=str, required=True, help="Comma-separated list of Telegram channels.")
    parser.add_argument("--interval", type=int, default=60, help="Reposting interval in seconds.")
    parser.add_argument("--mode", type=str, choices=["simple", "ai_grade"], default="simple", help="Workflow mode.")
    parser.add_argument("--threshold", type=int, default=50, help="AI mode threshold (0-100).")
    args = parser.parse_args()

    # Initialize QueueManager
    queue_manager = QueueManager(interval=args.interval, mode=args.mode, threshold=args.threshold)

    # Simulate adding messages to the queue
    messages = [
        {"text": "This is a test message 1."},
        {"text": "This is a test message 2."},
        {"text": "This is a test message 3."},
    ]
    for message in messages:
        await queue_manager.add_to_queue(message)

    # Start processing the queue
    await queue_manager.process_queue()

if __name__ == "__main__":
    asyncio.run(main())