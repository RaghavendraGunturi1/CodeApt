import re
with open(r'f:\Personal\codeapt_site\templates\assessments\take_section_exam.html', encoding='utf-8') as f:
    text = f.read()

# find all {% ... %}
for m in re.finditer(r'\{%.*?%\}', text, flags=re.DOTALL):
    s = m.group(0)
    if '\n' in s:
        print(f"BROKEN TAG FOUND: {repr(s)}")

lines = text.splitlines()
stack = []
for i, line in enumerate(lines):
    if '{% if' in line or '{% for' in line:
        stack.append((i+1, line.strip()))
    if '{% endif %}' in line or '{% endfor %}' in line:
        if stack:
            stack.pop()
        else:
            print(f"UNMATCHED CLOSE AT {i+1}: {line.strip()}")

print("REMAINING OPEN:", stack)
