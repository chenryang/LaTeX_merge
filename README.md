# LaTeX_merge

Recursively expands LaTeX files by inlining included files and removing comments.

## Usage

```python latex_expander.py input.tex output.tex [options]```

### Options

- `--bib-dir DIR`: Specify bibliography directory
- `--delete-tex`: Delete other .tex files (keeps by default)
- `--delete-unused-pdf`: Delete unused PDF files (keeps all by default)
