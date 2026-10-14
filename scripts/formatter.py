"""Humanizer Multi-Format Output Compiler.
Generates polished output files in the user's requested format:
- Markdown (.md)
- Microsoft Word (.docx)
- Standard PDF (.pdf via ReportLab)
- Academic LaTeX Document (.tex) and LaTeX-compiled PDF

Compatible with Antigravity, Claude Code, OpenAI Codex, OpenCode, and Hermes.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ── Markdown Formatter ───────────────────────────────────────────────────────

def export_markdown(text: str, output_path: Path | str) -> Path:
    out = Path(output_path).with_suffix(".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    return out


# ── Word (.docx) Formatter ───────────────────────────────────────────────────

def export_docx(text: str, output_path: Path | str) -> Path:
    try:
        import docx
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise ImportError("python-docx is required for Word export. Run: pip install python-docx")

    out = Path(output_path).with_suffix(".docx")
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = docx.Document()

    # Set 1-inch margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Configure Normal style font: Calibri 11pt, 1.15 line spacing, 6pt after
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    font.color.rgb = RGBColor(0x22, 0x22, 0x22)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Headings
        if line.startswith("# "):
            p = doc.add_paragraph()
            run = p.add_run(line[2:].strip())
            run.font.name = 'Calibri'
            run.font.size = Pt(18)
            run.bold = True
            run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
        elif line.startswith("## "):
            p = doc.add_paragraph()
            run = p.add_run(line[3:].strip())
            run.font.name = 'Calibri'
            run.font.size = Pt(14)
            run.bold = True
            run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
        elif line.startswith("### "):
            p = doc.add_paragraph()
            run = p.add_run(line[4:].strip())
            run.font.name = 'Calibri'
            run.font.size = Pt(12)
            run.bold = True
            run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(2)
        elif line.startswith(("- ", "* ", "• ")):
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(line[2:].strip())
            p.paragraph_format.space_after = Pt(2)
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.line_spacing = 1.15
            # Render basic markdown bold formatting
            parts = re.split(r'(\*\*.*?\*\*)', line)
            for part in parts:
                if part.startswith("**") and part.endswith("**") and len(part) >= 4:
                    r = p.add_run(part[2:-2])
                    r.bold = True
                else:
                    p.add_run(part)

        i += 1

    doc.save(str(out))
    return out


# ── PDF Formatter (ReportLab) ─────────────────────────────────────────────────

def export_pdf(text: str, output_path: Path | str) -> Path:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
    except ImportError:
        raise ImportError("reportlab is required for PDF export. Run: pip install reportlab")

    out = Path(output_path).with_suffix(".pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        spaceAfter=12,
        textColor='#111827'
    )
    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=6,
        textColor='#1F2937'
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
        textColor='#1F2937'
    )

    story = []
    lines = text.split("\n\n")
    for block in lines:
        block = block.strip()
        if not block:
            continue
        if block.startswith("# "):
            story.append(Paragraph(block[2:].strip(), title_style))
        elif block.startswith("## "):
            story.append(Paragraph(block[3:].strip(), h2_style))
        elif block.startswith("### "):
            story.append(Paragraph(block[4:].strip(), h2_style))
        else:
            # Escape HTML brackets for ReportLab
            clean_p = block.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            clean_p = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean_p)
            clean_p = re.sub(r'\*(.*?)\*', r'<i>\1</i>', clean_p)
            story.append(Paragraph(clean_p, body_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    return out


# ── LaTeX Academic Formatter (.tex & compiled .pdf) ───────────────────────────

def export_latex(text: str, output_path: Path | str, compile_pdf: bool = True) -> Tuple[Path, Optional[Path]]:
    out_tex = Path(output_path).with_suffix(".tex")
    out_tex.parent.mkdir(parents=True, exist_ok=True)

    def escape_latex(s: str) -> str:
        s = s.replace('\\', '\\textbackslash{}')
        s = s.replace('&', '\\&').replace('%', '\\%').replace('$', '\\$').replace('#', '\\#')
        s = s.replace('_', '\\_').replace('{', '\\{').replace('}', '\\}').replace('~', '\\textasciitilde{}')
        s = s.replace('^', '\\textasciicircum{}')
        return s

    lines = text.splitlines()
    doc_title = "Document"
    body_latex = []

    for line in lines:
        l = line.strip()
        if not l:
            body_latex.append("")
            continue
        if l.startswith("# "):
            doc_title = l[2:].strip()
            body_latex.append(f"\\section*{{{escape_latex(doc_title)}}}")
        elif l.startswith("## "):
            body_latex.append(f"\\subsection*{{{escape_latex(l[3:].strip())}}}")
        elif l.startswith("### "):
            body_latex.append(f"\\subsubsection*{{{escape_latex(l[4:].strip())}}}")
        elif l.startswith(("- ", "* ", "• ")):
            body_latex.append(f"\\begin{{itemize}}\n  \\item {escape_latex(l[2:].strip())}\n\\end{{itemize}}")
        else:
            # Convert **bold** to \textbf
            escaped = escape_latex(l)
            escaped = re.sub(r'\\textbackslash\{\}textbf\\\{(.*?)\\\}', r'\\textbf{\1}', escaped)
            body_latex.append(f"{escaped}\n")

    latex_code = f"""\\documentclass[11pt,a4paper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{amsmath,amssymb}}
\\usepackage{{microtype}}
\\usepackage{{setspace}}
\\setstretch{{1.15}}
\\usepackage{{hyperref}}
\\hypersetup{{colorlinks=true, linkcolor=blue, citecolor=blue, urlcolor=blue}}

\\title{{\\textbf{{{escape_latex(doc_title)}}}}}
\\author{{}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

{chr(10).join(body_latex)}

\\end{{document}}
"""
    with open(out_tex, "w", encoding="utf-8") as f:
        f.write(latex_code)

    compiled_pdf = None
    if compile_pdf:
        # Check if pdflatex or xelatex is present
        compiler = shutil.which("pdflatex") or shutil.which("xelatex")
        if compiler:
            try:
                subprocess.run(
                    [compiler, "-interaction=nonstopmode", out_tex.name],
                    cwd=str(out_tex.parent),
                    capture_output=True,
                    timeout=30
                )
                pdf_cand = out_tex.with_suffix(".pdf")
                if pdf_cand.exists():
                    compiled_pdf = pdf_cand
            except Exception:
                pass

        # If pdflatex not on system, use ReportLab to generate LaTeX-styled academic PDF
        if not compiled_pdf:
            compiled_pdf = export_pdf(text, output_path)

    return out_tex, compiled_pdf


def compile_format(text: str, output_path: Path | str, target_format: str) -> str:
    """Universal dispatcher for the requested output format."""
    fmt = target_format.lower().strip().replace(".", "")

    if fmt in ["md", "markdown"]:
        out = export_markdown(text, output_path)
        return str(out)
    elif fmt in ["docx", "word", "doc"]:
        out = export_docx(text, output_path)
        return str(out)
    elif fmt == "pdf":
        out = export_pdf(text, output_path)
        return str(out)
    elif fmt in ["latex", "tex", "latex-pdf"]:
        tex_path, pdf_path = export_latex(text, output_path, compile_pdf=True)
        return f"{tex_path} (and {pdf_path})"
    else:
        out = export_markdown(text, output_path)
        return str(out)


def main():
    parser = argparse.ArgumentParser(description="Compile text to md, docx, pdf, or latex")
    parser.add_argument("input", type=str, help="Input text or markdown file")
    parser.add_argument("--format", "-f", type=str, default="md", choices=["md", "docx", "pdf", "latex"], help="Target format")
    parser.add_argument("--output", "-o", type=str, required=True, help="Destination file base path")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        content = f.read()

    res = compile_format(content, args.output, args.format)
    print(f"[Formatter] Exported to: {res}")


if __name__ == "__main__":
    main()
