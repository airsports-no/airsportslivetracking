import re
import sys
import argparse
import difflib

# Improved prefix regex to handle various gate formats: SP, TP 1, WP-3, Start, Finish, FP, SC1, etc.
PREFIX_RE = re.compile(r'^([A-Za-z0-9\s\.\-\(\)]+): ')

def normalize_log(log_entry):
    """Removes gate prefixes (e.g., 'SP: ', 'TP 1: ') to compare the core message."""
    if not log_entry:
        return ""
    return PREFIX_RE.sub('', log_entry).strip()

def are_logs_similar(left, right):
    """
    Checks if two log entries are similar based on timing jitter, waypoint shifts, 
    and point differences in corridor scoring.
    """
    if not left or not right:
        return left == right
        
    l = normalize_log(left)
    r = normalize_log(right)
    
    if l == r:
        return True
    
    # Normalize point values in corridor logs to allow matching with different scores
    # Example: "315 points outside corridor" -> "outside corridor"
    # This handles the user's request to ignore corridor score differences.
    l_norm = re.sub(r'^\d+ points outside corridor', 'outside corridor', l)
    r_norm = re.sub(r'^\d+ points outside corridor', 'outside corridor', r)
    
    if l_norm == r_norm:
        return True

    # 1s timing jitter check on the normalized messages
    # Matches patterns like (12 s), (+2 s), (-4 s)
    pattern = r'^(.*)\(([\+\-]?\d+)\s*s\)(.*)$'
    ml = re.match(pattern, l_norm)
    mr = re.match(pattern, r_norm)
    
    if ml and mr:
        pre_l, sec_l, suf_l = ml.groups()
        pre_r, sec_r, suf_r = mr.groups()
        
        if pre_l == pre_r and suf_l == suf_r:
            try:
                if abs(int(sec_l) - int(sec_r)) <= 1:
                    return True
            except ValueError:
                pass
                
    return False

def normalize_for_matcher(s):
    """
    Aggressive normalization used only for the difflib alignment.
    Masks gate names, timing values, and corridor scores so difflib can find 
    the 'best' alignment of similar events even if they aren't identical.
    """
    s = normalize_log(s)
    # Mask corridor scores
    s = re.sub(r'^\d+ points outside corridor', 'outside corridor', s)
    # Mask timing jitter (+2 s), (12 s), etc.
    s = re.sub(r'\([\+\-]?\d+\s*s\)', '(TIME s)', s)
    return s

def parse_and_filter(report_path, output_path):
    with open(report_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    # Split into sections based on the delimiter
    sections = content.split("-" * 40)
    
    header_block = sections[0].split("================================================================================")
    header = header_block[0]
    filtered_output = [header + "================================================================================\n"]
    
    original_failures = 0
    filtered_failures = 0
    
    for section in sections:
        if "FAILURE:" not in section:
            continue
            
        original_failures += 1
            
        # Extract contestant info and discrepancies
        lines = section.strip().split('\n')
        failure_header = []
        discrepancies = []
        log_lines = []
        in_logs = False
        
        for line in lines:
            if line.startswith("FAILURE:"):
                failure_header.append(line)
            elif line.startswith("Link:"):
                failure_header.append(line)
            elif line.startswith(" - "):
                discrepancies.append(line)
            elif "Side-by-side Score Log" in line:
                in_logs = True
            elif in_logs:
                log_lines.append(line)
        
        # Parse side-by-side logs into two clean sequences
        orig_list = []
        clone_list = []
        
        for log_line in log_lines:
            if "!!" in log_line:
                parts = log_line.split(" !! ")
                left = parts[0].strip()
                right = parts[1].strip() if len(parts) > 1 else ""
                if left: orig_list.append(left)
                if right: clone_list.append(right)
            else:
                msg = log_line.strip()
                if msg:
                    orig_list.append(msg)
                    clone_list.append(msg)

        # Filter out 'Excursion penalty so far' and 'backtracking'
        orig_clean = [l for l in orig_list if "Excursion penalty so far" not in l and "backtracking" not in l]
        clone_clean = [l for l in clone_list if "Excursion penalty so far" not in l and "backtracking" not in l]
        
        # Align using normalized strings
        orig_norm = [normalize_for_matcher(l) for l in orig_clean]
        clone_norm = [normalize_for_matcher(l) for l in clone_clean]
        
        matcher = difflib.SequenceMatcher(None, orig_norm, clone_norm)
        
        # Check if all log mismatches are acceptable using greedy matching
        pending_orig = []
        pending_clone = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for k in range(i2 - i1):
                    l_orig = orig_clean[i1 + k]
                    r_clone = clone_clean[j1 + k]
                    if not are_logs_similar(l_orig, r_clone):
                        pending_orig.append(l_orig)
                        pending_clone.append(r_clone)
            elif tag == 'delete':
                for k in range(i1, i2): pending_orig.append(orig_clean[k])
            elif tag == 'insert':
                for k in range(j1, j2): pending_clone.append(clone_clean[k])
            elif tag == 'replace':
                for k in range(i1, i2): pending_orig.append(orig_clean[k])
                for k in range(j1, j2): pending_clone.append(clone_clean[k])

        orig_to_match = list(pending_orig)
        clone_to_match = list(pending_clone)
        still_pending_orig = []
        for o in orig_to_match:
            matched = False
            for idx, c in enumerate(clone_to_match):
                if are_logs_similar(o, c):
                    clone_to_match.pop(idx)
                    matched = True
                    break
            if not matched: still_pending_orig.append(o)
        
        log_mismatch_resolved = (len(still_pending_orig) == 0 and len(clone_to_match) == 0)
        
        # Build surgical diff (only showing items that aren't similar)
        surgical_diff = []
        col_width = 80
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for k in range(i2 - i1):
                    l_orig, r_clone = orig_clean[i1 + k], clone_clean[j1 + k]
                    if not are_logs_similar(l_orig, r_clone):
                        surgical_diff.append(f"{l_orig:<{col_width}} !! {r_clone}")
            else:
                max_lines = max(i2 - i1, j2 - j1)
                for k in range(max_lines):
                    l_val = orig_clean[i1 + k] if (i1 + k) < i2 else ""
                    r_val = clone_clean[j1 + k] if (j1 + k) < j2 else ""
                    if not are_logs_similar(l_val, r_val):
                        surgical_diff.append(f"{l_val:<{col_width}} !! {r_val}")

        # Filter the discrepancies list
        remaining_discrepancies = []
        for d in discrepancies:
            # Rule: If logs are functionally identical after filtering, we also ignore the score mismatch
            # as it is likely a direct result of the ignored log entries (e.g. backtracking points).
            if "Score mismatch" in d and log_mismatch_resolved:
                continue
                
            # Rule: Ignore score mismatches of <= 1.0 point (timing jitter)
            score_match = re.search(r'Score mismatch: Original=([\d\.]+), Cloned=([\d\.]+)', d)
            if score_match and abs(float(score_match.group(1)) - float(score_match.group(2))) <= 1.0:
                continue
                
            if "Score log mismatch detected" in d and log_mismatch_resolved:
                continue
            remaining_discrepancies.append(d)
            
        if remaining_discrepancies:
            filtered_failures += 1
            block = "\n" + "\n".join(failure_header) + "\n" + "\n".join(remaining_discrepancies) + "\n"
            block += "\nFull Side-by-side Score Log (Original vs Cloned):\n" + "\n".join(log_lines) + "\n"
            if not log_mismatch_resolved:
                block += "\nSurgical Score Log (True Differences Only):\n" + "\n".join(surgical_diff) + "\n"
            block += "-" * 40 + "\n"
            filtered_output.append(block)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(filtered_output)
    print(f"Original failures: {original_failures}\nFiltered failures: {filtered_failures}\nFiltered report: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter recalculation test report.")
    parser.add_argument("report_file", nargs="?", default="recalculation_test_report.txt")
    parser.add_argument("output_file", nargs="?", default="filtered_recalculation_report.txt")
    args = parser.parse_args()
    parse_and_filter(args.report_file, args.output_file)
