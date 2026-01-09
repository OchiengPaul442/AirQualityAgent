"""
Professional Markdown Formatter for Air Quality Agent Responses

This module ensures all AI-generated responses follow professional markdown standards
optimized for air quality research and environmental data presentation. It handles:
- Proper list formatting (numbered and bulleted)
- Professional table rendering for air quality data
- Correct header hierarchy for research reports
- Clean code block formatting with language detection and syntax highlighting
- Clean line breaks and spacing
- Professional source citation formatting for environmental research
- Consistent formatting throughout

Based on established markdown standards and best practices for scientific communication.
"""

import logging
import re

logger = logging.getLogger(__name__)


class MarkdownFormatter:
    """
    Formats Air Quality Agent responses to professional markdown standards.

    This formatter ensures air quality research and environmental data presentations:
    1. Lists have proper spacing (blank line before, no extra lines between items)
    2. Tables are properly formatted with aligned columns for data comparison
    3. Headers have proper spacing (blank line before and after) for report structure
    4. Code blocks are properly formatted with language identifiers and clean syntax
    5. Parentheses and brackets that are incorrectly split across lines are fixed
    6. Emoji numbering is converted to regular numbering for professional appearance
    7. Sources and citations are formatted professionally for environmental research
    8. No excessive line breaks or awkward spacing
    9. Consistent bullet points and numbering for clear data presentation
    """

    @staticmethod
    def format_response(text: str) -> str:
        """
        Apply all markdown formatting rules to create professional output.

        Args:
            text: Raw markdown text from AI

        Returns:
            Professionally formatted markdown text
        """
        if not text or not text.strip():
            return text

        # Apply formatting in specific order
        text = MarkdownFormatter._normalize_line_breaks(text)
        text = MarkdownFormatter._fix_broken_parentheses(text)
        text = MarkdownFormatter._convert_emoji_numbering(text)
        text = MarkdownFormatter._format_headers(text)
        text = MarkdownFormatter._format_lists(text)
        text = MarkdownFormatter._format_tables(text)
        text = MarkdownFormatter._format_code_blocks(text)
        text = MarkdownFormatter._format_sources(text)
        text = MarkdownFormatter._format_bold_and_emphasis(text)
        text = MarkdownFormatter._clean_spacing(text)
        text = MarkdownFormatter._final_cleanup(text)

        return text.strip()

    @staticmethod
    def _normalize_line_breaks(text: str) -> str:
        """Convert various line break formats to consistent \n"""
        # Normalize Windows/Mac line endings to Unix
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove trailing spaces from each line
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines)

    @staticmethod
    def _fix_broken_parentheses(text: str) -> str:
        """
        Fix parentheses and brackets that are incorrectly split across lines.

        This handles cases where AI models generate text like:
        "Station Name ("
        "station_id"
        ")"

        And converts it to:
        "Station Name (station_id)"
        """
        lines = text.split("\n")
        fixed_lines = []
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check if line ends with opening parenthesis/bracket but no closing match
            if ("(" in line or "[" in line or "{" in line) and not (
                ")" in line or "]" in line or "}" in line
            ):
                # Look ahead to find the closing parenthesis/bracket
                opening_count = line.count("(") + line.count("[") + line.count("{")
                closing_count = line.count(")") + line.count("]") + line.count("}")

                if opening_count > closing_count:
                    # Find the line with the matching closing parenthesis/bracket
                    combined_line = line
                    j = i + 1

                    while j < len(lines):
                        next_line = lines[j].strip()
                        # Join lines without extra spaces - let natural text flow handle spacing
                        combined_line += next_line

                        # Count parentheses in this line
                        next_opening = (
                            next_line.count("(") + next_line.count("[") + next_line.count("{")
                        )
                        next_closing = (
                            next_line.count(")") + next_line.count("]") + next_line.count("}")
                        )

                        opening_count += next_opening
                        closing_count += next_closing

                        # If we have balanced parentheses, this is likely the end
                        if opening_count <= closing_count:
                            # Check if this completes the parentheses properly
                            # If the current line contains only closing punctuation, we've found the end
                            if next_line in [")", "]", "}"] or next_line.startswith(
                                (")", "]", "}")
                            ):
                                fixed_lines.append(combined_line)
                                i = j + 1
                                break
                            # If there's more content after this line, keep this line separate
                            elif j + 1 < len(lines) and lines[j + 1].strip():
                                fixed_lines.append(combined_line)
                                i = j
                                break
                            else:
                                # This is the complete combined line
                                fixed_lines.append(combined_line)
                                i = j + 1
                                break
                        j += 1
                    else:
                        # No matching closing found, add the current line as-is
                        fixed_lines.append(line)
                        i += 1
                else:
                    fixed_lines.append(line)
                    i += 1
            else:
                fixed_lines.append(line)
                i += 1

        return "\n".join(fixed_lines)

    @staticmethod
    def _convert_emoji_numbering(text: str) -> str:
        """
        Convert emoji numbering to regular numbering for professional appearance.

        Converts:
        - 1️⃣ → 1.
        - 2️⃣ → 2.
        - etc.
        """
        # Define emoji numbers and their regular counterparts
        emoji_numbers = {
            "1️⃣": "1.",
            "2️⃣": "2.",
            "3️⃣": "3.",
            "4️⃣": "4.",
            "5️⃣": "5.",
            "6️⃣": "6.",
            "7️⃣": "7.",
            "8️⃣": "8.",
            "9️⃣": "9.",
            "🔟": "10.",
        }

        for emoji, regular in emoji_numbers.items():
            text = text.replace(emoji, regular)

        return text

    @staticmethod
    def _format_headers(text: str) -> str:
        """
        Format headers with proper spacing.
        Headers should have:
        - Blank line before (unless it's the first line)
        - Blank line after
        - Space after the # symbols
        """
        lines = text.split("\n")
        formatted_lines: list[str] = []

        for i, line in enumerate(lines):
            # Check if line is a header
            header_match = re.match(r"^(#{1,6})\s*(.*?)$", line)

            if header_match:
                hashes, content = header_match.groups()

                # Ensure space after hashes
                formatted_header = f"{hashes} {content.strip()}"

                # Add blank line before header (if not first line and previous isn't blank)
                if i > 0 and formatted_lines and formatted_lines[-1].strip():
                    formatted_lines.append("")

                formatted_lines.append(formatted_header)

                # Add blank line after header (if next line exists and isn't blank)
                if i < len(lines) - 1 and lines[i + 1].strip():
                    formatted_lines.append("")
            else:
                formatted_lines.append(line)

        return "\n".join(formatted_lines)

    @staticmethod
    def _format_lists(text: str) -> str:
        """
        Format lists with proper spacing and indentation.

        Rules:
        1. Blank line before list starts
        2. No blank lines between list items (unless nested)
        3. Consistent bullet character (-)
        4. Proper indentation for nested lists (2 spaces)
        5. Space after bullet/number
        """
        lines = text.split("\n")
        formatted_lines: list[str] = []
        in_list = False
        list_indent_level = 0

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect list items
            is_bullet = re.match(r"^[\*\-\+]\s+", stripped)
            is_numbered = re.match(r"^\d+\.\s+", stripped)
            is_list_item = bool(is_bullet or is_numbered)

            if is_list_item:
                # Entering a list - add blank line before if needed
                if not in_list and formatted_lines and formatted_lines[-1].strip():
                    formatted_lines.append("")

                in_list = True

                # Get indentation level
                leading_spaces = len(line) - len(line.lstrip())
                indent_level = leading_spaces // 2

                # Normalize bullet character to '-' for consistency
                if is_bullet:
                    # Replace *, +, - with consistent '-'
                    content = re.sub(r"^[\*\-\+]\s+", "", stripped)
                    formatted_item = "  " * indent_level + "- " + content
                else:
                    # Numbered list - keep numbering
                    formatted_item = "  " * indent_level + stripped

                formatted_lines.append(formatted_item)
            else:
                # Not a list item
                if in_list and stripped:
                    # Exiting list - add blank line after if next content exists
                    formatted_lines.append("")
                    in_list = False

                formatted_lines.append(line)

        return "\n".join(formatted_lines)

    @staticmethod
    def _format_tables(text: str) -> str:
        """
        Format markdown tables with proper alignment and spacing.

        Ensures:
        1. Blank line before and after table
        2. Proper pipe alignment
        3. Consistent spacing around pipes
        4. Valid separator row
        5. Fix malformed tables that don't start with pipes
        """
        lines = text.split("\n")
        formatted_lines: list[str] = []
        in_table = False
        table_buffer = []

        for i, line in enumerate(lines):
            # Detect table row (has pipes with content)
            is_table_row = (
                "|" in line and line.strip().startswith("|") and line.strip().endswith("|")
            )

            # Also detect malformed table rows that have pipes but don't start with |
            # This handles cases like: "Header1|Header2|Header3|" or "Data1|Data2|Data3|"
            is_malformed_table_row = (
                "|" in line
                and not line.strip().startswith("|")
                and line.strip().endswith("|")
                and line.count("|") >= 2
            )

            if is_table_row or is_malformed_table_row:
                if not in_table:
                    # Starting new table - add blank line before
                    if formatted_lines and formatted_lines[-1].strip():
                        formatted_lines.append("")
                    in_table = True

                # Fix malformed table row by ensuring it starts with |
                if is_malformed_table_row and not line.strip().startswith("|"):
                    line = "|" + line

                table_buffer.append(line)
            else:
                if in_table:
                    # Finish the table
                    formatted_table = MarkdownFormatter._format_table_buffer(table_buffer)
                    formatted_lines.extend(formatted_table)

                    # Add blank line after table if there's more content
                    if line.strip():
                        formatted_lines.append("")

                    table_buffer = []
                    in_table = False

                formatted_lines.append(line)

        # Handle table at end of document
        if in_table and table_buffer:
            formatted_table = MarkdownFormatter._format_table_buffer(table_buffer)
            formatted_lines.extend(formatted_table)

        return "\n".join(formatted_lines)

    @staticmethod
    def _format_table_buffer(table_rows: list[str]) -> list[str]:  # type: ignore
        """
        Format a complete table with aligned columns.

        CRITICAL FIX: Handle malformed tables with dash separators that cause rendering issues
        """
        if not table_rows:
            return []

        # CRITICAL: Filter out rows that are pure dash separators (not proper markdown)
        # These cause the rendering issue seen in the screenshot
        filtered_rows = []
        for row in table_rows:
            # Skip rows that are just dashes and pipes without proper structure
            stripped = row.strip()
            if not stripped:
                continue

            # Check if this is a malformed separator row (all dashes/pipes, no proper alignment markers)
            # Proper markdown separator: | --- | --- | or | :--- | :---: |
            # Malformed: |-----------------------------|------------------------------------------------------|
            if "|" in stripped:
                cells = [c.strip() for c in stripped.split("|") if c.strip()]
                if cells:
                    # Check if ALL cells are pure dashes (malformed)
                    all_dashes = all(re.match(r"^-+$", cell) for cell in cells)
                    if all_dashes and len(cells) > 0:
                        # This is a malformed separator - skip it entirely
                        logger.warning(f"Skipping malformed table separator row: {stripped[:50]}")
                        continue

            filtered_rows.append(row)

        if not filtered_rows:
            return []

        # Check if first row looks like a title (contains date or comparison text)
        title_row = None
        if len(filtered_rows) > 1:
            first_cells = [cell.strip() for cell in filtered_rows[0].split("|") if cell.strip()]
            second_cells = [cell.strip() for cell in filtered_rows[1].split("|") if cell.strip()]

            # If first row has different column count or contains date/comparison keywords
            is_title_row = (
                len(first_cells) != len(second_cells)
                or any(
                    keyword in filtered_rows[0].lower()
                    for keyword in ["comparison", "202", "summary", "data"]
                )
                or (
                    "(" in filtered_rows[0]
                    and ")" in filtered_rows[0]
                    and len(first_cells) > len(second_cells)
                )
            )

            if is_title_row and len(first_cells) > 1:
                first_cell = first_cells[0]
                is_first_cell_title = any(
                    keyword in first_cell.lower()
                    for keyword in ["comparison", "202", "summary", "data"]
                ) or ("(" in first_cell and ")" in first_cell)

                if is_first_cell_title:
                    title_row = first_cell
                    header_cells = first_cells[1:]
                    filtered_rows[0] = "| " + " | ".join(header_cells) + " |"
                else:
                    title_text = " ".join(first_cells)
                    title_text = re.sub(r"\s+", " ", title_text)
                    title_row = title_text
                    filtered_rows = filtered_rows[1:]

        # Parse table cells
        parsed_rows = []
        for row in filtered_rows:
            cells = [cell.strip() for cell in row.split("|")]
            cells = [c for c in cells if c or cells.index(c) not in (0, len(cells) - 1)]
            if cells:
                parsed_rows.append(cells)

        if not parsed_rows:
            return filtered_rows

        # Calculate column widths
        num_cols = max(len(row) for row in parsed_rows)
        col_widths = [0] * num_cols

        for row in parsed_rows:
            for col_idx, cell in enumerate(row):
                if not re.match(r"^[\-:]+$", cell):
                    col_widths[col_idx] = max(col_widths[col_idx], len(cell))  # type: ignore

        # Ensure minimum width of 3 for separator dashes
        col_widths = [max(w, 3) for w in col_widths]  # type: ignore

        # Format each row with padding
        formatted_rows: list[str] = []

        # Add title if detected
        if title_row:
            formatted_rows.append(f"**{title_row}**")
            formatted_rows.append("")

        # Track if we need to add a separator row (after header)
        needs_separator = True
        separator_added = False

        for row_idx, row in enumerate(parsed_rows):
            formatted_cells = []
            for col_idx in range(num_cols):
                cell = row[col_idx] if col_idx < len(row) else ""

                # Check if this is already a separator row
                if re.match(r"^[\-:]+$", cell):
                    formatted_cells.append("-" * col_widths[col_idx])
                else:
                    formatted_cells.append(cell.ljust(col_widths[col_idx]))

            formatted_row = "| " + " | ".join(formatted_cells) + " |"
            formatted_rows.append(formatted_row)

            # Add separator after first row (header) if not already present
            if needs_separator and row_idx == 0 and not separator_added:
                # Check if next row is separator
                if row_idx + 1 < len(parsed_rows):
                    next_row = parsed_rows[row_idx + 1]
                    is_next_separator = all(
                        re.match(r"^[\-:]+$", cell) for cell in next_row if cell
                    )
                    if not is_next_separator:
                        # Add separator
                        separator = (
                            "| " + " | ".join(["-" * col_widths[i] for i in range(num_cols)]) + " |"
                        )
                        formatted_rows.append(separator)
                        separator_added = True
                else:
                    # No next row, add separator
                    separator = (
                        "| " + " | ".join(["-" * col_widths[i] for i in range(num_cols)]) + " |"
                    )
                    formatted_rows.append(separator)
                    separator_added = True

        return formatted_rows

    @staticmethod
    def _format_code_blocks(text: str) -> str:
        """
        Format code blocks for professional presentation.

        Ensures:
        - Code blocks use proper fenced syntax with language identifiers
        - Inline code is properly formatted
        - Code blocks have consistent formatting
        - Language detection for common programming languages
        """
        if not text:
            return text

        # Handle fenced code blocks (```)
        lines = text.split("\n")
        formatted_lines: list[str] = []
        in_code_block = False
        code_block_lines: list[str] = []
        code_language = ""

        for line in lines:
            if line.strip().startswith("```"):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_language = line.strip()[3:].strip()  # Extract language after ```
                    code_block_lines = []
                else:
                    # End of code block
                    in_code_block = False

                    # If no language specified, try to detect from content
                    if not code_language:
                        code_language = MarkdownFormatter._detect_code_language(code_block_lines)

                    # Clean up code content
                    cleaned_code = MarkdownFormatter._clean_code_content(code_block_lines)

                    # Decide whether this is actually code or just short text that was
                    # accidentally wrapped in fences by the model. If it's short and
                    # doesn't look like code, unwrap it to plain text to avoid ugly
                    # code-block boxes in the UI.
                    joined = "\n".join(cleaned_code).strip()
                    looks_like_code = bool(code_language) or MarkdownFormatter._looks_like_code(
                        joined
                    )

                    if (
                        not looks_like_code
                        and len(joined) > 0
                        and len(joined) <= 80
                        and "\n" not in joined
                    ):
                        # Treat as plain text (single short line) - don't use code fences
                        formatted_lines.append(joined)
                        # preserve a blank line for spacing
                        formatted_lines.append("")
                    else:
                        # Add opening fence with detected language (may be empty)
                        formatted_lines.append(f"```{code_language}")
                        # Add cleaned code lines
                        formatted_lines.extend(cleaned_code)
                        # Add closing fence
                        formatted_lines.append("```")
                        # Add blank line after code block for spacing
                        formatted_lines.append("")

                    code_block_lines = []
                    code_language = ""
            elif in_code_block:
                # Inside code block, collect lines
                code_block_lines.append(line)
            else:
                # Regular text
                formatted_lines.append(line)

        # Handle unclosed code block at end
        if in_code_block and code_block_lines:
            # If no language specified, try to detect from content
            if not code_language:
                code_language = MarkdownFormatter._detect_code_language(code_block_lines)

            cleaned_code = MarkdownFormatter._clean_code_content(code_block_lines)
            # Decide whether to unwrap (same logic as above)
            joined = "\n".join(cleaned_code).strip()
            looks_like_code = bool(code_language) or MarkdownFormatter._looks_like_code(joined)

            if not looks_like_code and len(joined) > 0 and len(joined) <= 80 and "\n" not in joined:
                formatted_lines.append(joined)
                formatted_lines.append("")
            else:
                formatted_lines.append(f"```{code_language}")
                formatted_lines.extend(cleaned_code)
                formatted_lines.append("```")
                formatted_lines.append("")

        return "\n".join(formatted_lines)

    @staticmethod
    def _detect_code_language(code_lines: list[str]) -> str:
        """
        Basic language detection for code blocks.

        Args:
            code_lines: Lines of code to analyze

        Returns:
            Detected language identifier or empty string
        """
        if not code_lines:
            return ""

        code_text = "\n".join(code_lines).lower()

        # Language detection patterns
        language_patterns = {
            "python": ["def ", "import ", "from ", "class ", "if __name__"],
            "javascript": ["function ", "const ", "let ", "var ", "console.log", "=>"],
            "typescript": ["interface ", "type ", ": string", ": number", ": boolean"],
            "java": ["public class", "import java", "public static void main"],
            "cpp": ["#include", "std::", "cout <<", "cin >>"],
            "c": ["#include <stdio.h>", "printf(", "scanf("],
            "csharp": ["using System", "namespace ", "public class", "Console.WriteLine"],
            "php": ["<?php", "echo ", "$", "function "],
            "ruby": ["def ", "puts ", "require ", "class "],
            "go": ["package ", "func ", "import (", "fmt.Println"],
            "rust": ["fn ", "let ", "use ", "println!"],
            "sql": ["select ", "from ", "where ", "insert into", "create table"],
            "bash": ["#!/bin/bash", "echo ", "if [", "for ", "while "],
            "powershell": ["Write-Host", "$", "Get-", "Set-"],
            "yaml": ["version:", "services:", "image:", "ports:"],
            "json": ["{", "}", '"', ":"],
            "xml": ["<", ">", "<?xml", "</"],
            "html": ["<html", "<head", "<body", "<div"],
            "css": ["{", "}", "color:", "font-size:", "margin:"],
        }

        # Count matches for each language
        language_scores = {}
        for lang, patterns in language_patterns.items():
            score = sum(1 for pattern in patterns if pattern in code_text)
            if score > 0:
                language_scores[lang] = score

        # Return the language with highest score
        if language_scores:
            return max(language_scores, key=lambda k: language_scores[k])

        return ""

    @staticmethod
    def _looks_like_code(text: str) -> bool:
        """
        Heuristic to decide if a short piece of text looks like code.
        Returns True if it contains characters or patterns common in code.
        """
        if not text:
            return False

        # Common code indicators: semicolons, parentheses, equals, arrows, braces, keywords
        code_indicators = [
            ";",
            "()",
            "={",
            "=>",
            "->",
            "import ",
            "def ",
            "class ",
            "console.log",
            "{",
            "}",
            "function ",
            "print(",
            "printf(",
            "$",
            "<",
            ">",
            '"',
            "'",
        ]
        score = sum(1 for pat in code_indicators if pat in text)

        # Also detect JSON-like or key:value patterns
        if re.search(r"\"\w+\"\s*:\s*", text):
            score += 2

        return score >= 1

    @staticmethod
    def _clean_code_content(code_lines: list[str]) -> list[str]:
        """
        Clean up code content inside code blocks.

        Args:
            code_lines: Raw code lines

        Returns:
            Cleaned code lines
        """
        if not code_lines:
            return code_lines

        cleaned_lines = []

        # Remove common leading/trailing whitespace issues
        # But preserve indentation for languages that use it
        for line in code_lines:
            # Remove trailing whitespace
            cleaned_line = line.rstrip()

            # For empty lines, keep them as-is (they might be intentional)
            if cleaned_line or line.endswith(" "):
                cleaned_lines.append(cleaned_line)
            else:
                cleaned_lines.append("")

        # Remove excessive empty lines at start and end
        while cleaned_lines and cleaned_lines[0].strip() == "":
            cleaned_lines.pop(0)

        while cleaned_lines and cleaned_lines[-1].strip() == "":
            cleaned_lines.pop()

        return cleaned_lines

    @staticmethod
    def _format_sources(text: str) -> str:
        """
        Format source citations professionally for environmental research.

        Converts various source formats into professional citations for air quality research:
        - "Source: Title (URL) - Summary" -> Professional citation blocks
        - Multiple sources get numbered references for scientific credibility
        - URLs become clickable links for easy access to environmental data
        - Maintains academic/professional appearance suitable for air quality reports
        """
        lines = text.split("\n")
        formatted_lines: list[str] = []
        sources_section_started = False
        current_sources = []

        for i, line in enumerate(lines):
            # Check for inline sources (Source: appearing after content on the same line)
            inline_source_match = re.search(r"(.+?)\s+(Source|source):\s*(.+)$", line)

            if inline_source_match:
                # Handle inline source citation
                content_before, _, full_source_text = inline_source_match.groups()

                # Initialize variables
                url = None
                summary = ""

                # Parse the source text: can be "Title (URL) – summary" or "Title – summary" or just "Title"
                if "(" in full_source_text and ")" in full_source_text:
                    # Has URL in parentheses: Title (URL) – summary
                    url_match = re.search(
                        r"(.+?)\s*\((https?://[^\s)]+)\)(?:\s*–\s*(.+))?", full_source_text
                    )
                    if url_match:
                        title = url_match.group(1).strip()
                        url = url_match.group(2)
                        summary = url_match.group(3).strip() if url_match.group(3) else ""
                    else:
                        title = full_source_text.strip()
                        url = None
                        summary = ""
                else:
                    # No URL: Title – summary
                    if " – " in full_source_text:
                        title, summary = full_source_text.split(" – ", 1)
                        title = title.strip()
                        summary = summary.strip()
                    else:
                        title = full_source_text.strip()
                        summary = ""

                # Check if summary continues on next lines
                if (
                    summary
                    and not summary.endswith(".")
                    and not summary.endswith(")")
                    and i + 1 < len(lines)
                ):
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith("Source:")
                        and not re.match(r"^(?:Source|source):", next_line, re.IGNORECASE)
                    ):
                        summary += " " + next_line
                        lines[i + 1] = ""  # Mark as processed

                # Format inline citation with line break
                if summary and url:
                    citation = f"**{title}** - {summary} ([link]({url}))"
                elif summary:
                    citation = f"**{title}** - {summary}"
                elif url:
                    citation = f"**{title}** ([link]({url}))"
                else:
                    citation = f"**{title}**"

                # Add the content with source on new line
                formatted_lines.append(content_before.strip())
                formatted_lines.append(citation)
                continue

            # Check if this is a standalone source line (handle multi-line summaries)
            stripped_line = line.strip()
            source_match = re.match(
                r"^(?:Source|source):\s*(.+?)\s*\((https?://[^\s)]+)\)(?:\s*-\s*(.+))?$",
                stripped_line,
            )

            if source_match:
                title, url, summary = source_match.groups()
                title = title.strip()
                url = url.strip()
                summary = summary.strip() if summary else ""

                # Check if summary continues on next lines (incomplete summary)
                if (
                    summary
                    and not summary.endswith(".")
                    and not summary.endswith(")")
                    and i + 1 < len(lines)
                ):
                    # Look ahead to find continuation of summary
                    next_line = lines[i + 1].strip()
                    if (
                        next_line
                        and not next_line.startswith("Source:")
                        and not re.match(r"^(?:Source|source):", next_line, re.IGNORECASE)
                    ):
                        summary += " " + next_line
                        lines[i + 1] = ""  # Mark as processed

                # Create professional citation
                if summary:
                    citation = f"**{title}** - {summary} ([link]({url}))"
                else:
                    citation = f"**{title}** ([link]({url}))"

                current_sources.append(citation)
                continue  # Don't add the original line

            # Check if we're starting a sources/references section
            if re.match(
                r"^(?:Sources?|References?|Citations?)(?:\s*:)?\s*$", line.strip(), re.IGNORECASE
            ):
                sources_section_started = True
                formatted_lines.append("")  # Add blank line before sources section
                formatted_lines.append("### Sources & References")
                formatted_lines.append("")
                continue

            # If we have accumulated sources and hit a non-source line, format them
            if current_sources and not source_match and line.strip():
                if not sources_section_started:
                    # Add sources section if not already started
                    formatted_lines.append("")
                    formatted_lines.append("### Sources & References")
                    formatted_lines.append("")

                # Format sources as numbered list
                for i, source in enumerate(current_sources, 1):
                    formatted_lines.append(f"{i}. {source}")

                formatted_lines.append("")  # Add blank line after sources
                current_sources = []  # Reset sources
                sources_section_started = False

            formatted_lines.append(line)

        # Handle any remaining sources at the end
        if current_sources:
            if not sources_section_started:
                formatted_lines.append("")
                formatted_lines.append("### Sources & References")
                formatted_lines.append("")

            for i, source in enumerate(current_sources, 1):
                formatted_lines.append(f"{i}. {source}")

            formatted_lines.append("")

        return "\n".join(formatted_lines)

    @staticmethod
    def _format_bold_and_emphasis(text: str) -> str:
        """
        Ensure bold and emphasis markers are properly formatted.
        - No spaces inside markers
        - Consistent use of ** for bold, * for italic
        """
        # Fix bold with extra spaces: ** text ** -> **text**
        # Only match on single lines to avoid cross-line issues
        text = re.sub(r"(?m)^\*\*\s+([^\*\n]+?)\s+\*\*$", r"**\1**", text)

        # Fix italic with extra spaces: * text * -> *text*
        text = re.sub(r"(?m)^(?<!\*)\*\s+([^\*\n]+?)\s+\*(?!\*)$", r"*\1*", text)

        # Fix bold-italic: *** text *** -> ***text***
        text = re.sub(r"(?m)^\*\*\*\s+([^\*\n]+?)\s+\*\*\*$", r"***\1***", text)

        return text

    @staticmethod
    def _clean_spacing(text: str) -> str:
        """
        Clean up excessive spacing issues.
        - Max 2 consecutive blank lines
        - No spaces at end of lines
        - Proper spacing around blocks
        """
        # Remove trailing spaces from lines
        lines = [line.rstrip() for line in text.split("\n")]

        # Collapse more than 2 consecutive blank lines to 2
        cleaned_lines = []
        blank_count = 0

        for line in lines:
            if not line.strip():
                blank_count += 1
                if blank_count <= 2:
                    cleaned_lines.append(line)
            else:
                blank_count = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    @staticmethod
    def _final_cleanup(text: str) -> str:
        """Final pass to fix any remaining issues"""
        # Remove blank lines at start and end
        text = text.strip()

        # Ensure single blank line between major sections
        # (Already handled mostly, but this catches edge cases)
        text = re.sub(r"\n{4,}", "\n\n\n", text)

        # Fix any remaining spacing around headers
        text = re.sub(r"\n(#{1,6}\s+.*?)\n{3,}", r"\n\n\1\n\n", text)

        return text


def format_markdown(text: str) -> str:
    """
    Convenience function to format markdown text.

    Args:
        text: Raw markdown text

    Returns:
        Professionally formatted markdown

    Example:
        >>> raw = "# Title\\n\\n\\n- item 1\\n- item 2"
        >>> formatted = format_markdown(raw)
        >>> print(formatted)
        # Title

        - item 1
        - item 2
    """
    formatter = MarkdownFormatter()
    return formatter.format_response(text)


def validate_markdown_table(table_text: str) -> dict:
    """
    Validate if a markdown table is properly formatted.

    Args:
        table_text: Markdown table text

    Returns:
        Dict with 'valid' (bool) and 'errors' (list of issues)
    """
    errors = []
    lines = [line.strip() for line in table_text.strip().split("\n") if line.strip()]

    if len(lines) < 2:
        errors.append("Table must have at least header row and separator row")
        return {"valid": False, "errors": errors}

    # Check all lines start and end with |
    for i, line in enumerate(lines):
        if not line.startswith("|") or not line.endswith("|"):
            errors.append(f"Row {i+1} must start and end with |")

    # Check separator row (usually second row)
    if len(lines) >= 2:
        sep_row = lines[1]
        cells = [c.strip() for c in sep_row.split("|")[1:-1]]
        for cell in cells:
            if not re.match(r"^:?-+:?$", cell):
                errors.append(f"Invalid separator row format: {sep_row}")
                break

    # Check consistent column count
    col_counts = []
    for line in lines:
        count = len([c for c in line.split("|")[1:-1]])
        col_counts.append(count)

    if len(set(col_counts)) > 1:
        errors.append(f"Inconsistent column counts: {col_counts}")

    return {"valid": len(errors) == 0, "errors": errors}
