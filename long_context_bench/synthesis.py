"""Prompt synthesis: Generate natural task instructions from PR metadata using LLMs."""

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

# Import litellm only when needed (for synthesis)
try:
    from litellm import completion
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    completion = None

console = Console()


# Default example user messages for style reference
# These are short, natural instructions that focus on the task, not the solution
DEFAULT_EXAMPLE_MESSAGES = [
    "Fix the bug in the search query parser",
    "Add support for custom field mappings",
    "Refactor the indexing pipeline for better performance",
    "Update the API to handle pagination correctly",
    "Implement caching for frequently accessed data",
    "Fix the memory leak in the aggregation module",
    "Add validation for user input parameters",
    "Improve error handling in the network layer",
]


def build_synthesis_prompt(
    pr_title: str,
    pr_body: str,
    pr_diff: str,
    example_messages: Optional[list[str]] = None,
) -> tuple[str, str]:
    """Build the prompt and rules for synthesizing a user message from PR metadata.

    Analyzes the PR and generates a natural user message that could have prompted
    the PR creation.
    
    Args:
        pr_title: PR title
        pr_body: PR description/body
        pr_diff: Full PR diff
        example_messages: Optional list of example user messages for style reference
        
    Returns:
        Tuple of (prompt, rules)
    """
    if example_messages is None:
        example_messages = DEFAULT_EXAMPLE_MESSAGES
    
    # Format example messages
    user_messages_section = "\n--------------\n".join(example_messages)
    
    # Build the main prompt
    prompt = (
        "Analyze the following pull request and the codebase thoroughly and "
        "generate the user message that created it.\n\n"
        "The pull request title is:\n"
        "```\n"
        f"{pr_title}\n"
        "```\n"
        "The pull request body is:\n"
        "```\n"
        f"{pr_body or '(no description)'}\n"
        "```\n"
        "The pull request diff is:\n"
        "```\n"
        f"{pr_diff}\n"
        "```\n"
        "\n\n"
        "Example user messages:\n"
        f"{user_messages_section}\n"
    )
    
    # Build the rules/guidelines
    rules = (
        "Guidelines:\n"
        " - The generated user message should not be a question.\n"
        " - If the pull request contains tests, the generated user message "
        "should ALWAYS focus on the non-test code changes.\n"
        " - The generated user message MUST follow the style and tone "
        "of the example user messages.\n"
        " - The generated user message MUST STRICTLY align with "
        "the length and detail of the example user messages.\n"
        " - The generated user message length MUST NEVER exceed the length of the "
        "longest example user message.\n"
        " - The generated user message length MUST NEVER be shorter than the "
        "shortest example user message.\n"
        " - The generated user message MUST not contain any information "
        "about the pull request itself.\n"
        " - The generated user message MUST not provide details about "
        "solution.\n"
        " - You MUST always strictly respond in the required output format:\n"
        "```\n"
        "<user_message>\n"
        "    ... generated user message ...\n"
        "</user_message>\n"
        "```"
    )
    
    return prompt, rules


def extract_user_message(response_text: str) -> Optional[str]:
    """Extract the user message from the LLM response.

    Expects the response to contain <user_message>...</user_message> tags.
    If tags are not found, tries to extract the message directly.

    Args:
        response_text: Full LLM response text

    Returns:
        Extracted user message, or None if parsing failed
    """
    # Look for <user_message>...</user_message> tags
    match = re.search(r"<user_message>(.*?)</user_message>", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: If no tags, try to extract the message directly
    # Remove common prefixes and clean up
    text = response_text.strip()

    # Remove common prefixes
    prefixes_to_remove = [
        "Here is the user message:",
        "User message:",
        "The user message is:",
        "Generated user message:",
    ]
    for prefix in prefixes_to_remove:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            break

    # If the text is reasonable length (not too long), use it
    if text and len(text) < 500 and '\n\n' not in text:
        return text

    return None


def synthesize_task_instructions(
    pr_title: str,
    pr_body: str,
    pr_diff: str,
    model: str = "claude-3-7-sonnet-20250219",
    example_messages: Optional[list[str]] = None,
    max_diff_chars: int = 50000,
) -> Optional[str]:
    """Synthesize natural task instructions from PR metadata using an LLM.

    This uses LiteLLM to call an LLM (default: Claude Sonnet 3.7) to generate
    a natural user message that could have prompted the PR creation.

    Args:
        pr_title: PR title
        pr_body: PR description/body
        pr_diff: Full PR diff
        model: LiteLLM model identifier (e.g., "claude-3-7-sonnet-20250219")
        example_messages: Optional list of example user messages for style reference
        max_diff_chars: Maximum characters to include from diff (to avoid token limits)

    Returns:
        Synthesized task instructions, or None if synthesis failed
    """
    if not LITELLM_AVAILABLE:
        console.print(f"  [red]✗ LiteLLM not installed. Install with: pip install litellm[/red]")
        return None

    try:
        # Truncate diff if too long
        if len(pr_diff) > max_diff_chars:
            pr_diff = pr_diff[:max_diff_chars] + "\n\n[diff truncated for synthesis]"
        
        # Build prompt and rules
        prompt, rules = build_synthesis_prompt(pr_title, pr_body, pr_diff, example_messages)
        
        # Combine prompt and rules into system message
        system_message = f"{prompt}\n\n{rules}"
        
        console.print(f"  [dim]Synthesizing with {model}...[/dim]")
        
        # Call LLM via LiteLLM
        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": "Generate the user message."},
            ],
            temperature=0.7,  # Some creativity, but not too much
            max_tokens=500,   # User messages should be short
        )
        
        # Extract response text
        response_text = response.choices[0].message.content
        
        # Parse user message
        user_message = extract_user_message(response_text)
        
        if user_message:
            console.print(f"  [green]✓ Synthesized: {user_message[:80]}...[/green]")
            return user_message
        else:
            console.print(f"  [yellow]⚠ Failed to parse synthesis response[/yellow]")
            console.print(f"  [dim]Response: {response_text[:200]}...[/dim]")
            return None
            
    except Exception as e:
        console.print(f"  [red]✗ Synthesis failed: {e}[/red]")
        return None


def get_synthesis_timestamp() -> str:
    """Get current timestamp in ISO format for synthesis metadata.

    Returns:
        ISO format timestamp string
    """
    return datetime.utcnow().isoformat() + "Z"


def synthesize_with_auggie(
    pr_title: str,
    pr_body: str,
    pr_diff: str,
    model: str = "claude-sonnet-4",
    example_messages: Optional[list[str]] = None,
    max_diff_chars: int = 10000,  # Smaller limit for Auggie to avoid timeouts
) -> Optional[str]:
    """Synthesize task instructions using Auggie CLI.

    This uses the Auggie CLI to generate natural task instructions from PR metadata.
    Requires Auggie to be installed and authenticated (via OAuth or API token).

    Args:
        pr_title: PR title
        pr_body: PR description/body
        pr_diff: Full PR diff
        model: Auggie model name (e.g., "claude-sonnet-4")
        example_messages: Optional list of example user messages for style reference
        max_diff_chars: Maximum characters to include from diff (to avoid token limits)

    Returns:
        Synthesized task instructions, or None if synthesis failed
    """
    try:
        # Truncate diff if too long
        if len(pr_diff) > max_diff_chars:
            pr_diff = pr_diff[:max_diff_chars] + "\n\n[diff truncated for synthesis]"

        # Build a simplified prompt for Auggie to avoid tool usage
        # Auggie tends to use tools when it sees "codebase" or "pull request"
        if example_messages is None:
            example_messages = DEFAULT_EXAMPLE_MESSAGES

        examples_text = "\n".join(f"- {msg}" for msg in example_messages)

        instruction = f"""You are a text generation assistant. Generate a concise user message based on the following information.

Title: {pr_title}

Description: {pr_body or '(no description)'}

Code changes summary (first 1000 chars):
{pr_diff[:1000] if len(pr_diff) > 1000 else pr_diff}

Example messages (match this style and length):
{examples_text}

Rules:
- Generate ONLY a short user message (1-2 sentences)
- Focus on what needs to be done, not how
- Match the style of the examples
- Do NOT use any tools or analyze files
- Output format: <user_message>your message here</user_message>

Generate the user message now."""

        console.print(f"  [dim]Synthesizing with Auggie ({model})...[/dim]")

        # Create temporary file for instruction
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(instruction)
            instruction_file = f.name

        try:
            # Create a temporary directory for Auggie to run in
            # This avoids Auggie trying to analyze the current codebase
            with tempfile.TemporaryDirectory() as temp_workspace:
                # Call Auggie CLI in print mode (one-shot, non-interactive)
                result = subprocess.run(
                    [
                        "auggie",
                        "--model", model,
                        "--instruction-file", instruction_file,
                        "--print",  # Print mode - one-shot
                        "--max-turns", "1",  # Single turn
                    ],
                    capture_output=True,
                    text=True,
                    timeout=180,  # 3 minute timeout
                    cwd=temp_workspace,  # Run in empty temp dir to avoid codebase analysis
                )

                if result.returncode != 0:
                    console.print(f"  [red]✗ Auggie failed: {result.stderr}[/red]")
                    return None

                # Extract user message from Auggie's output
                response_text = result.stdout
                user_message = extract_user_message(response_text)

                if user_message:
                    console.print(f"  [green]✓ Synthesized: \"{user_message[:80]}{'...' if len(user_message) > 80 else ''}\"[/green]")
                    return user_message
                else:
                    console.print(f"  [yellow]⚠ Could not extract user message from Auggie output[/yellow]")
                    return None

        finally:
            # Clean up temp file
            Path(instruction_file).unlink(missing_ok=True)

    except subprocess.TimeoutExpired:
        console.print(f"  [red]✗ Auggie timed out after 120 seconds[/red]")
        return None
    except FileNotFoundError:
        console.print(f"  [red]✗ Auggie CLI not found. Install with: npm install -g @augmentcode/cli[/red]")
        return None
    except Exception as e:
        console.print(f"  [red]✗ Synthesis failed: {type(e).__name__}: {e}[/red]")
        return None

