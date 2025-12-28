import os

def clean_extracted_text(text):
    """
    Normalizes text by replacing newlines with spaces and collapsing whitespace
    """
    if not text:
        return ""
    text = text.replace("\n", " ")
    return " ".join(text.split())

def load_corpus(data_dir="data"):
    """Loads documents from the 'data' folder"""
    docs = {}
    
    # Create data dir if it doesn't exist
    if not os.path.exists(data_dir):
        return {}
            
    for f in os.listdir(data_dir):
        file_path = os.path.join(data_dir, f)
        try:
            raw_text = ""
            if f.endswith(".txt") or f.endswith(".md"):
                with open(file_path, "r", encoding="utf-8") as file:
                    raw_text = file.read()
            elif f.endswith(".pdf"):
                import PyPDF2
                with open(file_path, "rb") as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            raw_text += extracted + " "
            elif f.endswith(".docx"):
                import docx
                doc = docx.Document(file_path)
                raw_text = "\n".join([para.text for para in doc.paragraphs])
            docs[f] = clean_extracted_text(raw_text)
            
        except Exception as e:
            print(f"Error loading {f}: {e}")
    return docs

def find_maximal_matches(response_text, corpus_docs, min_len=15):
    """
    Greedy Maximal Exact Match algorithm
    Returns the response text annotated with HTML links for highlights
    """
    output_html = ""
    n = len(response_text)
    i = 0
    
    while i < n:
        best_len = 0
        best_source = None
        
        # Look ahead window (limit to 400 chars max match check)
        max_lookahead = min(n, i + 400)
        
        longest_match_curr = ""
        source_curr = ""
        
        # Simple iterative check
        current_substring = ""
        
        # Word Boundary Check (Heuristic)
        is_word_boundary = True
        if i > 0 and response_text[i-1].isalnum() and response_text[i].isalnum():
             is_word_boundary = False

        if is_word_boundary:
            for j in range(i, max_lookahead):
                char = response_text[j]
                current_substring += char
                
                # Check if this substring exists in any doc
                exists = False
                for doc_name, content in corpus_docs.items():
                    if current_substring in content:
                        exists = True
                        # It exists, so it's a candidate
                        if len(current_substring) >= min_len:
                            if len(current_substring) > len(longest_match_curr):
                                longest_match_curr = current_substring
                                source_curr = doc_name
                        break # Found in at least one doc, continue extending
                
                if not exists:
                    break
        
        if len(longest_match_curr) >= min_len:
            # Create clickable HTML anchor
            # Escape HTML in the text to prevent rendering issues
            safe_text = longest_match_curr.replace("<", "&lt;").replace(">", "&gt;")
            
            # ID format: "doc_name:::encoded_text"
            import urllib.parse
            encoded_text = urllib.parse.quote(longest_match_curr)
            html_tag = f"<a class='verbatim-match' href='#' id='{source_curr}:::{encoded_text}'>{safe_text}</a>"
            output_html += html_tag
            i += len(longest_match_curr)
        else:
            # Append current char and move 1
            safe_char = response_text[i].replace("<", "&lt;").replace(">", "&gt;")
            output_html += safe_char
            i += 1
            
    return output_html.replace("\n", "<br>")
