# This python script calls the Gemma 3 27B language model to verify a in input text 
# against Myndigheternas skrivregler - the swedish government writing style guide.
#
# The API key is stored in the .env file.
# 
# The script accepts an input text file name for the text to check and an output filename for the result.abs
# 
# Usage: python check.py <input_text_file> <output_file>
# 

import os
import sys
import json
import re
import markdown
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY not found in .env file")

# Constants
STYLE_GUIDE_PATH = Path(__file__).parent / "skrivregler.md"
SVARTA_LISTAN_PATH = Path(__file__).parent / "svarta_listan.json"
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

def load_style_guide():
    """Load the style guide rules from markdown and parse them into categories."""
    with open(STYLE_GUIDE_PATH, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert MD to HTML for easier parsing
    html_content = markdown.markdown(md_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Extract rules by categories (h1, h2, h3 headers)
    rules = []
    current_h1 = None
    current_h2 = None
    current_h3 = None
    current_content = []
    
    for element in soup.find_all(['h1', 'h2', 'h3', 'p']):
        if element.name == 'h1':
            if current_h3 and current_content:
                rules.append({
                    'category': current_h1,
                    'subcategory': current_h2,
                    'rule_name': current_h3,
                    'content': ' '.join(current_content)
                })
                current_content = []
            current_h1 = element.text.strip()
            current_h2 = None
            current_h3 = None
        elif element.name == 'h2':
            if current_h3 and current_content:
                rules.append({
                    'category': current_h1,
                    'subcategory': current_h2,
                    'rule_name': current_h3,
                    'content': ' '.join(current_content)
                })
                current_content = []
            current_h2 = element.text.strip()
            current_h3 = None
        elif element.name == 'h3':
            if current_h3 and current_content:
                rules.append({
                    'category': current_h1,
                    'subcategory': current_h2,
                    'rule_name': current_h3,
                    'content': ' '.join(current_content)
                })
                current_content = []
            current_h3 = element.text.strip()
        elif element.name == 'p':
            current_content.append(element.text.strip())
    
    # Add the last rule if exists
    if current_h3 and current_content:
        rules.append({
            'category': current_h1,
            'subcategory': current_h2,
            'rule_name': current_h3,
            'content': ' '.join(current_content)
        })
    
    return rules

def load_svarta_listan():
    """Load the black list of words to avoid."""
    with open(SVARTA_LISTAN_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def perform_rule_based_checks(text, svarta_listan):
    """Check the text for issues based on specific rules."""
    issues = []
    
    # Check for words in the "svarta listan"
    for item in svarta_listan:
        for word in item["avoid"]:
            # Handle words with explanations in parentheses
            search_word = word.split('(')[0].strip()
            if re.search(r'\b' + re.escape(search_word) + r'\b', text, re.IGNORECASE):
                preferred = ", ".join(item["prefer"]) if item["prefer"][0] else "undvik detta uttryck"
                issues.append({
                    "type": "Undvik ord",
                    "issue": f"Texten innehåller ordet/frasen '{word}'",
                    "suggestion": f"Försök använda: {preferred}",
                    "source": item["source"]
                })
    
    # Check for passive voice (common in Swedish bureaucratic language)
    passive_matches = re.finditer(r'\b\w+[as]s\b', text)
    for match in passive_matches:
        passive_word = match.group(0)
        issues.append({
            "type": "Passiv form",
            "issue": f"Möjlig passiv form: '{passive_word}'",
            "suggestion": "Försök använda aktiv form när möjligt",
            "source": "Regel 1.3.3"
        })
    
    # Check for complex nominal expressions (substantiveringar)
    nominalization_endings = ["ande", "ende", "ing", "ning", "else"]
    for ending in nominalization_endings:
        matches = re.finditer(r'\b\w+' + ending + r'\b', text)
        for match in matches:
            nominal_word = match.group(0)
            issues.append({
                "type": "Substantivering",
                "issue": f"Möjlig substantivering: '{nominal_word}'",
                "suggestion": "Överväg att omformulera med verb istället",
                "source": "Regel 1.4.11" 
            })
    
    return issues

def calculate_lix_score(text):
    """
    Calculate the LIX (Läsbarhetsindex) readability score for a text.
    
    LIX = A/B + (C*100)/A, where:
    A = number of words
    B = number of sentences
    C = number of long words (words with more than 6 characters)
    
    LIX score interpretation:
    <30: Very easy text
    30-40: Easy text
    40-50: Medium difficulty
    50-60: Difficult text
    >60: Very difficult text
    """
    # Remove special characters and normalize whitespace
    text = re.sub(r'[^\w\s\.\!\?]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Count sentences (split on '.', '!', '?')
    sentences = re.split(r'[\.!\?]+', text)
    # Remove empty sentences
    sentences = [s for s in sentences if s.strip()]
    sentence_count = len(sentences)
    
    # Count words
    words = re.findall(r'\b\w+\b', text.lower())
    word_count = len(words)
    
    # Count long words (more than 6 characters)
    long_word_count = sum(1 for word in words if len(word) > 6)
    
    # Calculate LIX score
    if sentence_count == 0 or word_count == 0:
        return 0
    
    lix = (word_count / sentence_count) + ((long_word_count * 100) / word_count)
    
    return round(lix, 1)

def get_lix_interpretation(lix_score):
    """Get a human-readable interpretation of a LIX score."""
    if lix_score < 30:
        return "Mycket lättläst text (motsvarande barnböcker)"
    elif lix_score < 40:
        return "Lättläst text (motsvarande skönlitteratur, populärtidningar)"
    elif lix_score < 50:
        return "Medelsvår text (motsvarande normal tidningstext)"
    elif lix_score < 60:
        return "Svår text (motsvarande officiella texter, facklitteratur)"
    else:
        return "Mycket svår text (motsvarande byråkrattext, lagtexter)"

def analyze_with_gemma(text, style_guide_rules, lix_score, lix_interpretation):
    """Use Gemma 3 LLM to analyze the text against the style guide rules."""
    # Create a simplified version of the style guide for the prompt
    simplified_rules = []
    for rule in style_guide_rules:
        if "Att skriva klarspråk" in rule["category"]:
            simplified_rules.append(f"{rule['rule_name']}: {rule['content']}")
    
    # Create the prompt for Gemma
    prompt = f"""
    Du är en expertkonsult för Myndigheternas skrivregler. Analysera följande text från en svensk myndighet 
    och identifiera hur den kan förbättras enligt Myndigheternas skrivregler.
    
    Här är en sammanfattning av viktiga regler från skrivreglerna:
    
    {'  '.join(simplified_rules[:15])}  
    
    TEXT ATT ANALYSERA:
    {text}
    
    LÄSBARHET:
    Textens LIX-värde är {lix_score}, vilket indikerar: {lix_interpretation}.
    
    Ge en detaljerad analys och uppge specifika exempel på text som bryter mot skrivreglerna. 
    För varje exempel, ange:
    1. Vilken regel som inte följs
    2. Vad problemet är
    3. Ett förslag på hur texten kan förbättras
    
    Avsluta med ett förslag på en korrigerad text. 
    Svara enbart på svenska.
    """
    
    # Call the Gemma API via NVIDIA
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {NVIDIA_API_KEY}"
    }
    
    payload = {
        "model": "google/gemma-3-27b-it",
        "messages": [
            {
                "content": prompt,
                "role": "user"
            }
        ],
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 4096,
        "stream": False
    }
    
    # Call the cNvidia instance of Gemma 3 27B for now. This could be hosted as a local model.
    # 
    response = requests.post(NVIDIA_API_URL, json=payload, headers=headers)
    
    if response.status_code != 200:
        return {"error": f"API error: {response.status_code}", "details": response.text}
    
    result = response.json()
    try:
        analysis = result["choices"][0]["message"]["content"]
        return {"analysis": analysis}
    except (KeyError, IndexError) as e:
        return {"error": f"Error parsing API response: {str(e)}", "details": result}

def generate_report(text, rule_issues, gemma_analysis, lix_score, lix_interpretation):
    """Generate a comprehensive report with all findings."""
    report = []
    report.append("# Språkgranskningsrapport\n")
    report.append("## Sammanfattning\n")
    
    report.append(f"- LIX-värde: {lix_score} - {lix_interpretation}")
    
    if rule_issues:
        report.append(f"- Antal specifika språkregelfel: {len(rule_issues)}")
    else:
        report.append("- Inga specifika språkregelfel hittades.")
    
    if "error" in gemma_analysis:
        report.append("- AI-analys: Misslyckades\n")
    else:
        report.append("- AI-analys genomförd\n")
    
    # Rule-based issues
    if rule_issues:
        report.append("## Specifika språkregelfel\n")
        for i, issue in enumerate(rule_issues, 1):
            report.append(f"### Problem {i}: {issue['type']}\n")
            report.append(f"- **Problem:** {issue['issue']}")
            report.append(f"- **Förslag:** {issue['suggestion']}")
            report.append(f"- **Källa:** {issue['source']}\n")
    
    # Gemma analysis
    report.append("## AI-analys\n")
    if "error" in gemma_analysis:
        report.append(f"Ett fel uppstod vid anrop till Gemma API: {gemma_analysis['error']}\n")
        if "details" in gemma_analysis:
            report.append("Detaljer:\n```\n" + str(gemma_analysis["details"]) + "\n```\n")
    else:
        report.append(gemma_analysis["analysis"])
    
    report.append("\n## Originaltext\n")
    report.append("\n" + text + "\n")
    
    return "\n".join(report)

def main():
    # Check command line arguments
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <input_text_file> <output_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Load the input text
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}")
        sys.exit(1)
    
    # Load style guide and black list
    try:
        style_guide_rules = load_style_guide()
        svarta_listan = load_svarta_listan()
    except Exception as e:
        print(f"Error loading rules: {e}")
        sys.exit(1)
    
    # Perform checks
    print("Performing rule-based checks...")
    rule_issues = perform_rule_based_checks(text, svarta_listan)
    
    # Calculate LIX score
    print("Calculating readability (LIX)...")
    lix_score = calculate_lix_score(text)
    lix_interpretation = get_lix_interpretation(lix_score)
    
    # Analyze with Gemma
    print("Analyzing...")
    gemma_analysis = analyze_with_gemma(text, style_guide_rules, lix_score, lix_interpretation)
    
    # Generate report
    print("Generating report...")
    report = generate_report(text, rule_issues, gemma_analysis, lix_score, lix_interpretation)
    
    # Write output
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report written to {output_file}")
    except Exception as e:
        print(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
