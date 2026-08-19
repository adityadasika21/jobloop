% =============================================================================
% resume.cls — self-contained one-page resume class for jobloop.
%
% This is Aditya's own source, reference/resume-source.tex, expressed as a
% class. Its preamble is reproduced line for line: point size, margins, section
% format, and — the part that was got wrong the first time — every piece of
% vertical spacing.
%
% The earlier version kept the reconstruction's own spacing machinery (a
% \setlist override killing itemsep, \parskip 0pt, and negative \vspace values
% tuned for 11pt) while adopting his 10pt body and margins. The result had no
% gap between bullets and ran project headings into the line above. Spacing is
% a system: half of one and half of another is not a compromise, it is a
% third layout nobody designed.
%
% If you change a \vspace here, diff the rendered PDF against
% reference/resume-source.tex before committing it.
% =============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/08/19 jobloop resume class]

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

% Ensure that generated pdf is machine readable / ATS parsable. Guarded
% because build_pdf() falls back to lualatex, which has no \pdfgentounicode.
\ifdefined\pdfgentounicode
  \input{glyphtounicode}
  \pdfgentounicode=1
\fi

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
\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

% ---- Header ------------------------------------------------------------------
% #1 name  #2 headline  #3 contact line
% Reproduces his \begin{center} block exactly, including that \small applies
% to both the headline and the contact line below it.
\newcommand{\resumeHeader}[3]{%
  \begin{center}
    \textbf{\Huge \scshape #1} \\ \vspace{2pt}
    \small #2 \\ \vspace{3pt}
    #3
  \end{center}%
}

\endinput
