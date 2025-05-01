import os
import asyncio

async def monitor_new_folders(parent_folder):
    """
    Monitors the parent_folder for newly created subfolders and prints their names
    along with the list of files inside them.
    """
    processed_folders = set(os.listdir(parent_folder))  # Track already seen folders

    while True:
        try:
            # Get the current list of folders
            current_folders = set(os.listdir(parent_folder))

            # Identify new folders
            new_folders = current_folders - processed_folders

            for folder in new_folders:
                folder_path = os.path.join(parent_folder, folder)

                # Ensure it's a directory
                if os.path.isdir(folder_path):
                    print(f"New folder detected: {folder}")
                    print("Files in the folder:")
                    for file_name in os.listdir(folder_path):
                        print(f"  - {file_name}")

                    # Mark the folder as processed
                    processed_folders.add(folder)

            # Sleep for a short duration before checking again
            await asyncio.sleep(2)

        except Exception as e:
            print(f"Error while monitoring folders: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    output_folder = "tweet_history"  # Replace with your folder path
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)  # Ensure the folder exists

    print(f"Monitoring folder: {output_folder}")
    asyncio.run(monitor_new_folders(output_folder))