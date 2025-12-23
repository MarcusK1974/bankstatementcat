#!/usr/bin/env python3
"""
API Configuration Management

Manages API keys, settings, and environment variables for the transformer system.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    print("Note: python-dotenv not installed. Install with: pip install python-dotenv")


class Config:
    """Configuration manager for API keys and settings."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Load .env file if available
        if DOTENV_AVAILABLE:
            env_path = Path('.env')
            if env_path.exists():
                load_dotenv(env_path)
        
        # Load configuration
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.claude_confidence_threshold = float(os.getenv('CLAUDE_CONFIDENCE_THRESHOLD', '0.95'))
        self.learning_enabled = os.getenv('LEARNING_ENABLED', 'true').lower() == 'true'
        self.learned_patterns_path = Path(os.getenv('LEARNED_PATTERNS_PATH', 'data/learned_patterns.json'))
        self.test_mode = os.getenv('TEST_MODE', 'false').lower() == 'true'
        
        self._initialized = True
    
    def has_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self.anthropic_api_key and self.anthropic_api_key.startswith('sk-ant-'))
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.test_mode:
            # Test mode doesn't need API key
            return True, None
        
        if not self.has_api_key():
            return False, (
                "No valid ANTHROPIC_API_KEY found. "
                "Set it as an environment variable or in .env file. "
                "Get your key from: https://console.anthropic.com/"
            )
        
        if not 0.0 <= self.claude_confidence_threshold <= 1.0:
            return False, "CLAUDE_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0"
        
        return True, None
    
    def get_summary(self) -> dict:
        """Get configuration summary."""
        return {
            'has_api_key': self.has_api_key(),
            'api_key_prefix': self.anthropic_api_key[:10] if self.anthropic_api_key else None,
            'claude_confidence_threshold': self.claude_confidence_threshold,
            'learning_enabled': self.learning_enabled,
            'learned_patterns_path': str(self.learned_patterns_path),
            'test_mode': self.test_mode,
        }
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """Get singleton instance."""
        return cls()


def get_config() -> Config:
    """Get configuration instance."""
    return Config.get_instance()


def setup_instructions() -> str:
    """Get setup instructions for users."""
    return """
# Claude API Setup Instructions

## Step 1: Get Your API Key

1. Go to: https://console.anthropic.com/
2. Sign up or log in
3. Navigate to "API Keys" section
4. Click "Create Key"
5. Copy the key (starts with 'sk-ant-')

## Step 2: Configure Your Environment

Choose ONE of these methods:

### Method A: Environment Variable (Recommended)
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### Method B: .env File
```bash
# Create .env file in project root
cp .env.example .env

# Edit .env and add your key:
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## Step 3: Verify Setup

Run:
```bash
python3 -c "from transformer.config.api_config import get_config; print(get_config().get_summary())"
```

## Test Mode (No API Charges)

To test without making real API calls:
```bash
export TEST_MODE=true
```

Or in .env:
```
TEST_MODE=true
```

## Need Help?

- API Documentation: https://docs.anthropic.com/
- Pricing: https://www.anthropic.com/api#pricing
- Support: https://support.anthropic.com/
"""


if __name__ == '__main__':
    config = get_config()
    print("Current Configuration:")
    print("=" * 60)
    for key, value in config.get_summary().items():
        print(f"  {key}: {value}")
    print("=" * 60)
    
    is_valid, error = config.validate()
    if is_valid:
        print("\n✅ Configuration is valid")
    else:
        print(f"\n❌ Configuration error: {error}")
        print("\n" + setup_instructions())

