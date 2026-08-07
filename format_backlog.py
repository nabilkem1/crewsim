import os
import re
import yaml
import glob

def load_stories_status():
    status_map = {}
    with open('/Users/nabil/Documents/dev/_TS/draft-sim/backlog/stories.yaml', 'r') as f:
        data = yaml.safe_load(f)
        for s in data['stories']:
            status_map[s['id']] = s['status']
    return status_map

def format_file(filepath, status_map):
    with open(filepath, 'r') as f:
        content = f.read()

    # Split by blocks starting with #+ 
    parts = re.split(r'^(#+\s+S\d+[a-zA-Z]*-\d+[a-zA-Z]*.*?)$', content, flags=re.MULTILINE)
    
    if len(parts) == 1:
        # No stories found
        return

    new_content = parts[0]
    
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i+1]
        
        # Determine header level
        m_level = re.match(r'^(#+)\s+', header)
        level = m_level.group(1) if m_level else '##'
        
        # Parse header: ## S1a-04 — Accrue reserve staffing per reserve-day  ·  `S`  ·  fixes **D1**
        # Sometimes there's no fixes
        m_header = re.match(r'^#+\s+(S\w+-\w+)\s+—\s+(.*?)(?:\s+·\s+`(.*?)`)(?:\s+·\s+(.*))?$', header)
        if not m_header:
            # Fallback if no backticks for size, or missing something
            m_header_fallback = re.match(r'^#+\s+(S\w+-\w+)\s+—\s+(.*?)(?:\s+·\s+(.*?))?$', header)
            if not m_header_fallback:
                print(f"Could not parse header in {filepath}: {header}")
                new_content += "\n\n" + header + body
                continue
            story_id = m_header_fallback.group(1).strip()
            title = m_header_fallback.group(2).strip()
            size = m_header_fallback.group(3).strip() if m_header_fallback.group(3) else "?"
            suffix = ""
            # Strip backticks from size if any
            size = size.replace('`', '')
        else:
            story_id = m_header.group(1).strip()
            title = m_header.group(2).strip()
            size = m_header.group(3).strip()
            suffix = m_header.group(4).strip() if m_header.group(4) else ""
            
        status = status_map.get(story_id, 'todo')
        if status == 'done':
            status_tag = "🟢 [DONE]"
        else:
            status_tag = "⏳ [TODO]"
            
        new_header = f"{level} {status_tag} {story_id} — {title}"
        if suffix:
            new_header += f"  ·  {suffix}"
            
        # Parse Depends on & Spec
        # Depends on: S1a-03 · Spec §5.8, §7.2
        m_depends = re.search(r'^Depends on:\s*(.*?)\s*(?:·|\|)\s*Spec\s*(.*?)$', body, re.MULTILINE)
        depends = ""
        spec = ""
        if m_depends:
            depends = m_depends.group(1).strip()
            spec = m_depends.group(2).strip()
            # Remove the old depends line
            body = re.sub(r'^Depends on:.*?$', '', body, flags=re.MULTILINE)
            
        meta_line = f"**Size:** `{size}`"
        if depends:
            meta_line += f" | **Depends on:** {depends}"
        if spec:
            meta_line += f" | **Spec:** {spec}"
            
        # Parse Acceptance
        # **Acceptance** or ### Acceptance
        body = re.sub(r'^\s*\*\*Acceptance\*\*\s*$', '### Acceptance Criteria', body, flags=re.MULTILINE)
        
        # Replace bullets in acceptance criteria
        # Match lines starting with - and replace with - [ ]
        # Only in the acceptance criteria section
        
        sections = re.split(r'^(### Acceptance Criteria|🤖|🙋)', body, flags=re.MULTILINE)
        new_body = sections[0].strip() + "\n\n"
        if len(new_body.strip()) == 0:
            new_body = ""
        
        in_acceptance = False
        verification_lines = []
        
        for j in range(1, len(sections), 2):
            marker = sections[j]
            content_section = sections[j+1]
            
            if marker == '### Acceptance Criteria':
                ac_lines = []
                for line in content_section.splitlines():
                    if line.strip().startswith('-') and not line.strip().startswith('- ['):
                        if status == 'done':
                            ac_lines.append(line.replace('-', '- [x]', 1))
                        else:
                            ac_lines.append(line.replace('-', '- [ ]', 1))
                    elif line.strip().startswith('- [ ]') and status == 'done':
                        ac_lines.append(line.replace('- [ ]', '- [x]', 1))
                    else:
                        ac_lines.append(line)
                new_body += "### Acceptance Criteria\n" + "\n".join(ac_lines).strip() + "\n\n"
                
            elif marker == '🤖' or marker == '🙋':
                if '### Verification' not in new_body and not verification_lines:
                    pass
                verification_lines.append((marker, content_section))

        if verification_lines:
            new_body += "### Verification\n"
            for marker, text in verification_lines:
                lines = text.splitlines()
                first_line = lines[0].strip().strip('`')
                if marker == '🤖':
                    new_body += f"*   🤖 **Automated:** `{first_line}`\n"
                elif marker == '🙋':
                    new_body += f"*   🙋 **Manual:** `{first_line}`\n"
                
                # handle expect/fails if in following lines
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    if line == '---' or line.startswith('---'):
                        continue
                    m_expect = re.match(r'^\**Expect\**\s+(.*)$', line)
                    if m_expect:
                        new_body += f"    *   **Expect:** {m_expect.group(1)}\n"
                        continue
                    m_fails = re.match(r'^\**Fails if\**\s+(.*)$', line)
                    if m_fails:
                        new_body += f"    *   **Fails if:** {m_fails.group(1)}\n"
                        continue
                    
                    # If it doesn't match but is part of the block, append it indented
                    new_body += f"    *   {line}\n"
            new_body += "\n"

        new_content += f"{new_header}\n{meta_line}\n\n{new_body.strip()}\n\n---\n\n"

    # Clean up multiple newlines
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)
    # Remove extra --- at the end of file if we added one
    new_content = re.sub(r'---\s*$', '', new_content)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    print(f"Formatted {filepath}")

def main():
    status_map = load_stories_status()
    # Find all md files
    for root, dirs, files in os.walk('/Users/nabil/Documents/dev/_TS/draft-sim/backlog'):
        for file in files:
            if file.endswith('.md') and not file == 'README.md' and not file == 'COVERAGE_AUDIT.md':
                format_file(os.path.join(root, file), status_map)

if __name__ == "__main__":
    main()
