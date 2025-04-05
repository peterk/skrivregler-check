# This script converts the Svarta listan PDF document to json data.
# Svarta listan has two columns where words in bold in the left column defines words to avoid.
# A corresponding word in the right column on the same line is the suggested replacement word.
# There may be multiple words to avoid on the same line separated by commas.
# There may be multiple suggestions for replacement words separated by "/" (slash).
# 
# The columns are defined by bounding boxes:
#     left_bbox = (20, 40, (width / 2) - 3, height-49)
#     right_bbox = ((width / 2)-3, 40, width, height-49)
#
# The JSON structure for each entry is:
# {
#     "avoid": ["word1", "word2", ...],
#     "prefer": ["replacement1", "replacement2", ...],
#     "source": "Page X"
# }
#
# Usage: python convert_svarta_listan.py <pdf_file> <output_file> [start_page] [end_page]
#        If start_page is provided without end_page, only that specific page will be processed.
#        If both start_page and end_page are provided, all pages in that range (inclusive) will be processed.

import pdfplumber
import json
import sys
import re
from typing import List, Dict, Any, Tuple, Optional, Union

def extract_text_from_columns(pdf_path: str, page_range: Optional[Union[int, Tuple[int, int]]] = None) -> List[Tuple[List[Dict], List[Dict], int]]:
    """
    Extract text from left and right columns of the PDF.
    Returns a list of tuples, each containing the left and right column text with character information,
    and the page number.
    
    Args:
        pdf_path: Path to the PDF file
        page_range: Optional page range to process. Can be:
                   - None: process all pages
                   - int: process only that specific page (0-indexed)
                   - Tuple[int, int]: process all pages in that range (inclusive, 0-indexed)
    """
    column_data = []
    
    with pdfplumber.open(pdf_path) as pdf:
        # Determine which pages to process based on page_range
        if page_range is None:
            # Process all pages
            pages = pdf.pages
        elif isinstance(page_range, int):
            # Process a single page
            if 0 <= page_range < len(pdf.pages):
                pages = [pdf.pages[page_range]]
            else:
                print(f"Error: Page {page_range} is out of range. PDF has {len(pdf.pages)} pages.")
                sys.exit(1)
        else:
            # Process a range of pages
            start_page, end_page = page_range
            if start_page < 0 or end_page >= len(pdf.pages) or start_page > end_page:
                print(f"Error: Page range {start_page}-{end_page} is invalid. PDF has {len(pdf.pages)} pages.")
                sys.exit(1)
            pages = pdf.pages[start_page:end_page+1]
            
        for page in pages:
            width, height = page.width, page.height
            
            # Define bounding boxes for left and right columns
            left_bbox = (20, 40, (width / 2) - 3, height-47)
            right_bbox = ((width / 2)-3, 40, width, height-47)
            
            # Extract text with character information from both columns
            left_chars = page.crop(left_bbox).extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3, extra_attrs=['fontname', 'size'])
            right_chars = page.crop(right_bbox).extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3, extra_attrs=['fontname', 'size'])
            
            # Get the current page number (adjusted as per user's modification)
            current_page = pdf.pages.index(page) + 1 - 2  # Adjust by -2 as per user's modification
            
            # Debug information
            print(f"Page {current_page}, Left column words: {len(left_chars)}, Right column words: {len(right_chars)}")
            
            column_data.append((left_chars, right_chars, current_page))
    
    return column_data

def is_bold_font(fontname: str) -> bool:
    """Check if a fontname indicates bold text."""
    # The specific bold font in this PDF
    return "JWHTPB+TradeGothicPro-Bd2" in fontname

def process_columns(column_data: List[Tuple[List[Dict], List[Dict], int]]) -> List[Dict[str, Any]]:
    """
    Process the column data to extract words to avoid and their replacements.
    Handles multiple words separated by commas and multiple replacements separated by slashes.
    """
    entries = []
    
    for left_words, right_words, page_num in column_data:
        # Group words by their y-position (line)
        left_by_y = {}
        for word in left_words:
            y_pos = int(word['top'])
            if y_pos not in left_by_y:
                left_by_y[y_pos] = []
            left_by_y[y_pos].append(word)
        
        right_by_y = {}
        for word in right_words:
            y_pos = int(word['top'])
            if y_pos not in right_by_y:
                right_by_y[y_pos] = []
            right_by_y[y_pos].append(word)
        
        # Get all unique y-positions (lines) sorted
        all_y_positions = sorted(set(list(left_by_y.keys()) + list(right_by_y.keys())))
        
        # Process each line by y-position
        for i, y_pos in enumerate(all_y_positions):
            # Construct text for this line
            left_line_words = left_by_y.get(y_pos, [])
            right_line_words = right_by_y.get(y_pos, [])
            
            left_line = ' '.join([w['text'] for w in left_line_words])
            right_line = ' '.join([w['text'] for w in right_line_words])
            
            # Skip empty lines
            if not left_line.strip():
                continue
            
            # Check if any word in the left line has the bold font
            has_bold_left = any(is_bold_font(word.get('fontname', '')) for word in left_line_words)
            
            # If this line has bold text in the left column, it's a word to avoid
            if has_bold_left:
                # Get the corresponding right line (may be on the same line or the next line)
                replacement_text = right_line.strip()
                
                # If no replacement on this line, check the next line
                if not replacement_text and i + 1 < len(all_y_positions):
                    next_y_pos = all_y_positions[i + 1]
                    next_right_words = right_by_y.get(next_y_pos, [])
                    replacement_text = ' '.join([w['text'] for w in next_right_words]).strip()
                
                # Split words to avoid by commas
                words_to_avoid = [word.strip() for word in left_line.split(',')]
                
                # Skip entries that only consist of a number in the left column
                # (likely page numbers or section numbers)
                if len(words_to_avoid) == 1 and words_to_avoid[0].isdigit():
                    print(f"Skipping page/section number: {words_to_avoid[0]}")
                    continue
                
                # Split replacement suggestions by slashes
                replacements = []
                if replacement_text:
                    replacements = [repl.strip() for repl in replacement_text.split('/')]
                
                entry = {
                    "avoid": words_to_avoid,
                    "prefer": replacements,
                    "source": f"Page {page_num}"
                }
                
                entries.append(entry)
                print(f"Found entry: {words_to_avoid} -> {replacements} (Page {page_num})")
    
    return entries

def main():
    if len(sys.argv) < 3 or len(sys.argv) > 5:
        print("Usage: python convert_svarta_listan.py <pdf_file> <output_file> [start_page] [end_page]")
        print("       If start_page is provided without end_page, only that specific page will be processed.")
        print("       If both start_page and end_page are provided, all pages in that range (inclusive) will be processed.")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2]
    
    # Determine page range to process
    page_range = None
    
    if len(sys.argv) >= 4:
        try:
            start_page = int(sys.argv[3])
            
            if len(sys.argv) == 5:
                # Process a range of pages
                end_page = int(sys.argv[4])
                page_range = (start_page, end_page)
                print(f"Processing pages {start_page} to {end_page} (0-indexed)")
            else:
                # Process a single page
                page_range = start_page
                print(f"Processing only page {start_page} (0-indexed)")
                
        except ValueError:
            print("Error: Page numbers must be integers")
            sys.exit(1)
    
    # Extract text from columns
    column_data = extract_text_from_columns(pdf_path, page_range)
    
    # Process the columns to extract words to avoid and their replacements
    entries = process_columns(column_data)
    
    # Write the JSON output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    
    print(f"Converted {len(entries)} entries to {output_path}")

if __name__ == "__main__":
    main()
