import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tender_basic.word_safe_scan import scan_word_safe_docx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('docx', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = scan_word_safe_docx(args.docx)
    except Exception as exc:
        report = {'result': 'FAIL', 'error': str(exc)}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    print(text)
    return 0 if report['result'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
