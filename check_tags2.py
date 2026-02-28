import re
with open(r'f:\Personal\codeapt_site\templates\assessments\take_section_exam.html', encoding='utf-8') as f:
    text = f.read()

for i, m in enumerate(re.finditer(r'\{%.*?%\}', text, flags=re.DOTALL)):
    s = m.group(0)
    if '\n' in s:
        print(f"BROKEN TAG AT MATCH {i+1}:")
        print("---")
        print(s)
        print("---")
