% =============================================================================
% resume.cls — self-contained one-page resume class for jobloop.
%
% Reproduces the layout of the original Aditya_Resume.pdf (Jake-Ryan-style:
% Computer Modern, small-caps rules under section headings, right-aligned dates).
%
% Deliberately depends ONLY on packages verified present on this machine:
%   geometry, titlesec, enumitem, hyperref, fontawesome5, tabularx, marvosym
% moderncv and altacv are NOT installed and are not used.
% =============================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{resume}[2026/08/18 jobloop resume class]

\LoadClass[letterpaper,11pt]{article}

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
\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1.19in}
\addtolength{\topmargin}{-0.7in}
\addtolength{\textheight}{1.4in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

% ---- Section headings: small caps + rule ------------------------------------
\titleformat{\section}{
  \vspace{-5pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{-6pt}]

% ---- Building blocks ---------------------------------------------------------
\newcommand{\resumeItem}[1]{%
  \item\small{#1 \vspace{-3pt}}%
}

\newcommand{\resumeSubheading}[4]{%
  \vspace{-2pt}\item
    \begin{tabular*}{1.0\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & \textbf{\small #2} \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-5pt}%
}

\newcommand{\resumeProjectHeading}[2]{%
  \item
    \begin{tabular*}{1.001\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & \textbf{\small #2}\\
    \end{tabular*}\vspace{-5pt}%
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}

\renewcommand\labelitemi{$\vcenter{\hbox{\tiny$\bullet$}}$}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}

\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}]}
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
