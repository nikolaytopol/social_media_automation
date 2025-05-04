class AIProvider:
    """Base class for AI providers with standardized interface"""
    
    async def filter_content(self, text, filter_prompt):
        """Return True if content should pass through, False if filtered"""
        raise NotImplementedError
        
    async def modify_content(self, text, transform_prompt):
        """Return modified text based on the prompt"""
        raise NotImplementedError