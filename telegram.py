###############################
# New Function: Setup Monitored Channels
###############################

import logging
import traceback

async def setup_monitored_channels(client, channels_list, logger=None):
    """
    Test each channel and return only the valid ones that can be resolved
    """
    if logger is None:
        logger = logging.getLogger("telegram_setup")
    valid_channels = []
    for channel in channels_list:
        try:
            # Attempt to resolve the channel
            logger.info(f"Testing channel: {channel}")
            await client.get_input_entity(channel)
            valid_channels.append(channel)
            logger.info(f"Successfully verified channel: {channel}")
        except ValueError as e:
            # This happens when the username doesn't exist
            logger.error(f"Invalid channel {channel}: {e}")
        except Exception as e:
            # Other errors (network, etc)
            logger.error(f"Error verifying channel {channel}: {e}")
    
    if not valid_channels:
        logger.critical("No valid channels to monitor! Check your channel list.")
    
    logger.info(f"Monitoring {len(valid_channels)}/{len(channels_list)} channels: {valid_channels}")
    return valid_channels



###############################
# New Function: Post to Telegram Channel
###############################

async def post_to_telegram_channel(text, media_paths, channel_username, client, logger=None):
    """
    Posts the given text (and optionally media) to the specified Telegram channel.
    """
    if logger is None:
        logger = logging.getLogger("telegram_posting")
    logger.info(f"Posting to Telegram channel: {channel_username}")
    try:
        if media_paths:
            await client.send_file(channel_username, media_paths, caption=text)
        else:
            await client.send_message(channel_username, text)
        logger.info(f"Successfully posted to Telegram channel: {channel_username}")
    except Exception as e:
        logger.error(f"Error posting to Telegram channel {channel_username}: {e}")
        logger.error(traceback.format_exc())