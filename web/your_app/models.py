class Workflow:
    def __init__(self, user_id, sources, filter_prompt, repost_method, destinations, duplicate_check, mod_prompt, status='stopped'):
        self.user_id = user_id
        self.sources = sources  # e.g., ["Telegram Channel A", "Twitter Account B"]
        self.filter_prompt = filter_prompt
        self.repost_method = repost_method  # immediate, queue, etc.
        self.destinations = destinations  # ["Telegram", "Twitter"]
        self.duplicate_check = duplicate_check
        self.mod_prompt = mod_prompt
        self.status = status  # running / stopped
