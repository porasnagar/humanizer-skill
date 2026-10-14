# Academic LaTeX Templates

The `humanizer` skill supports compiling verified humanized text into publication-ready LaTeX documents (`.tex`) and compiled PDFs.

---

## 1. Standard Academic Article Template

```latex
\documentclass[11pt,a4paper]{article}

% Page Geometry & Margins
\usepackage[margin=1in]{geometry}

% Typography & Math
\usepackage{amsmath,amssymb}
\usepackage{microtype}
\usepackage{setspace}
\setstretch{1.15}

% Clean Headings
\usepackage{titlesec}
\titleformat{\section}{\large\bfseries\color{black}}{\thesection}{1em}{}
\titleformat{\subsection}{\normalsize\bfseries\color{black}}{\thesubsection}{1em}{}

% Tables & Figures
\usepackage{booktabs}
\usepackage{graphicx}

% Hyperlinks
\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    linkcolor=black,
    citecolor=blue,
    urlcolor=blue
}

\title{\textbf{<Document Title>}}
\author{}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
<Abstract text if applicable>
\end{abstract}

<Humanized Body Content>

\end{document}
```

---

## 2. Compilation Instructions

If `pdflatex` or `xelatex` is installed on the host system:
```bash
pdflatex -interaction=nonstopmode document.tex
```

If neither is available, the skill's `formatter.py` automatically falls back to ReportLab to generate a clean, PDF formatted with equivalent academic layout, serif typography, and margins.
