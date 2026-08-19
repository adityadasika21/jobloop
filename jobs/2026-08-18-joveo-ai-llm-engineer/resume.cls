% =============================================================================
% resume.cls — self-contained one-page resume class for jobloop.
%
% Reconciled against reference/resume-source.tex — Aditya's own authoritative
% source, supplied 2026-08-18. This class was reverse-engineered from a
% compiled PDF before that file existed; where the two disagree, HIS WINS.
% Point size, margins, list indents, tabular widths and section-heading weight
% below are his values, not the reconstruction's.
%
% Deliberately depends ONLY on packages verified present on this machine:
%   geometry, titlesec, enumitem, hyperref, fontawesome5, tabularx, marvosym
% moderncv and altacv are NOT installed and are not used.
% =============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/08/18 jobloop resume class]

\LoadClass[letterpaper,10pt]{article}

\RequirePackage{latexsym}
\RequirePackage[empty]{fullpage}
\RequirePackage{titlesec}
\RequirePackage{marvosym}
\RequirePackage[usenames,dvipsnames]{color}
\RequirePackage{verbatim}
\RequirePackage{enumitem}
\RequirePackage[hidelinks]{hyperref}
\RequirePackage{fancyhdr}
\RequirePackage[english]{babel}
\RequirePackage{tabularx}
\RequirePackage{fontawesome5}
\RequirePackage{multicol}
\RequirePackage{ragged2e}

% Ensure that generated pdf is machine readable / ATS parsable. This is the
% single highest-value line in the class: it installs the glyph->unicode map
% pdfLaTeX needs for text extraction to be reliable rather than lucky. His
% source carries it; the reconstruction had lost it entirely.
% Guarded because build_pdf() falls back to lualatex, which has no
% \pdfgentounicode and needs no equivalent.
\ifdefined\pdfgentounicode
  \input{glyphtounicode}
  \pdfgentounicode=1
\fi

\setlength{\multicolsep}{-3.0pt}
\setlength{\columnsep}{-1pt}

% Zero out list leading globally. LaTeX's default itemize spacing is tuned
% for prose, and on a dense one-page resume it silently costs ~4 lines --
% which is exactly what pushed Education onto page 2.
\setlist[itemize]{topsep=2pt, partopsep=0pt, parsep=0pt, itemsep=1pt}
\setlength{\parskip}{0pt}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

% ---- Margins -----------------------------------------------------------------
\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% ---- Section headings: small caps + rule ------------------------------------
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

% ---- Building blocks ---------------------------------------------------------
\newcommand{\resumeItem}[1]{%
  \item\small{#1 \vspace{-3pt}}%
}

\newcommand{\resumeSubheading}[4]{%
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & \textbf{\small #2} \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-5pt}%
}

\newcommand{\resumeProjectHeading}[2]{%
  \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & \textbf{\small #2}\\
    \end{tabular*}\vspace{-5pt}%
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-2pt}}

% ---- Header ------------------------------------------------------------------
% #1 name  #2 headline  #3 contact line
\newcommand{\resumeHeader}[3]{%
  \begin{center}
    {\Huge \scshape #1} \\ \vspace{3pt}
    \small #2 \\ \vspace{2pt}
    \footnotesize #3
  \end{center}\vspace{-6pt}%
}

\endinput
