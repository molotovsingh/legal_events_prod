#!/usr/bin/env python3
"""
Token Counting and Cost Estimation for LLM Providers
Supports OpenAI, Anthropic, Google AI, and Hugging Face models
"""

import tiktoken
import json
from typing import Dict, List, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class TokenCosts:
    """Token cost configuration for different providers"""
    input_cost_per_token: float
    output_cost_per_token: float
    
    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_cost_per_token) + (output_tokens * self.output_cost_per_token)


class BaseTokenizer(ABC):
    """Abstract base class for tokenizers"""
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass
    
    @abstractmethod
    def get_provider(self) -> str:
        pass


class OpenAITokenizer(BaseTokenizer):
    """OpenAI tokenizer implementation"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        self.model_name = model_name
        self.encoder = tiktoken.encoding_for_model(model_name)
        # Updated pricing (as of 2024)
        self.pricing = {
            "gpt-3.5-turbo": TokenCosts(0.0015, 0.002),  # per 1K tokens
            "gpt-4": TokenCosts(0.03, 0.06),
            "gpt-4-turbo": TokenCosts(0.01, 0.03)
        }
    
    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))
    
    def get_provider(self) -> str:
        return "OpenAI"
    
    def calculate_cost(self, text: str, is_input: bool = True) -> float:
        tokens = self.count_tokens(text)
        model_costs = self.pricing[self.model_name]
        
        if is_input:
            return (tokens / 1000) * model_costs.input_cost_per_token
        else:
            return (tokens / 1000) * model_costs.output_cost_per_token


class AnthropicTokenizer(BaseTokenizer):
    """Anthropic Claude tokenizer implementation"""
    
    def __init__(self, model_name: str = "claude-3-sonnet-20240229"):
        self.model_name = model_name
        # Claude uses a custom tokenizer - approximated with tiktoken cl100k_base
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")
        except:
            # Fallback to GPT-4 tokenizer if cl100k_base not available
            self.encoder = tiktoken.encoding_for_model("gpt-4")
        
        # Updated pricing (as of 2024)
        self.pricing = {
            "claude-3-haiku-20240307": TokenCosts(0.00025, 0.00125),
            "claude-3-sonnet-20240229": TokenCosts(0.003, 0.015),
            "claude-3-opus-20240229": TokenCosts(0.015, 0.075)
        }
    
    def count_tokens(self, text: str) -> int:
        return len(self.encoder.encode(text))
    
    def get_provider(self) -> str:
        return "Anthropic"
    
    def calculate_cost(self, text: str, is_input: bool = True) -> float:
        tokens = self.count_tokens(text)
        model_costs = self.pricing[self.model_name]
        
        if is_input:
            return (tokens / 1000) * model_costs.input_cost_per_token
        else:
            return (tokens / 1000) * model_costs.output_cost_per_token


class HuggingFaceTokenizer(BaseTokenizer):
    """Hugging Face tokenizer implementation"""
    
    def __init__(self, model_name: str = "microsoft/DialoGPT-medium"):
        self.model_name = model_name
        from transformers import AutoTokenizer
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            # Add padding token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
        except Exception as e:
            raise ValueError(f"Could not load tokenizer for {model_name}: {e}")
    
    def count_tokens(self, text: str) -> int:
        encoded = self.tokenizer.encode(text, add_special_tokens=True)
        return len(encoded)
    
    def get_provider(self) -> str:
        return "Hugging Face"
    
    def calculate_cost(self, text: str, is_input: bool = True) -> float:
        # Hugging Face doesn't have fixed pricing - return 0 for local models
        return 0.0


class TokenCounter:
    """Main token counting and cost estimation class"""
    
    def __init__(self):
        self.tokenizers: Dict[str, BaseTokenizer] = {}
        self._register_default_tokenizers()
    
    def _register_default_tokenizers(self):
        """Register default tokenizers for common providers"""
        try:
            self.tokenizers["openai-gpt3.5"] = OpenAITokenizer("gpt-3.5-turbo")
            self.tokenizers["openai-gpt4"] = OpenAITokenizer("gpt-4")
            self.tokenizers["anthropic-haiku"] = AnthropicTokenizer("claude-3-haiku-20240307")
            self.tokenizers["anthropic-sonnet"] = AnthropicTokenizer("claude-3-sonnet-20240229")
            self.tokenizers["huggingface-default"] = HuggingFaceTokenizer()
        except ImportError as e:
            print(f"Warning: Some tokenizers could not be loaded: {e}")
    
    def add_custom_tokenizer(self, name: str, tokenizer: BaseTokenizer):
        """Add a custom tokenizer"""
        self.tokenizers[name] = tokenizer
    
    def count_tokens(self, text: str, tokenizer_name: str) -> int:
        """Count tokens using specified tokenizer"""
        if tokenizer_name not in self.tokenizers:
            raise ValueError(f"Tokenizer '{tokenizer_name}' not found. Available: {list(self.tokenizers.keys())}")
        
        return self.tokenizers[tokenizer_name].count_tokens(text)
    
    def estimate_cost(self, 
                     input_text: str, 
                     estimated_output_tokens: int, 
                     tokenizer_name: str) -> Dict[str, float]:
        """Estimate total cost for a request"""
        if tokenizer_name not in self.tokenizers:
            raise ValueError(f"Tokenizer '{tokenizer_name}' not found")
        
        tokenizer = self.tokenizers[tokenizer_name]
        input_tokens = tokenizer.count_tokens(input_text)
        input_cost = tokenizer.calculate_cost(input_text, is_input=True)
        output_cost = tokenizer.calculate_cost("x" * estimated_output_tokens, is_input=False)
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "input_cost_usd": round(input_cost, 6),
            "output_cost_usd": round(output_cost, 6),
            "total_cost_usd": round(total_cost, 6),
            "provider": tokenizer.get_provider(),
            "model": getattr(tokenizer, 'model_name', 'unknown')
        }
    
    def batch_count(self, texts: List[str], tokenizer_name: str) -> List[int]:
        """Count tokens for multiple texts"""
        return [self.count_tokens(text, tokenizer_name) for text in texts]
    
    def get_available_tokenizers(self) -> List[str]:
        """Get list of available tokenizers"""
        return list(self.tokenizers.keys())


def demo_usage():
    """Demonstrate token counting and cost estimation"""
    
    # Initialize the token counter
    counter = TokenCounter()
    
    # Sample texts for testing
    sample_texts = [
        "Hello, how are you today?",
        "This is a longer piece of text that will generate more tokens when processed by the LLM.",
        "Legal documents often contain complex terminology and require detailed analysis for proper understanding.",
    ]
    
    print("=== Token Counting and Cost Estimation Demo ===\n")
    
    print("Available tokenizers:")
    for tokenizer_name in counter.get_available_tokenizers():
        print(f"  - {tokenizer_name}")
    print()
    
    # Example 1: Count tokens for different models
    print("Example 1: Token counting across providers")
    for text in sample_texts:
        print(f"Text: '{text[:50]}...'")
        for tokenizer_name in ["openai-gpt3.5", "anthropic-haiku"]:
            try:
                tokens = counter.count_tokens(text, tokenizer_name)
                print(f"  {tokenizer_name}: {tokens} tokens")
            except Exception as e:
                print(f"  {tokenizer_name}: Error - {e}")
        print()
    
    # Example 2: Cost estimation
    print("Example 2: Cost estimation for a typical request")
    input_text = "Analyze the following legal document and provide a summary of key terms and conditions..."
    estimated_output_tokens = 200  # Expected completion length
    
    for tokenizer_name in ["openai-gpt3.5", "anthropic-haiku", "anthropic-sonnet"]:
        try:
            cost_estimate = counter.estimate_cost(input_text, estimated_output_tokens, tokenizer_name)
            print(f"\nProvider: {cost_estimate['provider']}")
            print(f"Model: {cost_estimate['model']}")
            print(f"Input tokens: {cost_estimate['input_tokens']}")
            print(f"Output tokens: {cost_estimate['estimated_output_tokens']}")
            print(f"Input cost: ${cost_estimate['input_cost_usd']:.6f}")
            print(f"Output cost: ${cost_estimate['output_cost_usd']:.6f}")
            print(f"Total cost: ${cost_estimate['total_cost_usd']:.6f}")
        except Exception as e:
            print(f"\nError with {tokenizer_name}: {e}")
    
    # Example 3: Batch processing
    print(f"\nExample 3: Batch token counting")
    batch_texts = [
        "Legal case summary",
        "Contract analysis", 
        "Regulatory compliance review",
        "Risk assessment report"
    ]
    
    for tokenizer_name in ["openai-gpt3.5"]:
        try:
            token_counts = counter.batch_count(batch_texts, tokenizer_name)
            total_tokens = sum(token_counts)
            
            print(f"Using {tokenizer_name}:")
            for text, tokens in zip(batch_texts, token_counts):
                print(f"  '{text}': {tokens} tokens")
            print(f"Total tokens in batch: {total_tokens}")
        except Exception as e:
            print(f"Error with batch processing: {e}")


if __name__ == "__main__":
    demo_usage()