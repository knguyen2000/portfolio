import os

def load_corpus(data_dir="data"):
    """Loads documents from the 'data' folder."""
    docs = {}
    
    # Create data dir if it doesn't exist (sanity check)
    if not os.path.exists(data_dir):
        return {}
            
    for f in os.listdir(data_dir):
        if f.endswith(".txt") or f.endswith(".md"):
            try:
                with open(os.path.join(data_dir, f), "r", encoding="utf-8") as file:
                    docs[f] = file.read()
            except Exception as e:
                print(f"Error loading {f}: {e}")
    return docs

def find_maximal_matches(response_text, corpus_docs, min_len=15):
    """
    Greedy Maximal Exact Match algorithm.
    Returns the response text annotated with HTML links for highlights.
    """
    output_html = ""
    n = len(response_text)
    i = 0
    
    while i < n:
        best_len = 0
        best_source = None
        
        # Look ahead window (optimization: limit to 400 chars max match check)
        max_lookahead = min(n, i + 400)
        
        longest_match_curr = ""
        source_curr = ""
        
        # Simple iterative check
        current_substring = ""
        for j in range(i, max_lookahead):
            char = response_text[j]
            current_substring += char
            
            # Check if this substring exists in any doc
            exists = False
            for doc_name, content in corpus_docs.items():
                if current_substring in content:
                    exists = True
                    # It exists, so it's a candidate.
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
