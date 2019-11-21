# TalkyCars Thesis – Report

## LaTeX Setup
* Add TeXstudio PPA: `sudo add-apt-repository ppa:sunderme/texstudio && sudo apt update`
* Install TeXstudio: `sudo apt install texstudio`
* Install LaTeX: `sudo apt install texlive texlive-lang-german texlive-latex-extra texlive-science`
* [Optional] Install GTK styles for Qt: `sudo apt install qt5-style-plugins`

```
# /usr/share/applications/texstudio.desktop 
[Desktop Entry]
Categories=Office;Publishing;Qt;X-SuSE-Core-Office;X-Mandriva-Office-Publishing;X-Misc;
Exec=env QT_QPA_PLATFORMTHEME=gtk2 texstudio %F
GenericName=LaTeX Editor
GenericName[de]=LaTeX Editor
GenericName[fr]=Editeur LaTeX
Comment=LaTeX development environment
Comment[de]=LaTeX Entwicklungsumgebung
Comment[fr]=Environnement de développement LaTeX
Icon=texstudio
Keywords=LaTeX;TeX;editor;
MimeType=text/x-tex;
Name=TeXstudio
StartupNotify=false
Terminal=false
Type=Application
```