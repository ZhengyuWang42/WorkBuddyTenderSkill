"""Environment control: exactly the documented public python-docx example."""
import argparse
from pathlib import Path
from docx import Document

def build(output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.add_paragraph('Hello Word')
    doc.save(output)
    return output

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=Path('tmp/99_hello.docx'))
    print(build(p.parse_args().output))
