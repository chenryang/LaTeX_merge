# LaTeX_merge

Recursively expands LaTeX files by inlining included files, removing comments, consecutive(>=3) blank lines.

Generated by Claude 3.7 Sonnet and Gemini Pro 2.5

## Usage

```python main.py [input_file] [output_file] [options]```

### Options

- `--delete-tex`: Delete all other .tex files except for output_file (keeps by default)
- `--delete-unused-pdf`: Delete unused PDF files (keeps all by default)
