"""
Professional Markdown Formatter for AI Agent Responses

This module ensures all AI-generated responses follow professional markdown standards
similar to ChatGPT output quality. It handles:
- Proper list formatting (numbered and bulleted)
- Professional table rendering
- Correct header hierarchy
- Clean line breaks and spacing
- Consistent formatting throughout

Based on best practices from leading AI assistants and markdown standards.
"""

import re
from typing import List


class MarkdownFormatter:
    """
    Formats AI agent responses to professional markdown standards.
    
    This formatter ensures:
    1. Lists have proper spacing (blank line before, no extra lines between items)
    2. Tables are properly formatted with aligned columns
    3. Headers have proper spacing (blank line before and after)
    4. No excessive line breaks or awkward spacing
    5. Consistent bullet points and numbering
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
        text = MarkdownFormatter._format_headers(text)
        text = MarkdownFormatter._format_lists(text)
        text = MarkdownFormatter._format_tables(text)
        text = MarkdownFormatter._format_bold_and_emphasis(text)
        text = MarkdownFormatter._clean_spacing(text)
        text = MarkdownFormatter._final_cleanup(text)

        return text.strip()

    @staticmethod
    def _normalize_line_breaks(text: str) -> str:
        """Convert various line break formats to consistent \n"""
        # Normalize Windows/Mac line endings to Unix
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Remove trailing spaces from each line
        lines = [line.rstrip() for line in text.split('\n')]
        return '\n'.join(lines)

    @staticmethod
    def _format_headers(text: str) -> str:
        """
        Format headers with proper spacing.
        Headers should have:
        - Blank line before (unless it's the first line)
        - Blank line after
        - Space after the # symbols
        """
        lines = text.split('\n')
        formatted_lines = []
        
        for i, line in enumerate(lines):
            # Check if line is a header
            header_match = re.match(r'^(#{1,6})\s*(.*?)$', line)
            
            if header_match:
                hashes, content = header_match.groups()
                
                # Ensure space after hashes
                formatted_header = f"{hashes} {content.strip()}"
                
                # Add blank line before header (if not first line and previous isn't blank)
                if i > 0 and formatted_lines and formatted_lines[-1].strip():
                    formatted_lines.append('')
                
                formatted_lines.append(formatted_header)
                
                # Add blank line after header (if next line exists and isn't blank)
                if i < len(lines) - 1 and lines[i + 1].strip():
                    formatted_lines.append('')
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

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
        lines = text.split('\n')
        formatted_lines = []
        in_list = False
        list_indent_level = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Detect list items
            is_bullet = re.match(r'^[\*\-\+]\s+', stripped)
            is_numbered = re.match(r'^\d+\.\s+', stripped)
            is_list_item = bool(is_bullet or is_numbered)
            
            if is_list_item:
                # Entering a list - add blank line before if needed
                if not in_list and formatted_lines and formatted_lines[-1].strip():
                    formatted_lines.append('')
                
                in_list = True
                
                # Get indentation level
                leading_spaces = len(line) - len(line.lstrip())
                indent_level = leading_spaces // 2
                
                # Normalize bullet character to '-' for consistency
                if is_bullet:
                    # Replace *, +, - with consistent '-'
                    content = re.sub(r'^[\*\-\+]\s+', '', stripped)
                    formatted_item = '  ' * indent_level + '- ' + content
                else:
                    # Numbered list - keep numbering
                    formatted_item = '  ' * indent_level + stripped
                
                formatted_lines.append(formatted_item)
            else:
                # Not a list item
                if in_list and stripped:
                    # Exiting list - add blank line after if next content exists
                    formatted_lines.append('')
                    in_list = False
                
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

    @staticmethod
    def _format_tables(text: str) -> str:
        """
        Format markdown tables with proper alignment and spacing.
        
        Ensures:
        1. Blank line before and after table
        2. Proper pipe alignment
        3. Consistent spacing around pipes
        4. Valid separator row
        """
        lines = text.split('\n')
        formatted_lines = []
        in_table = False
        table_buffer = []
        
        for i, line in enumerate(lines):
            # Detect table row (has pipes with content)
            is_table_row = '|' in line and line.strip().startswith('|') and line.strip().endswith('|')
            
            if is_table_row:
                if not in_table:
                    # Starting new table - add blank line before
                    if formatted_lines and formatted_lines[-1].strip():
                        formatted_lines.append('')
                    in_table = True
                
                table_buffer.append(line)
            else:
                if in_table:
                    # Finish the table
                    formatted_table = MarkdownFormatter._format_table_buffer(table_buffer)
                    formatted_lines.extend(formatted_table)
                    
                    # Add blank line after table if there's more content
                    if line.strip():
                        formatted_lines.append('')
                    
                    table_buffer = []
                    in_table = False
                
                formatted_lines.append(line)
        
        # Handle table at end of document
        if in_table and table_buffer:
            formatted_table = MarkdownFormatter._format_table_buffer(table_buffer)
            formatted_lines.extend(formatted_table)
        
        return '\n'.join(formatted_lines)

    @staticmethod
    def _format_table_buffer(table_rows: List[str]) -> List[str]:
        """Format a complete table with aligned columns"""
        if not table_rows:
            return []
        
        # Parse table cells
        parsed_rows = []
        for row in table_rows:
            # Split by | and clean up cells
            cells = [cell.strip() for cell in row.split('|')]
            # Remove empty first/last elements from split
            cells = [c for c in cells if c or cells.index(c) not in (0, len(cells)-1)]
            if cells:
                parsed_rows.append(cells)
        
        if not parsed_rows:
            return table_rows
        
        # Calculate column widths
        num_cols = max(len(row) for row in parsed_rows)
        col_widths = [0] * num_cols
        
        for row in parsed_rows:
            for col_idx, cell in enumerate(row):
                # Skip separator rows for width calculation
                if not re.match(r'^[\-:]+$', cell):
                    col_widths[col_idx] = max(col_widths[col_idx], len(cell))
        
        # Ensure minimum width of 3 for separator dashes
        col_widths = [max(w, 3) for w in col_widths]
        
        # Format each row with padding
        formatted_rows = []
        for row_idx, row in enumerate(parsed_rows):
            formatted_cells = []
            for col_idx in range(num_cols):
                cell = row[col_idx] if col_idx < len(row) else ''
                
                # Check if this is a separator row
                if re.match(r'^[\-:]+$', cell):
                    # Format as separator with proper dashes
                    formatted_cells.append('-' * col_widths[col_idx])
                else:
                    # Regular cell - pad to width
                    formatted_cells.append(cell.ljust(col_widths[col_idx]))
            
            # Join with proper spacing around pipes
            formatted_row = '| ' + ' | '.join(formatted_cells) + ' |'
            formatted_rows.append(formatted_row)
        
        return formatted_rows

    @staticmethod
    def _format_bold_and_emphasis(text: str) -> str:
        """
        Ensure bold and emphasis markers are properly formatted.
        - No spaces inside markers
        - Consistent use of ** for bold, * for italic
        """
        # Fix bold with extra spaces: ** text ** -> **text**
        text = re.sub(r'\*\*\s+([^\*]+?)\s+\*\*', r'**\1**', text)
        
        # Fix italic with extra spaces: * text * -> *text*
        text = re.sub(r'(?<!\*)\*\s+([^\*]+?)\s+\*(?!\*)', r'*\1*', text)
        
        # Fix bold-italic: *** text *** -> ***text***
        text = re.sub(r'\*\*\*\s+([^\*]+?)\s+\*\*\*', r'***\1***', text)
        
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
        lines = [line.rstrip() for line in text.split('\n')]
        
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
        
        return '\n'.join(cleaned_lines)

    @staticmethod
    def _final_cleanup(text: str) -> str:
        """Final pass to fix any remaining issues"""
        # Remove blank lines at start and end
        text = text.strip()
        
        # Ensure single blank line between major sections
        # (Already handled mostly, but this catches edge cases)
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        # Fix any remaining spacing around headers
        text = re.sub(r'\n(#{1,6}\s+.*?)\n{3,}', r'\n\n\1\n\n', text)
        
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
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    if len(lines) < 2:
        errors.append("Table must have at least header row and separator row")
        return {'valid': False, 'errors': errors}
    
    # Check all lines start and end with |
    for i, line in enumerate(lines):
        if not line.startswith('|') or not line.endswith('|'):
            errors.append(f"Row {i+1} must start and end with |")
    
    # Check separator row (usually second row)
    if len(lines) >= 2:
        sep_row = lines[1]
        cells = [c.strip() for c in sep_row.split('|')[1:-1]]
        for cell in cells:
            if not re.match(r'^:?-+:?$', cell):
                errors.append(f"Invalid separator row format: {sep_row}")
                break
    
    # Check consistent column count
    col_counts = []
    for line in lines:
        count = len([c for c in line.split('|')[1:-1]])
        col_counts.append(count)
    
    if len(set(col_counts)) > 1:
        errors.append(f"Inconsistent column counts: {col_counts}")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }
