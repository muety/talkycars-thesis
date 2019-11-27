# TalkyCars Thesis – Report

## LaTeX Setup
* Add TeXstudio PPA: `sudo add-apt-repository ppa:sunderme/texstudio && sudo apt update`
* Install TeXstudio: `sudo apt install texstudio`
* Install LaTeX: `sudo apt install texlive texlive-lang-german texlive-latex-extra texlive-bibtex-extra texlive-science`
* Add TeXstudio [config](/report/texstudio) files
* Add user command to `Options -> Build -> User Commands`:
  * `user0:Make Nomenclature` `makeindex -s nomencl.ist -t %.nlg -o %.nls %.nlo`